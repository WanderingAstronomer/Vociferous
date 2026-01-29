"""
Application Coordinator - composition root for the application.

Owns the lifecycle of:
1. Core Services (Config, History, State)
2. Hardware Interfaces (KeyListener, Microphone/Audio)
3. UI Components (MainWindow, SystemTray)
4. AI Subsystems (Whisper, SLM)

This moves wiring logic out of main.py and MainWindow.
"""

import logging

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QApplication

# Core
from src.core.config_manager import ConfigManager
from src.core.state_manager import StateManager
from src.core.exceptions import DatabaseError
from src.database.history_manager import HistoryManager
from src.core.command_bus import CommandBus

# Infrastructure
from src.input_handler.listener import KeyListener
from src.ui.utils.error_handler import get_error_logger

# Domain Services
# from src.services.transcription_runtime import TranscriptionRuntime, ThreadResult, ThreadState
# Replacing TranscriptionRuntime with direct EngineClient usage
from src.core_runtime.client import EngineClient
from src.core_runtime.types import EngineState, TranscriptionResult
from src.services.slm_service import SLMService  # Legacy service for now
# from src.services.transcription_service import create_local_model

# Intents
from src.ui.interaction.intents import (
    InteractionIntent,
    BeginRecordingIntent,
    StopRecordingIntent,
    ToggleRecordingIntent,
    IntentSource,
)

# UI
from src.ui.components.main_window.main_window import MainWindow
from src.ui.styles.unified_stylesheet import get_unified_stylesheet
from src.ui.components.main_window.system_tray import SystemTrayManager

logger = logging.getLogger(__name__)


class EngineSignals(QObject):
    """Bridge for signals from background engine threads to Qt main loop."""

    resultReady = pyqtSignal(TranscriptionResult)
    statusUpdate = pyqtSignal(str)
    audioLevel = pyqtSignal(float)
    audioSpectrum = pyqtSignal(list)


