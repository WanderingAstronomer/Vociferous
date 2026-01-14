"""
Vociferous - Main orchestration module.

Coordinates KeyListener → ResultThread → clipboard output via Qt signals.
Tracks signal connections in _thread_connections for proper cleanup.
"""

import logging
import os
import sys

from PyQt6.QtCore import (
    QLockFile,
    QObject,
    QThread,
    QTimer,
    pyqtSignal,
    pyqtSlot,
    qInstallMessageHandler,
)
from PyQt6.QtWidgets import QApplication, QMessageBox

from history_manager import HistoryManager
from input_handler import KeyListener
from result_thread import ResultThread
from services.slm_service import SLMService
from transcription import create_local_model
from ui.components.main_window import MainWindow
from ui.components.settings import SettingsDialog
from ui.components.system_tray import SystemTrayManager
from ui.utils.clipboard_utils import copy_text
from ui.utils.error_handler import get_error_logger, install_exception_hook
from ui.widgets.dialogs.error_dialog import show_error_dialog
from utils import ConfigManager

logger = logging.getLogger(__name__)

# Prefer client-side decorations on Wayland so we can draw our own frame
os.environ.setdefault("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1")

_QT_MESSAGE_HANDLER_INSTALLED = False
_TRAY_DBUS_ERROR_SEEN = False


def _qt_message_handler(_mode, _context, message: str) -> None:
    global _TRAY_DBUS_ERROR_SEEN
    if "QDBusTrayIcon encountered a D-Bus error" in message:
        _TRAY_DBUS_ERROR_SEEN = True
        return
    sys.__stderr__.write(f"{message}\n")
    sys.__stderr__.flush()


def _install_qt_message_handler() -> None:
    global _QT_MESSAGE_HANDLER_INSTALLED
    if _QT_MESSAGE_HANDLER_INSTALLED:
        return
    qInstallMessageHandler(_qt_message_handler)
    _QT_MESSAGE_HANDLER_INSTALLED = True


class _HotkeyDispatcher(QObject):
    """Dispatch hotkey callbacks onto the Qt main thread.

    KeyListener callbacks run in a background thread. Emitting these signals from
    that thread ensures the connected slots execute on the main Qt thread.
    """

    activated = pyqtSignal()
    deactivated = pyqtSignal()


def _get_lock_file_path() -> str:
    """Get the lock file path, respecting environment override."""
    override = os.environ.get("VOCIFEROUS_LOCK_PATH")
    if override:
        return override
    import tempfile
    return os.path.join(tempfile.gettempdir(), "vociferous.lock")


