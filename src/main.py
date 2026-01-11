"""
Vociferous - Main orchestration module.

Coordinates KeyListener → ResultThread → clipboard output via Qt signals.
Tracks signal connections in _thread_connections for proper cleanup.
"""

import logging
import os
import sys
from pathlib import Path

from PyQt6.QtCore import QLockFile, QObject, pyqtSignal, pyqtSlot, qInstallMessageHandler
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

from history_manager import HistoryManager
from key_listener import KeyListener
from result_thread import ResultThread
from transcription import create_local_model
from ui.components.main_window import MainWindow
from ui.components.settings import SettingsDialog
from ui.utils.clipboard_utils import copy_text
from ui.utils.error_handler import get_error_logger, install_exception_hook
from ui.widgets.dialogs.custom_dialog import MessageDialog
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


class VociferousApp(QObject):
    """Main application orchestrator coordinating all components."""

    def __init__(self) -> None:
        # Initialize error logging FIRST (before anything else)
        error_logger = get_error_logger()
        
        # Install global exception hook with error dialog callback
        install_exception_hook(self._show_global_error)
        
        _install_qt_message_handler()
        # Check for existing instance BEFORE creating QApplication
        import tempfile

        lock_file = os.path.join(tempfile.gettempdir(), "vociferous.lock")
        self.lock = QLockFile(lock_file)
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
            parent = getattr(self, 'main_window', None)
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
            ConfigManager.console_print("Loading Whisper model (this may take a moment)...")
            self.local_model = create_local_model()

            # Result thread (for recording/transcription)
            self.result_thread: ResultThread | None = None

            # History manager for transcription storage
            self.history_manager = HistoryManager()

            # Main window (shows recording/transcribing state)
            self.main_window = MainWindow(self.history_manager)
            self.main_window.setWindowIcon(self._build_tray_icon())
            self.main_window.on_settings_requested(self.show_settings)

            # Connect history widget selection to load into editor
            self.main_window.history_widget.entrySelected.connect(
                self.on_edit_entry_requested
            )

            # Cancel recording without transcribing
            self.main_window.cancelRecordingRequested.connect(self._cancel_recording)

            # Connect workspace start/stop signals
            self.main_window.startRecordingRequested.connect(self.start_result_thread)
            self.main_window.stopRecordingRequested.connect(self._stop_recording_from_ui)

            # System tray
            self.create_tray_icon()
            self.main_window.windowCloseRequested.connect(self.exit_app)

            # React to configuration changes
            ConfigManager.instance().configChanged.connect(self._on_config_changed)

            # Start listening for hotkey
            self.key_listener.start()

            activation_key = ConfigManager.get_config_value(
                "recording_options", "activation_key"
            )
            ConfigManager.console_print(f"Ready! Press '{activation_key}' to start.")
            
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

    def _tray_available(self) -> bool:
        """Return True if a functional system tray is available."""
        if sys.platform.startswith("linux"):
            if not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
                logger.warning("D-Bus session bus missing; skipping tray icon.")
                return False
            try:
                from PyQt6.QtDBus import QDBusConnection
            except Exception as exc:
                logger.warning(f"QtDBus unavailable; skipping tray icon: {exc}")
                return False

            bus = QDBusConnection.sessionBus()
            if not bus.isConnected():
                logger.warning("D-Bus session bus not connected; skipping tray icon.")
                return False

            interface = bus.interface()
            if not (
                interface
                and interface.isServiceRegistered("org.kde.StatusNotifierWatcher")
            ):
                logger.warning("No StatusNotifierWatcher; skipping tray icon.")
                return False

            return True

        return QSystemTrayIcon.isSystemTrayAvailable()

    def create_tray_icon(self) -> None:
        """Create system tray icon with context menu."""
        if not self._tray_available():
            self.tray_icon = None
            self.main_window.show_and_raise()
            return

        try:
            icon = self._build_tray_icon()
            self.tray_icon = QSystemTrayIcon(icon, self.app)

            tray_menu = QMenu()

            # Status indicator (non-clickable)
            status_action = QAction("Vociferous - Ready", self.app)
            status_action.setEnabled(False)
            tray_menu.addAction(status_action)
            self.status_action = status_action

            tray_menu.addSeparator()

            show_hide_action = QAction("Show/Hide Window", self.app)
            show_hide_action.triggered.connect(self.toggle_main_window)
            tray_menu.addAction(show_hide_action)
            self.show_hide_action = show_hide_action

            settings_action = QAction("Settings...", self.app)
            settings_action.setEnabled(True)
            settings_action.triggered.connect(self.show_settings)
            tray_menu.addAction(settings_action)
            self.settings_action = settings_action

            tray_menu.addSeparator()

            # Exit action
            exit_action = QAction("Exit", self.app)
            exit_action.triggered.connect(self.exit_app)
            tray_menu.addAction(exit_action)

            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.setToolTip("Vociferous - Speech to Text")
            self.tray_icon.activated.connect(self.on_tray_activated)
            self.tray_icon.show()
            if _TRAY_DBUS_ERROR_SEEN:
                logger.warning("Disabling tray icon after D-Bus error.")
                self.tray_icon.hide()
                self.tray_icon = None
        except Exception as e:
            # D-Bus errors are common on some desktop environments
            # Tray icon is optional, so just log and continue
            logger.warning(f"System tray initialization failed (non-fatal): {e}")
            self.tray_icon = None

        # Start with window shown on first launch
        self.main_window.show_and_raise()

    def toggle_main_window(self) -> None:
        """Toggle window between minimized and visible."""
        if self.main_window.isMinimized():
            self.main_window.show_and_raise()
        else:
            self.main_window.showMinimized()

    def on_tray_activated(self, reason):
        """Handle tray icon activation (double-click to toggle window)."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_main_window()

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
            if section == "model_options" and key in {"compute_type", "device", "language"}:
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

    def _build_tray_icon(self) -> QIcon:
        """Return a non-empty icon for the tray using bundled assets with fallbacks."""
        icons_dir = Path(__file__).resolve().parent.parent / "icons"
        candidates = [
            icons_dir / "512x512.png",
            icons_dir / "192x192.png",
            icons_dir / "favicon.ico",
        ]

        icon = QIcon()
        for candidate in candidates:
            if candidate.is_file():
                icon.addFile(str(candidate))

        if icon.isNull():
            icon = QIcon.fromTheme("microphone-sensitivity-high")

        if icon.isNull():
            app_instance = QApplication.instance()
            if app_instance and isinstance(app_instance, QApplication):
                style = app_instance.style()
                icon = (
                    style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
                    if style
                    else QIcon()
                )
            else:
                icon = QIcon()
        return icon

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
        except Exception as e:
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
                self.main_window.workspace.add_audio_level
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
        except Exception as e:
            logger.exception("Error in _on_thread_finished")

    def stop_result_thread(self) -> None:
        """Stop the recording/transcription thread."""
        try:
            if self.result_thread and self.result_thread.isRunning():
                self.result_thread.stop()
        except Exception as e:
            logger.exception("Error stopping result thread")

    @pyqtSlot()
    def _cancel_recording(self) -> None:
        """Cancel recording early without transcribing."""
        try:
            if self.result_thread and self.result_thread.isRunning():
                self.result_thread.stop()
        except Exception as e:
            logger.exception("Error cancelling recording")

    @pyqtSlot()
    def _stop_recording_from_ui(self) -> None:
        """Stop recording when user clicks Stop button in workspace."""
        try:
            if self.result_thread and self.result_thread.isRunning():
                self.result_thread.stop_recording()
        except Exception as e:
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
                    self._on_transcription_complete(result.text, result.duration_ms, result.speech_duration_ms)
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
        if _TRAY_DBUS_ERROR_SEEN and self.tray_icon:
            self.tray_icon.hide()
            self.tray_icon = None
            return
        match status:
            case "recording":
                text = "Vociferous - Recording..."
            case "transcribing":
                text = "Vociferous - Transcribing..."
            case "error":
                text = "Vociferous - Error"
            case _:
                text = "Vociferous - Ready"

        # Update tray icon if it exists (may be None if D-Bus failed)
        if self.tray_icon:
            self.status_action.setText(text)
            self.tray_icon.setToolTip(text)

    def _on_transcription_complete(self, result: str, duration_ms: int, speech_duration_ms: int) -> None:
        """Handle completed transcription: add to history and copy to clipboard."""
        try:
            if not result:
                return

            # Add to history and display using the persisted entry to keep timestamps aligned
            entry = self.history_manager.add_entry(result, duration_ms=duration_ms, speech_duration_ms=speech_duration_ms)
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
        except Exception as e:
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
        except Exception as e:
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
        except Exception as e:
            logger.exception("Error during cleanup")

    def exit_app(self) -> None:
        """Exit the application."""
        try:
            self.cleanup()
            QApplication.quit()
        except Exception as e:
            logger.exception("Error exiting application")
            QApplication.quit()

    def run(self) -> int:
        """Run the application."""
        try:
            return self.app.exec()
        except Exception as e:
            logger.exception("Error in application main loop")
            return 1


if __name__ == "__main__":
    app = VociferousApp()
    sys.exit(app.run())