class ApplicationCoordinator(QObject):
    """
    Orchestrates the application lifecycle and wires dependencies.
    """

    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app

        # Core Services
        self.history_manager: HistoryManager | None = None
        self.state_manager: StateManager | None = None
        self.config_manager: ConfigManager | None = None

        # Messaging
        self.command_bus = CommandBus()
        self._hotkey_dispatcher = None

        # Hardware
        self.key_listener: KeyListener | None = None
        self.local_model = None  # Whisper model
        # Process-Based Engine Client
        self.engine_client: EngineClient | None = None

        # Shutdown Guard
        self._is_shutting_down = False
        self.engine_signals = EngineSignals()

        # AI Services
        self.slm_service: SLMService | None = None
        self.slm_thread: QThread | None = None

        # UI
        self.main_window: MainWindow | None = None
        self.tray_manager: SystemTrayManager | None = None

        # Internal State
        self._hotkey_dispatcher = None

    def start(self):
        """Initialize and start all components."""
        logger.info("Coordinator: Starting application...")

        # 1. Config & Logging
        ConfigManager.initialize()
        get_error_logger()

        # Apply Global Stylesheet
        self.app.setStyleSheet(get_unified_stylesheet())

        # 2. Wire Hotkeys (requires QObject thread affinity trick)
        self._setup_hotkey_dispatcher()

        # 3. Core Data Services
        # Initialize core services with graceful handling of DB init failures
        if not self._init_core_services():
            # If init failed, return early. The retry logic is handled by the dialog callback.
            return

        # 4. Hardware
        # Model loading is now deferred to the Engine Process (Headless)
        # We initialize the Client here, but connection (process spawn) is lazy or explicit.
        self.engine_client = EngineClient(
            on_result=self.engine_signals.resultReady.emit,
            on_status=self.engine_signals.statusUpdate.emit,
            on_audio_level=self.engine_signals.audioLevel.emit,
            on_audio_spectrum=self.engine_signals.audioSpectrum.emit,
        )
        self.engine_client.connect()  # Spawn process now to be ready

        # Wire Engine Signals
        self.engine_signals.resultReady.connect(self._handle_transcription_result)
        self.engine_signals.statusUpdate.connect(self._handle_engine_status)

        self.key_listener = KeyListener()

        # Wire KeyListener to CommandBus via HotkeyDispatcher
        # Note: wiring happens in _setup_hotkey_dispatcher

        self.key_listener.add_callback(
            "on_activate", lambda: self._hotkey_dispatcher.activated.emit()
        )
        self.key_listener.add_callback(
            "on_deactivate", lambda: self._hotkey_dispatcher.deactivated.emit()
        )

        # 5. UI Initialization
        self.main_window = MainWindow(
            self.history_manager, self.key_listener, command_bus=self.command_bus
        )

        # Set application-wide window icon (for taskbar/dock representation)
        # and main window icon (for system tray compatibility)
        app_icon = SystemTrayManager.build_icon(self.app)
        self.app.setWindowIcon(app_icon)
        self.main_window.setWindowIcon(app_icon)

        # Restore State
        if saved_motd := self.state_manager.get("motd"):
            self.main_window.set_motd(saved_motd)
            self.state_manager.set("motd", None)

        # 6. Legacy SLM Service Wiring
        self._setup_slm_service()

        # 7. Wire UI Signals -> Logic
        self._wire_main_window_signals()

        # 8. System Tray
        self.tray_manager = SystemTrayManager(self.app, self.main_window, self.exit_app)
        self.main_window.window_close_requested.connect(self.exit_app)

        # 9. Config Listeners
        ConfigManager.instance().config_changed.connect(self._on_config_changed)

        # 10. Check Onboarding Status
        onboarding_completed = ConfigManager.get_config_value(
            "user", "onboarding_completed"
        )
        logger.info(
            f"Onboarding status check: onboarding_completed={onboarding_completed} (type: {type(onboarding_completed).__name__})"
        )
        if not onboarding_completed:
            # Launch onboarding wizard if not completed
            logger.info("Onboarding not completed, launching wizard...")
            if not self.main_window.launch_onboarding():
                # Onboarding was cancelled, exit gracefully
                logger.info("Onboarding cancelled by user, exiting...")
                self.shutdown()
                return

        # 11. Start Interaction
        self.key_listener.start()
        self._update_activation_key()

        # Show Window (if configured, or start hidden)
        self.main_window.show()

    def cleanup(self):
        """Graceful shutdown — idempotent cleanup path."""
        if self._is_shutting_down:
            return
        self._is_shutting_down = True

        logger.info("Coordinator: Shutting down...")

        # Stop input handlers first to prevent new recordings
        if self.key_listener:
            self.key_listener.stop()

        # Shutdown engine client (stops recovery attempts and terminates subprocess)
        if self.engine_client:
            self.engine_client.shutdown()

        # Stop background services
        if self.slm_thread:
            self.slm_thread.quit()
            self.slm_thread.wait(5000)  # 5 second timeout

        # Close UI last
        if self.main_window:
            self.main_window.close()

        logger.info("Coordinator: Shutdown complete")

    def shutdown(self):
        """Public shutdown entrypoint — triggers cleanup and Qt exit."""
        self.cleanup()
        self.app.quit()

    def exit_app(self):
        """Exit the application (alias for shutdown)."""
        self.shutdown()

    # --- Internal Wiring ---

    def _setup_hotkey_dispatcher(self):
        """Create the bridge between KeyListener thread and Qt Main thread."""

        class _HotkeyDispatcher(QObject):
            activated = pyqtSignal()
            deactivated = pyqtSignal()

        self._hotkey_dispatcher = _HotkeyDispatcher()
        self._hotkey_dispatcher.activated.connect(self.on_activation)
        self._hotkey_dispatcher.deactivated.connect(self.on_deactivation)

    def _setup_slm_service(self):
        """Wire the legacy SLM service."""
        # Initialize SLM Service (Refinement Backend)
        self.slm_thread = QThread()
        self.slm_service = SLMService()
        self.slm_service.moveToThread(self.slm_thread)

        # We need to bridge signals.
        # Note: VociferousApp had signals requestRefinement etc.
        # We need to either expose them or wire main_window directly to slm_service?
        # Ideally, main_window emits intents, and we route them.
        # For this refactor, let's wire directly where possible to avoid changing MainWindow too much yet.

        # But wait, MainWindow emits 'refinement_requested'.
        self.main_window.refinement_requested.connect(
            self.slm_service.handle_refinement_request
        )

        # Responses
        self.slm_service.refinementSuccess.connect(self._on_refinement_success)
        self.slm_service.refinementError.connect(self._on_refinement_error)
        self.slm_service.motdReady.connect(self._on_motd_ready)
        self.slm_service.serviceBusy.connect(self.main_window.set_app_busy)

        # Wire State Changes to MainWindow (for Settings UI feedback)
        self.slm_service.stateChanged.connect(self.main_window.update_refinement_state)
        # We can also wire statusMessage if needed, but stateChanged might carry enough context or we mix both?
        # SLMService emits statusMessage separately.
        self.slm_service.statusMessage.connect(
            self.main_window.on_refinement_status_message
        )

        # GPU confirm is tricky, it accesses self.main_window as parent.
        # We can implement that handler here in Coordinator.
        self.slm_service.askGPUConfirmation.connect(self._on_gpu_confirmation_requested)

        # Wire heartbeat pause/resume for long-running operations (model provisioning)
        self.slm_service.requestHeartbeatPause.connect(
            lambda: self.engine_client.pause_heartbeat() if self.engine_client else None
        )
        self.slm_service.requestHeartbeatResume.connect(
            lambda: self.engine_client.resume_heartbeat()
            if self.engine_client
            else None
        )

        self.slm_thread.start()

        # Enable SLM if configured
        if ConfigManager.get_config_value("refinement", "enabled"):
            QTimer.singleShot(0, self.slm_service.initialize_service)

        # MOTD Logic - generate on startup after a short delay
        QTimer.singleShot(5000, lambda: self.slm_service.generate_motd())

    def _wire_main_window_signals(self):
        # Intent Bus - subscribe to the CommandBus instead of the Window
        self.command_bus.intent_dispatched.connect(self._on_intent)

        # Legacy / Special Signals
        self.main_window.motd_refresh_requested.connect(self._handle_motd_refresh)

        # Audio visualization
        if self.engine_signals:
            self.engine_signals.audioLevel.connect(self.main_window.update_audio_level)
            self.engine_signals.audioSpectrum.connect(
                self.main_window.update_audio_spectrum
            )

    @pyqtSlot(object)
    def _on_intent(self, intent: InteractionIntent):
        """Route intents to execution logic."""
        # Lazily import intents to avoid circular issues if any
        from src.ui.interaction.intents import (
            BeginRecordingIntent,
            StopRecordingIntent,
            CancelRecordingIntent,
            ToggleRecordingIntent,
        )

        if isinstance(intent, BeginRecordingIntent):
            self.start_result_thread()
        elif isinstance(intent, StopRecordingIntent):
            self._stop_recording_from_ui()
        elif isinstance(intent, CancelRecordingIntent):
            self._cancel_recording()
        elif isinstance(intent, ToggleRecordingIntent):
            self._handle_toggle_recording()

    def _handle_toggle_recording(self):
        """Toggle recording state."""
        # Check against EngineClient state?
        # But Client.start_session() sends START message.
        # We need to track logical state here if client is async.
        # For now, simplistic: if recording, stop.
        if (
            self.main_window and self.main_window.is_recording()
        ):  # Assuming MW tracks it visually
            self._stop_recording_from_ui()
        else:
            self.start_result_thread()

    def _handle_motd_refresh(self):
        """
        Handle persistent MOTD refresh.
        1. Consume cached MOTD immediately.
        2. Request generation of a new one for next time.
        """
        if self.state_manager and (chamber_motd := self.state_manager.get("motd")):
            logger.info("Consuming cached MOTD from chamber.")
            if self.main_window:
                self.main_window.set_motd(chamber_motd)
            self.state_manager.set("motd", None)
        else:
            logger.info("No cached MOTD available.")
            # Optional: self.main_window.set_motd("Fetching fresh wisdom...")

        # Trigger generation for the NEXT refresh (refills the chamber)
        if ConfigManager.get_config_value("refinement", "enabled") and self.slm_service:
            # We trigger generation. It typically is async.
            # SLMService.generate_motd emits motdReady when done.
            # We need to ensure we don't just overwrite the one we just showed?
            # motdReady connects to _on_motd_ready which sets state_manager for NEXT time.
            # Except if we currently are showing nothing, maybe we want to show it now?
            # Original logic: save for NEXT run.
            self.slm_service.generate_motd()

    # --- Event Handlers (Moved from VociferousApp / main.py) ---

    def on_activation(self):
        """Handle hotkey activation."""
        if not self.main_window:
            return

        mode = ConfigManager.get_config_value("recording_options", "recording_mode")
        if mode == "push_to_talk":
            self.main_window.dispatch_intent(
                BeginRecordingIntent(source=IntentSource.HOTKEY)
            )
        else:
            self.main_window.dispatch_intent(
                ToggleRecordingIntent(source=IntentSource.HOTKEY)
            )

    def on_deactivation(self):
        """Handle hotkey deactivation."""
        mode = ConfigManager.get_config_value("recording_options", "recording_mode")
        if mode == "push_to_talk":
            if self.main_window:
                self.main_window.dispatch_intent(
                    StopRecordingIntent(source=IntentSource.HOTKEY)
                )

    def start_result_thread(self):
        """Start recording/transcription."""
        if not self.engine_client:
            return

        logger.info("Starting recording...")
        self.main_window.set_recording_state(True)

        # Use persistent Engine Client
        # Ensure connected
        if not self.engine_client.process:  # Simple check
            self.engine_client.connect()

        self.engine_client.start_session()

    def _stop_recording_from_ui(self):
        """Stop recording (finish and transcribe)."""
        if self.engine_client:
            logger.info("Stopping recording (finishing)...")
            self.engine_client.stop_session()

    def _cancel_recording(self):
        """Cancel recording without transcribing."""
        if self.engine_client:
            logger.info("Cancelling recording...")
            self.engine_client.stop_session()
        self.main_window.set_app_busy(False)
        self.main_window.set_recording_state(False)

    @pyqtSlot(TranscriptionResult)
    def _handle_transcription_result(self, result: TranscriptionResult):
        """Handle unified updates from the transcription engine."""
        if result.state == EngineState.RECORDING:
            logger.info("Engine: Recording started")
            # Clear any "Loading Model" overlay
            self.main_window.set_app_busy(False)
            self.main_window.sync_recording_status_from_engine("recording")
        elif result.state == EngineState.TRANSCRIBING:
            logger.info("Engine: Transcribing...")
            self.main_window.sync_recording_status_from_engine("transcribing")
        elif result.state == EngineState.COMPLETE:
            logger.info(f"Transcription finished: {len(result.text)} chars")

            # Filter empty transcripts
            if not result.text.strip():
                logger.info("Ignoring empty transcript")
                self.main_window.sync_recording_status_from_engine("idle")
                return

            # Save to history (use helper to allow retry)
            if self.history_manager:
                self._save_transcript(
                    result.text, result.duration_ms, result.speech_duration_ms
                )


            # Sync engine status last to avoid premature state transition
            self.main_window.sync_recording_status_from_engine("idle")

            from src.ui.utils.clipboard_utils import copy_text

            copy_text(result.text)

        elif result.state == EngineState.ERROR:
            logger.error(f"Transcription error: {result.error_message}")
            self.main_window.set_app_busy(False)
            self.main_window.sync_recording_status_from_engine("error")

    @pyqtSlot(str)
    def _handle_engine_status(self, status: str):
        """Handle engine status updates."""
        if status == "loading_model":
            logger.info("ASR Model loading detected. Showing overlay.")
            self.main_window.set_app_busy(
                True, "Initializing ASR Engine...", title="Model Loading"
            )
        else:
            logger.info(f"Engine status: {status}")
            if self.main_window:
                self.main_window.sync_recording_status_from_engine(status)

    def _on_refinement_success(self, transcript_id: int, refined_text: str):
        logger.info(f"Refinement successful for ID {transcript_id}")
        self.main_window.set_app_busy(False)
        self.main_window.on_refinement_complete(transcript_id, refined_text)

    def _on_refinement_error(self, transcript_id: int, error: str):
        logger.error(f"Refinement error for ID {transcript_id}: {error}")
        self.main_window.set_app_busy(False)
        # TODO: Show error in RefineView?
        from src.ui.components.error_dialog import show_error_dialog

        show_error_dialog("Refinement Failed", error, self.main_window)

    def _init_core_services(self) -> bool:
        """Initialize History and State managers. Returns True on success, False on failure.

        On failure, show a retry dialog that re-invokes this method.
        """
        try:
            self.history_manager = HistoryManager()
            self.state_manager = StateManager()
            return True
        except Exception as e:
            # Wrap any initialization failure as DatabaseError for user-facing messaging
            from src.core.exceptions import DatabaseError
            from src.ui.widgets.dialogs.error_dialog import show_error_dialog

            db_err = DatabaseError(f"Failed to initialize history database: {e}")

            # Show a modal dialog with a Retry callback that attempts to initialize again
            show_error_dialog(
                title="Failed to Initialize History DB",
                message=(
                    "Vociferous could not initialize the history database. "
                    "You can retry initialization or exit the application."
                ),
                details=str(db_err),
                parent=None,
                retry_callback=self._init_core_services,
            )
            return False

    def _save_transcript(self, text: str, duration_ms: int, speech_duration_ms: int) -> None:
        """Attempt to save transcript to history. On DatabaseError, show dialog with retry."""
        try:
            entry = self.history_manager.add_entry(text, duration_ms, speech_duration_ms)
            # Ensure the UI refreshes metrics and updates list immediately
            self.main_window.on_transcription_complete(entry)
        except DatabaseError as e:
            logger.error(f"Failed to save transcript: {e}")
            from src.ui.widgets.dialogs.error_dialog import show_error_dialog

            # Provide a retry callback that re-invokes this method with the same payload
            show_error_dialog(
                title="Failed to Save Transcript",
                message=(
                    "The transcription was successful, but it could not be saved to history.\n\n"
                    "Your transcript has been copied to the clipboard, but it will not appear in your history."
                ),
                details=str(e),
                parent=self.main_window,
                retry_callback=lambda: self._save_transcript(
                    text, duration_ms, speech_duration_ms
                ),
            )

    def _on_motd_ready(self, message: str):
        if self.main_window:
            self.main_window.set_motd(message)
        if self.state_manager:
            self.state_manager.set("motd", message)

    def _on_config_changed(self, section: str, key: str, value: object):
        if section == "recording_options" and key == "activation_key":
            self._update_activation_key()
        elif section == "model_options" and self.engine_client:
            # Sync to headless engine process
            self.engine_client.update_config(section, key, value)
        elif section == "refinement" and key == "model_id" and self.slm_service:
            # Trigger model switch
            # Value comes as generic object, ensure string
            if isinstance(value, str):
                logger.info(
                    f"Config change detected: Switching refinement model to {value}"
                )
                # Use QMetaObject.invokeMethod to ensure thread safety
                from PyQt6.QtCore import QMetaObject, Q_ARG, Qt

                QMetaObject.invokeMethod(
                    self.slm_service,
                    "change_model",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, value),
                )

    def _update_activation_key(self):
        if self.key_listener:
            self.key_listener.update_activation_keys()

    def _on_gpu_confirmation_requested(self, free, total, needed):
        # Replicate logic from main.py using ConfirmationDialog
        # Needs to import relevant UI
        from src.ui.widgets.dialogs import ConfirmationDialog

        # Calculate percentages
        remaining_mb = free - needed
        headroom_pct = (remaining_mb / total) * 100

        message = (
            f"<b>Limited VRAM Detected</b><br><br>"
            f"Vociferous wants to load the refinement model into GPU memory for speed.<br>"
            f"<ul>"
            f"<li>Total VRAM: {total} MB</li>"
            f"<li>Available: {free} MB</li>"
            f"<li>Required: ~{needed} MB</li>"
            f"<li><b>Projected Headroom: {headroom_pct:.1f}%</b></li>"
            f"</ul>"
            f"Loading to GPU with &lt;20% headroom might cause system instability or crash other applications.<br><br>"
            f"Do you want to proceed with GPU loading?"
        )

        dialog = ConfirmationDialog(
            parent=self.main_window,
            title="GPU Configuration Warning",
            message=message,
            confirm_text="Yes, Use GPU",
            cancel_text="No, Use CPU",
            is_destructive=True,
        )

        # Dialog.exec() returns 1 for Accepted (Yes), 0 for Rejected (No)
        # If dialog is closed without clicking, it returns 0 (Rejected)
        result = dialog.exec()
        use_gpu = result == 1
        
        if self.slm_service:
            self.slm_service.submit_gpu_choice(use_gpu)
