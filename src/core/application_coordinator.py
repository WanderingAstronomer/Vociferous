"""
Application Coordinator — Composition Root for Vociferous v4.0.

Plain Python class. No QObject. Owns lifecycle of all services.
Starts Litestar API server and pywebview window.
"""

import logging
import threading

from src.core.command_bus import CommandBus
from src.core.event_bus import EventBus
from src.core.settings import VociferousSettings

logger = logging.getLogger(__name__)


class ApplicationCoordinator:
    """
    Composition root for the Vociferous application.

    Owns and manages the lifecycle of:
    - Settings (already initialized before construction)
    - Database
    - CommandBus + EventBus
    - Transcription model (pywhispercpp)
    - SLM runtime (llama-cpp-python refinement)
    - Audio service
    - Input handler
    - Litestar API server
    - pywebview window
    """

    def __init__(self, settings: VociferousSettings) -> None:
        self.settings = settings
        self._shutdown_event = threading.Event()

        # Core buses
        self.command_bus = CommandBus()
        self.event_bus = EventBus()

        # Services (initialized in start())
        self.db = None
        self.audio_service = None
        self.input_listener = None
        self.slm_runtime = None
        self._asr_model = None  # pywhispercpp Model instance

        # Recording state
        self._is_recording = False
        self._recording_stop = threading.Event()

        # Window references
        self._main_window = None
        self._mini_window = None

        self._server_thread: threading.Thread | None = None

    def start(self) -> None:
        """
        Initialize all services and start the application.

        Order matters:
        1. Database
        2. ASR model (warm load)
        3. SLM runtime
        4. Audio service (with event callbacks)
        5. Input handler
        6. Register intent handlers
        7. Start API server (background thread)
        8. Open pywebview window (blocks until closed)
        """
        logger.info("Starting Vociferous v4.0...")

        # 1. Database
        from src.database.db import TranscriptDB

        self.db = TranscriptDB()
        logger.info("Database initialized (%d transcripts)", self.db.transcript_count())

        # 2. ASR model (optional warm load)
        self._load_asr_model()

        # 3. SLM runtime
        self._init_slm_runtime()

        # 4. Audio service with event callbacks
        self._init_audio_service()

        # 5. Input handler
        self._init_input_handler()

        # 6. Register intent handlers with CommandBus
        self._register_handlers()

        # 7. Start API server in background thread
        self._start_api_server()

        # 8. Check first-run / onboarding
        if not self.settings.user.onboarding_completed:
            self._check_onboarding()

        # 9. Open pywebview window (blocks main thread)
        self._open_window()

        logger.info("Vociferous shutdown complete.")

    def shutdown(self) -> None:
        """Signal all services to stop."""
        logger.info("Shutdown requested...")
        self._shutdown_event.set()
        self._recording_stop.set()

        try:
            import webview

            for window in webview.windows:
                window.destroy()
        except Exception:
            pass

    def cleanup(self) -> None:
        """Release resources after event loop exits."""
        if self.input_listener:
            try:
                self.input_listener.stop()
            except Exception:
                logger.exception("Input listener cleanup failed")

        if self.slm_runtime:
            try:
                self.slm_runtime.disable()
            except Exception:
                logger.exception("SLM runtime cleanup failed")

        if self._asr_model:
            try:
                del self._asr_model
                self._asr_model = None
            except Exception:
                logger.exception("ASR model cleanup failed")

        if self.db:
            try:
                self.db.close()
            except Exception:
                logger.exception("Database cleanup failed")

        self.event_bus.clear()
        logger.info("Cleanup complete.")

    # --- Service Initialization ---

    def _load_asr_model(self) -> None:
        """Warm-load the whisper.cpp model at startup."""
        try:
            from src.services.transcription_service import create_local_model

            self._asr_model = create_local_model()
            self.event_bus.emit("engine_status", {"asr": "ready"})
        except Exception:
            logger.exception(
                "ASR model failed to load (will retry on first transcription)"
            )
            self.event_bus.emit("engine_status", {"asr": "unavailable"})

    def _init_slm_runtime(self) -> None:
        """Initialize the SLM refinement runtime if enabled."""
        try:
            from src.services.slm_runtime import SLMRuntime

            def on_slm_state(state):
                self.event_bus.emit("engine_status", {"slm": state.value})

            def on_slm_error(msg):
                self.event_bus.emit("refinement_error", {"message": msg})

            def on_slm_text(text):
                # Text result from async refinement — handled per-request in _handle_refine_transcript
                pass

            self.slm_runtime = SLMRuntime(
                on_state_changed=on_slm_state,
                on_error=on_slm_error,
                on_text_ready=on_slm_text,
            )

            if self.settings.refinement.enabled:
                self.slm_runtime.enable()

        except Exception:
            logger.exception("SLM runtime failed to initialize (non-fatal)")

    def _init_audio_service(self) -> None:
        """Initialize the audio capture service with EventBus callbacks."""
        try:
            from src.services.audio_service import AudioService

            def on_level(level: float) -> None:
                self.event_bus.emit("audio_level", {"level": level})

            def on_spectrum(bands: list[float]) -> None:
                self.event_bus.emit("audio_spectrum", {"bands": bands})

            self.audio_service = AudioService(
                on_level_update=on_level,
                on_spectrum_update=on_spectrum,
            )
            logger.info("Audio service ready")
        except Exception:
            logger.exception("Audio service failed to initialize (non-fatal)")

    def _init_input_handler(self) -> None:
        """Initialize the global hotkey listener."""
        try:
            from src.input_handler import create_listener

            self.input_listener = create_listener(callback=self._on_hotkey)
            logger.info("Input handler ready")
        except Exception:
            logger.exception("Input handler failed to initialize (non-fatal)")

    # --- Intent Handlers ---

    def _register_handlers(self) -> None:
        """Register all intent handlers with the CommandBus."""
        from src.core.intents.definitions import (
            BeginRecordingIntent,
            StopRecordingIntent,
            CancelRecordingIntent,
            ToggleRecordingIntent,
            DeleteTranscriptIntent,
            CommitEditsIntent,
            RefineTranscriptIntent,
        )

        self.command_bus.register(BeginRecordingIntent, self._handle_begin_recording)
        self.command_bus.register(StopRecordingIntent, self._handle_stop_recording)
        self.command_bus.register(CancelRecordingIntent, self._handle_cancel_recording)
        self.command_bus.register(ToggleRecordingIntent, self._handle_toggle_recording)
        self.command_bus.register(
            DeleteTranscriptIntent, self._handle_delete_transcript
        )
        self.command_bus.register(CommitEditsIntent, self._handle_commit_edits)
        self.command_bus.register(
            RefineTranscriptIntent, self._handle_refine_transcript
        )

    def _handle_begin_recording(self, intent) -> None:
        if self._is_recording or not self.audio_service:
            return

        self._is_recording = True
        self._recording_stop.clear()
        self.event_bus.emit("recording_started", {})

        t = threading.Thread(target=self._recording_loop, daemon=True, name="recording")
        t.start()

    def _handle_stop_recording(self, intent) -> None:
        if not self._is_recording:
            return
        self._recording_stop.set()

    def _handle_cancel_recording(self, intent) -> None:
        if not self._is_recording:
            return
        self._recording_stop.set()
        # Mark as cancelled so _recording_loop doesn't transcribe
        self._is_recording = False
        self.event_bus.emit("recording_stopped", {"cancelled": True})

    def _handle_toggle_recording(self, intent) -> None:
        if self._is_recording:
            from src.core.intents.definitions import StopRecordingIntent

            self.command_bus.dispatch(StopRecordingIntent())
        else:
            from src.core.intents.definitions import BeginRecordingIntent

            self.command_bus.dispatch(BeginRecordingIntent())

    def _handle_delete_transcript(self, intent) -> None:
        if self.db:
            self.db.delete_transcript(intent.transcript_id)
            self.event_bus.emit("transcript_deleted", {"id": intent.transcript_id})

    def _handle_commit_edits(self, intent) -> None:
        if self.db:
            self.db.add_variant(
                intent.transcript_id, "user_edit", intent.content, set_current=True
            )

    def _handle_refine_transcript(self, intent) -> None:
        """Refine a transcript using the SLM runtime."""
        if not self.slm_runtime or not self.db:
            self.event_bus.emit("refinement_error", {"message": "SLM not available"})
            return

        transcript = self.db.get_transcript(intent.transcript_id)
        if not transcript:
            self.event_bus.emit("refinement_error", {"message": "Transcript not found"})
            return

        self.event_bus.emit(
            "refinement_started",
            {
                "transcript_id": intent.transcript_id,
                "level": intent.level,
            },
        )

        def do_refine():
            try:
                text = transcript.text or transcript.raw_text
                refined = self.slm_runtime.refine_text_sync(text, level=intent.level)

                # Store as variant
                self.db.add_variant(
                    intent.transcript_id,
                    f"refinement_L{intent.level}",
                    refined,
                    model_id=self.settings.refinement.model_id,
                    set_current=True,
                )

                self.event_bus.emit(
                    "refinement_complete",
                    {
                        "transcript_id": intent.transcript_id,
                        "text": refined,
                        "level": intent.level,
                    },
                )
            except Exception as e:
                logger.exception(
                    "Refinement failed for transcript %d", intent.transcript_id
                )
                self.event_bus.emit(
                    "refinement_error",
                    {
                        "transcript_id": intent.transcript_id,
                        "message": str(e),
                    },
                )

        t = threading.Thread(target=do_refine, daemon=True, name="refine")
        t.start()

    # --- Recording Pipeline ---

    def _recording_loop(self) -> None:
        """
        Background thread: record audio → transcribe → store → emit.

        Runs off the main thread. Uses EventBus for all progress reporting.
        """
        try:
            audio_data = self.audio_service.record_audio(
                should_stop=lambda: self._recording_stop.is_set()
            )

            # Check if cancelled during recording
            if not self._is_recording:
                return

            self._is_recording = False
            self.event_bus.emit("recording_stopped", {"cancelled": False})

            if audio_data is None or len(audio_data) == 0:
                self.event_bus.emit(
                    "transcription_error", {"message": "Recording too short or empty"}
                )
                return

            # Transcribe
            self._transcribe_and_store(audio_data)

        except Exception as e:
            logger.exception("Recording loop error")
            self._is_recording = False
            self.event_bus.emit("recording_stopped", {"cancelled": False})
            self.event_bus.emit("transcription_error", {"message": str(e)})

    def _transcribe_and_store(self, audio_data) -> None:
        """Run transcription on audio data, store result, and emit event."""
        from src.services.transcription_service import transcribe, create_local_model

        try:
            # Lazy-load ASR model if not already loaded
            if self._asr_model is None:
                self._asr_model = create_local_model()

            text, speech_duration_ms = transcribe(
                audio_data, local_model=self._asr_model
            )

            if not text.strip():
                self.event_bus.emit(
                    "transcription_error", {"message": "No speech detected"}
                )
                return

            # Store in database
            duration_ms = int(len(audio_data) / 16000 * 1000)
            transcript = None
            if self.db:
                transcript = self.db.add_transcript(
                    raw_text=text,
                    duration_ms=duration_ms,
                    speech_duration_ms=speech_duration_ms,
                    project_id=self.settings.user.active_project_id,
                )

            self.event_bus.emit(
                "transcription_complete",
                {
                    "text": text,
                    "id": transcript.id if transcript else None,
                    "duration_ms": duration_ms,
                    "speech_duration_ms": speech_duration_ms,
                },
            )

            logger.info(
                "Transcription complete: %d chars, %dms", len(text), duration_ms
            )

        except Exception as e:
            logger.exception("Transcription failed")
            self.event_bus.emit("transcription_error", {"message": str(e)})

    # --- Hotkey ---

    def _on_hotkey(self) -> None:
        """Callback from input handler when activation key is pressed."""
        from src.core.intents.definitions import ToggleRecordingIntent

        self.command_bus.dispatch(ToggleRecordingIntent())

    def _check_onboarding(self) -> None:
        """
        Check if required models are available for first-run users.

        Emits an onboarding event so the frontend can guide the user
        through model provisioning on first launch.
        """
        from src.core.model_registry import get_asr_model
        from src.core.resource_manager import ResourceManager

        asr = get_asr_model(self.settings.model.model)
        if asr is None:
            logger.info("Onboarding: no ASR model configured")
            self.event_bus.emit("onboarding_required", {"reason": "no_asr_model"})
            return

        model_path = ResourceManager.get_user_cache_dir("models") / asr.filename
        if not model_path.is_file():
            logger.info("Onboarding: ASR model not downloaded (%s)", asr.filename)
            self.event_bus.emit(
                "onboarding_required",
                {
                    "reason": "model_not_downloaded",
                    "model": asr.filename,
                },
            )
        else:
            logger.info("ASR model ready: %s", model_path)

    # --- Server + Window ---

    def _start_api_server(self) -> None:
        """Start the Litestar API server in a background thread."""

        def run_server():
            try:
                import uvicorn
                from src.api.app import create_app

                app = create_app(self)
                uvicorn.run(
                    app,
                    host="127.0.0.1",
                    port=18900,
                    log_level="warning",
                )
            except Exception:
                logger.exception("API server failed")

        self._server_thread = threading.Thread(
            target=run_server, daemon=True, name="api-server"
        )
        self._server_thread.start()
        logger.info("API server starting on http://127.0.0.1:18900")

    def _open_window(self) -> None:
        """Open the main pywebview window. Blocks until closed."""
        try:
            import webview

            self._main_window = webview.create_window(
                title="Vociferous",
                url="http://127.0.0.1:18900",
                width=1200,
                height=800,
                min_size=(800, 600),
            )

            # Pre-create the mini widget window (hidden initially)
            self._mini_window = webview.create_window(
                title="Vociferous Mini",
                url="http://127.0.0.1:18900/mini.html",
                width=160,
                height=56,
                on_top=True,
                frameless=True,
                transparent=True,
                hidden=True,
            )

            webview.start(gui="gtk", debug=False)
        except Exception:
            logger.exception("pywebview failed to start")
            # Fallback: keep running headless (API server still active)
            logger.info(
                "Running in headless mode (API server at http://127.0.0.1:18900)"
            )
            self._shutdown_event.wait()

    def toggle_mini_widget(self) -> None:
        """Toggle between full UI and mini floating widget."""
        try:
            if self._main_window is None or self._mini_window is None:
                return

            if self._mini_window.hidden:
                # Switch to mini: hide main, show mini
                self._main_window.hide()
                self._mini_window.show()
            else:
                # Switch to full: hide mini, show main
                self._mini_window.hide()
                self._main_window.show()
        except Exception:
            logger.exception("Failed to toggle mini widget")