class VociferousApp(QObject):
    """Main application orchestrator coordinating all components."""

    requestRefinement = pyqtSignal(int, str, str)  # id, text, profile

    def __init__(self) -> None:
        # Initialize error logging FIRST (before anything else)
        get_error_logger()

        # Install global exception hook with error dialog callback
        install_exception_hook(self._show_global_error)

        _install_qt_message_handler()
        # Check for existing instance BEFORE creating QApplication

        lock_file_path = _get_lock_file_path()
        self.lock = QLockFile(lock_file_path)
        # Allow recovery from crashes: if a prior instance dies without releasing
        # the lock, we still want users to be able to start the app.
        self.lock.setStaleLockTime(10_000)  # ms

        if not self.lock.tryLock():
            # Try to recover from a stale lock file (e.g., app crash).
            if self.lock.removeStaleLockFile() and self.lock.tryLock():
                pass
            else:
                # Show error via stderr to avoid Qt initialization
                print(
                    "ERROR: Vociferous is already running. Only one instance allowed.",
                    file=sys.stderr,
                )
                sys.exit(1)

        super().__init__()
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Vociferous")
        self.app.setQuitOnLastWindowClosed(False)  # Keep running in tray

        # Set larger base font for 2x UI scale
        font = self.app.font()
        font.setPointSize(18)
        self.app.setFont(font)

        # DON'T apply stylesheet here - it causes Qt to crash when validating
        # hierarchical models during widget tree creation.
        # We'll apply it after all widgets are initialized.
        # from ui.styles.unified_stylesheet import generate_unified_stylesheet
        # self.app.setStyleSheet(generate_unified_stylesheet())

        # Initialize config
        ConfigManager.initialize()

        # Re-configure logging now that config is loaded (to apply user log level)
        get_error_logger().configure_logging()

        # Ensure hotkey callbacks are handled on the Qt main thread.
        self._hotkey_dispatcher = _HotkeyDispatcher()
        self._hotkey_dispatcher.activated.connect(self.on_activation)
        self._hotkey_dispatcher.deactivated.connect(self.on_deactivation)

        self.settings_dialog: SettingsDialog | None = None

        # Initialize components
        self.initialize_components()

        logger.info("Vociferous initialized successfully")

    def _show_global_error(self, title: str, message: str, details: str) -> None:
        """Show an error dialog for uncaught exceptions."""
        try:
            # Try to get the main window as parent
            parent = getattr(self, "main_window", None)
            show_error_dialog(
                title=title,
                message=message,
                details=details,
                parent=parent,
            )
        except Exception as e:
            # Last resort: print to stderr
            logger.error(f"Failed to show error dialog: {e}")
            print(f"CRITICAL ERROR: {title}\n{message}\n{details}", file=sys.stderr)

    def _on_gpu_confirmation_requested(
        self, free_mb: int, total_mb: int, needed_mb: int
    ) -> None:
        """
        Handle request for GPU usage confirmation when VRAM is tight.
        Called from SLMService background thread via signal (QueuedConnection).
        """
        # Calculate percentages
        remaining_mb = free_mb - needed_mb
        headroom_pct = (remaining_mb / total_mb) * 100

        logger.info(
            f"Prompting user for GPU usage: Free={free_mb}, Needed={needed_mb}, Headroom={headroom_pct:.1f}%"
        )

        reply = QMessageBox.question(
            getattr(self, "main_window", None),
            "GPU Configuration Warning",
            f"<b>Limited VRAM Detected</b><br><br>"
            f"Vociferous wants to load the refinement model into GPU memory for speed.<br>"
            f"<ul>"
            f"<li>Total VRAM: {total_mb} MB</li>"
            f"<li>Available: {free_mb} MB</li>"
            f"<li>Required: ~{needed_mb} MB</li>"
            f"<li><b>Projected Headroom: {headroom_pct:.1f}%</b></li>"
            f"</ul>"
            f"Loading to GPU with &lt;20% headroom might cause system instability or crash other applications.<br><br>"
            f"Do you want to proceed with GPU loading?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        use_gpu = reply == QMessageBox.StandardButton.Yes
        self.slm_service.submit_gpu_choice(use_gpu)

    def initialize_components(self) -> None:
        """Initialize components in dependency order: listener, model, UI, tray."""
        try:
            ConfigManager.console_print("Initializing Vociferous...")

            # Key listener for hotkey detection
            self.key_listener = KeyListener()
            self.key_listener.add_callback(
                "on_activate", lambda: self._hotkey_dispatcher.activated.emit()
            )
            self.key_listener.add_callback(
                "on_deactivate", lambda: self._hotkey_dispatcher.deactivated.emit()
            )

            # Load whisper model
            ConfigManager.console_print(
                "Loading Whisper model (this may take a moment)..."
            )
            self.local_model = create_local_model()

            # Result thread (for recording/transcription)
            self.result_thread: ResultThread | None = None

            # History manager for transcription storage
            self.history_manager = HistoryManager()

            # Main window (shows recording/transcribing state)
            self.main_window = MainWindow(self.history_manager, self.key_listener)
            self.main_window.setWindowIcon(SystemTrayManager.build_icon(self.app))

            # Cancel recording without transcribing
            self.main_window.cancelRecordingRequested.connect(self._cancel_recording)

            # Connect workspace start/stop signals
            self.main_window.startRecordingRequested.connect(self.start_result_thread)
            self.main_window.stopRecordingRequested.connect(
                self._stop_recording_from_ui
            )

            # System tray
            self.tray_manager = SystemTrayManager(
                self.app, self.main_window, self.show_settings, self.exit_app
            )
            self.main_window.windowCloseRequested.connect(self.exit_app)

            # React to configuration changes
            ConfigManager.instance().configChanged.connect(self._on_config_changed)

            # Initialize SLM Service (Refinement Backend)
            self.slm_thread = QThread()
            self.slm_service = SLMService()
            self.slm_service.moveToThread(self.slm_thread)

            self.requestRefinement.connect(self.slm_service.handle_refinement_request)
            self.slm_service.refinementSuccess.connect(self._on_refinement_success)
            self.slm_service.refinementError.connect(self._on_refinement_error)

            # Handle GPU Confirmation
            self.slm_service.askGPUConfirmation.connect(
                self._on_gpu_confirmation_requested
            )
            
            # Workspace signal connection removed (Legacy)

            self.slm_thread.start()

            if ConfigManager.get_config_value("refinement", "enabled"):
                QTimer.singleShot(0, self.slm_service.initialize_service)

            # Start listening for hotkey
            self.key_listener.start()

            activation_key = ConfigManager.get_config_value(
                "recording_options", "activation_key"
            )
            ConfigManager.console_print(f"Ready! Press '{activation_key}' to start.")

            # Show the window explicitly on startup
            self.main_window.show()

            # NOW apply stylesheet after all widgets are initialized
            # (applying stylesheet during widget tree creation causes Qt crashes)
            from ui.styles.unified_stylesheet import generate_unified_stylesheet

            self.app.setStyleSheet(generate_unified_stylesheet())

        except Exception as e:
            logger.exception("Failed to initialize components")
            self._show_global_error(
                title="Initialization Error",
                message=f"Failed to initialize Vociferous: {e}",
                details=f"Please check your configuration and try again.\n\nError: {e}",
            )
            raise


    def show_settings(self) -> None:
        """Open the settings dialog and apply changes immediately."""
        try:
            # Create fresh dialog each time to avoid state issues
            dialog = SettingsDialog(self.key_listener, self.main_window)
            dialog.exec()
        except Exception as e:
            logger.exception("Error showing settings dialog")
            self._show_global_error(
                title="Settings Error",
                message=f"Failed to open settings: {e}",
                details="",
            )

    @pyqtSlot(str, str, object)
    def _on_config_changed(self, section: str, key: str, value) -> None:
        """Handle live config updates for hotkey, backend, and model changes."""
        try:
            if section == "recording_options" and key == "activation_key":
                self.key_listener.update_activation_keys()
                return

            if section == "recording_options" and key == "input_backend":
                self.key_listener.update_backend()
                return

            # Reload model when model options change
            if section == "model_options" and key in {
                "compute_type",
                "device",
                "language",
            }:
                self._reload_model()
        except Exception as e:
            logger.exception("Error applying config change")
            self._show_global_error(
                title="Configuration Error",
                message=f"Failed to apply configuration change: {e}",
                details=f"Section: {section}, Key: {key}, Value: {value}",
            )

    def _reload_model(self) -> None:
        """Reload the Whisper model with updated configuration."""
        try:
            ConfigManager.console_print("Reloading Whisper model...")
            self.local_model = create_local_model()
            ConfigManager.console_print("Model reloaded successfully.")
        except Exception as e:
            logger.exception("Error reloading Whisper model")
            self._show_global_error(
                title="Model Error",
                message=f"Failed to reload Whisper model: {e}",
                details="The previous model will continue to be used.",
            )


    @pyqtSlot()
    def on_activation(self) -> None:
        """Called when activation key is pressed."""
        try:
            recording_mode = ConfigManager.get_config_value(
                "recording_options", "recording_mode"
            )

            if self.result_thread and self.result_thread.isRunning():
                # Already recording - stop it
                if recording_mode == "press_to_toggle":
                    self.result_thread.stop_recording()
                return

            # Start new recording
            self.start_result_thread()
        except Exception as e:
            logger.exception("Error in on_activation")
            self._show_global_error(
                title="Recording Error",
                message=f"Failed to start recording: {e}",
                details="",
            )

    @pyqtSlot()
    def on_deactivation(self) -> None:
        """Called when activation key is released (for hold_to_record mode)."""
        try:
            recording_mode = ConfigManager.get_config_value(
                "recording_options", "recording_mode"
            )

            if (
                recording_mode == "hold_to_record"
                and self.result_thread
                and self.result_thread.isRunning()
            ):
                self.result_thread.stop_recording()
        except Exception:
            logger.exception("Error in on_deactivation")
            # Don't show dialog for deactivation errors - just log

    @pyqtSlot()
    def start_result_thread(self) -> None:
        """Start recording/transcription thread with unified signal."""
        try:
            if self.result_thread and self.result_thread.isRunning():
                return

            self.result_thread = ResultThread(self.local_model)

            # Single unified signal connection - no manual tracking needed
            self.result_thread.resultReady.connect(self._handle_thread_result)

            # Connect audio level updates to workspace waveform visualization
            self.result_thread.audioLevelUpdated.connect(
                self.main_window.update_audio_level
            )

            # Auto-cleanup: when thread finishes, schedule deletion
            self.result_thread.finished.connect(self._on_thread_finished)
            self.result_thread.start()
        except Exception as e:
            logger.exception("Error starting result thread")
            self._show_global_error(
                title="Recording Error",
                message=f"Failed to start recording: {e}",
                details="",
            )

    @pyqtSlot()
    def _on_thread_finished(self) -> None:
        """Handle thread completion: schedule deletion."""
        try:
            if self.result_thread:
                self.result_thread.deleteLater()
                self.result_thread = None
        except Exception:
            logger.exception("Error in _on_thread_finished")

    def stop_result_thread(self) -> None:
        """Stop the recording/transcription thread."""
        try:
            if self.result_thread and self.result_thread.isRunning():
                self.result_thread.stop()
        except Exception:
            logger.exception("Error stopping result thread")

    @pyqtSlot()
    def _cancel_recording(self) -> None:
        """Cancel recording early without transcribing."""
        try:
            if self.result_thread and self.result_thread.isRunning():
                self.result_thread.stop()
        except Exception:
            logger.exception("Error cancelling recording")

    @pyqtSlot()
    def _stop_recording_from_ui(self) -> None:
        """Stop recording when user clicks Stop button in workspace."""
        try:
            if self.result_thread and self.result_thread.isRunning():
                self.result_thread.stop_recording()
        except Exception:
            logger.exception("Error stopping recording from UI")

    def _handle_thread_result(self, result) -> None:
        """
        Handle thread result signals based on state.

        Args:
            result: ThreadResult containing state, text, duration, and error info
        """
        try:
            from result_thread import ThreadState

            match result.state:
                case ThreadState.RECORDING:
                    self.main_window.sync_recording_status_from_engine("recording")
                    self.update_tray_status("recording")
                case ThreadState.TRANSCRIBING:
                    self.main_window.sync_recording_status_from_engine("transcribing")
                    self.update_tray_status("transcribing")
                case ThreadState.COMPLETE:
                    self.main_window.sync_recording_status_from_engine("idle")
                    self.update_tray_status("idle")
                    self._on_transcription_complete(
                        result.text, result.duration_ms, result.speech_duration_ms
                    )
                case ThreadState.ERROR:
                    self.main_window.sync_recording_status_from_engine("idle")
                    self.update_tray_status("error")
                    if result.error_message:
                        self._on_recording_error(result.error_message)
                case ThreadState.IDLE:
                    self.main_window.sync_recording_status_from_engine("idle")
                    self.update_tray_status("idle")
        except Exception as e:
            logger.exception("Error handling thread result")
            self._show_global_error(
                title="Processing Error",
                message=f"Failed to process transcription result: {e}",
                details="",
            )

    def update_tray_status(self, status: str) -> None:
        """Update tray icon tooltip based on current status."""
        if _TRAY_DBUS_ERROR_SEEN and hasattr(self, "tray_manager"):
            if self.tray_manager.tray_icon:
                self.tray_manager.tray_icon.hide()
                # We don't want to constantly re-hide, but this attribute access is checked
                self.tray_manager.tray_icon = None
            return

        if not hasattr(self, "tray_manager"):
            return

        is_recording = status == "recording"
        is_transcribing = status == "transcribing"
        self.tray_manager.update_status(is_recording, is_transcribing)

    def _on_transcription_complete(
        self, result: str, duration_ms: int, speech_duration_ms: int
    ) -> None:
        """Handle completed transcription: add to history and copy to clipboard."""
        try:
            if not result:
                return

            # Add to history and display using the persisted entry to keep timestamps aligned
            entry = self.history_manager.add_entry(
                result, duration_ms=duration_ms, speech_duration_ms=speech_duration_ms
            )
            self.main_window.display_transcription(entry)

            # Always copy to clipboard for manual paste
            copy_text(result)
        except Exception as e:
            logger.exception("Error handling transcription complete")
            self._show_global_error(
                title="Save Error",
                message=f"Failed to save transcription: {e}",
                details="The transcription was completed but could not be saved.",
            )

    def on_reinject_requested(self, text: str) -> None:
        """
        Handle re-copy from history.

        Copies text to clipboard for manual paste.
        Does NOT add to history again.
        """
        try:
            logger.info(f"Re-copying from history: {text[:50]}...")
            copy_text(text)
        except Exception:
            logger.exception("Error re-copying text")

    def on_edit_entry_requested(self, text: str, timestamp: str) -> None:
        """
        Handle edit entry request from history.

        Loads entry into the transcription editor.

        Args:
            text: The transcription text
            timestamp: ISO timestamp of the entry
        """
        try:
            logger.info(f"Loading entry for edit: {timestamp}")
            self.main_window.load_entry_for_edit(text, timestamp)
        except Exception as e:
            logger.exception("Error loading entry for edit")
            self._show_global_error(
                title="Load Error",
                message=f"Failed to load entry for editing: {e}",
                details="",
            )

    @pyqtSlot(str, str, str)
    def _on_refine_requested(self, profile: str, text: str, timestamp: str) -> None:
        """Handle refinement request with profile.

        Args:
            profile: The refinement profile to use
            text: The text content to refine
            timestamp: The timestamp of the transcript
        """
        try:
            if not text or not timestamp:
                logger.warning("Refine requested but no content loaded")
                return

            transcript_id = self.history_manager.get_id_by_timestamp(timestamp)
            if transcript_id is None:
                logger.error(f"Could not find transcript ID for timestamp {timestamp}")
                self._show_global_error(
                    "Refinement Error",
                    "Could not associate text with a database record.",
                    "",
                )
                return

            if not ConfigManager.get_config_value("refinement", "enabled"):
                self._show_global_error(
                    "Feature Disabled", "Refinement is disabled in settings.", ""
                )
                return

            ConfigManager.console_print(f"Refining transcript (Profile: {profile})...")
            self.requestRefinement.emit(transcript_id, text, profile)
        except Exception:
            logger.exception("Error handling refine request")

    @pyqtSlot(int, str)
    def _on_refinement_success(self, transcript_id: int, text: str) -> None:
        """Handle successful refinement."""
        try:
            logger.info(f"Refinement successful for ID {transcript_id}")
            # Add variant to DB
            success = self.history_manager.add_variant_atomic(
                transcript_id, text, "refined", SLMService.SOURCE_REPO_ID
            )

            if not success:
                logger.error("Failed to save refined variant to DB")
                return

            ConfigManager.console_print("Refinement complete and saved.")

            # Update UI if still viewing this transcript
            # We need to know the timestamp to check if it's the current one.
            # Ideally we would pass it through requestRefinement -> SLM -> success signal,
            # but for now we look it up from ID.
            entry = self.history_manager.get_entry(transcript_id)
            if entry:
                # variants = self.history_manager.get_transcript_variants(transcript_id) # not needed for simple diff yet
                
                # Switch view and load
                self.main_window.show_refinement(transcript_id, entry.text, text)


        except Exception:
            logger.exception("Error in refinement success handler")

    @pyqtSlot(int, str)
    def _on_refinement_error(self, transcript_id: int, message: str) -> None:
        """Handle refinement error."""
        logger.error(f"Refinement failed for {transcript_id}: {message}")
        ConfigManager.console_print(f"Refinement Failed: {message}")
        self._show_global_error("Refinement Failed", message, "")

        self._show_global_error("Refinement Failed", message, "")

    def _on_recording_error(self, error_message: str) -> None:
        """Handle recording errors with user-friendly feedback.

        Args:
            error_message: Description of the error
        """
        try:
            logger.error(f"Recording error: {error_message}")

            # Show error dialog to user
            show_error_dialog(
                title="Recording Error",
                message=f"Unable to record audio.\n\n{error_message}",
                parent=self.main_window,
            )

            # Reset UI state
            self.main_window.sync_recording_status_from_engine("idle")
            self.update_tray_status("idle")
        except Exception:
            logger.exception("Error showing recording error dialog")

    def cleanup(self) -> None:
        """Clean up resources."""
        try:
            # Stop and clean up result thread
            if self.result_thread and self.result_thread.isRunning():
                self.result_thread.stop()
                self.result_thread.wait(2000)  # Wait up to 2 seconds for graceful stop

            if self.key_listener:
                self.key_listener.stop()

            # Release lock file
            if hasattr(self, "lock"):
                self.lock.unlock()

            logger.info("Vociferous cleanup completed")
        except Exception:
            logger.exception("Error during cleanup")

    def exit_app(self) -> None:
        """Exit the application."""
        try:
            self.cleanup()
            QApplication.quit()
        except Exception:
            logger.exception("Error exiting application")
            QApplication.quit()

    def run(self) -> int:
        """Run the application."""
        try:
            return self.app.exec()
        except Exception:
            logger.exception("Error in application main loop")
            return 1


if __name__ == "__main__":
    app = VociferousApp()
    sys.exit(app.run())
