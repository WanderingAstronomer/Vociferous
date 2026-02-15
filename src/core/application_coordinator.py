"""
Application Coordinator — Composition Root for Vociferous v4.0.

Plain Python class. No QObject. Owns lifecycle of all services.
Starts Litestar API server and pywebview window.
"""

import logging
import threading
from pathlib import Path

from src.core.command_bus import CommandBus
from src.core.settings import VociferousSettings, save_settings

logger = logging.getLogger(__name__)


class ApplicationCoordinator:
    """
    Composition root for the Vociferous application.

    Owns and manages the lifecycle of:
    - Settings (already initialized before construction)
    - Database
    - CommandBus
    - Engine client (ASR subprocess)
    - SLM runtime (refinement)
    - Audio service
    - Input handler
    - Litestar API server
    - pywebview windows
    """

    def __init__(self, settings: VociferousSettings) -> None:
        self.settings = settings
        self._shutdown_event = threading.Event()

        # Core services (initialized in start())
        self.command_bus = CommandBus()
        self.db = None
        self.engine_client = None
        self.audio_service = None
        self.input_listener = None
        self._server_thread: threading.Thread | None = None

    def start(self) -> None:
        """
        Initialize all services and start the application.

        Order matters:
        1. Database
        2. Engine client (ASR subprocess)
        3. Audio service
        4. Input handler
        5. Register intent handlers
        6. Start API server (background thread)
        7. Open pywebview window (blocks until closed)
        """
        logger.info("Starting Vociferous v4.0...")

        # 1. Database
        from src.database.db import TranscriptDB
        self.db = TranscriptDB()
        logger.info("Database initialized (%d transcripts)", self.db.transcript_count())

        # 2. Register intent handlers with CommandBus
        self._register_handlers()

        # 3. Audio service
        try:
            from src.services.audio_service import AudioService
            self.audio_service = AudioService()
            logger.info("Audio service ready")
        except Exception:
            logger.exception("Audio service failed to initialize (non-fatal)")

        # 4. Input handler
        try:
            from src.input_handler import create_listener
            self.input_listener = create_listener(
                activation_key=self.settings.recording.activation_key,
                backend=self.settings.recording.input_backend,
                callback=self._on_hotkey,
            )
            logger.info("Input handler ready")
        except Exception:
            logger.exception("Input handler failed to initialize (non-fatal)")

        # 5. Start API server in background thread
        self._start_api_server()

        # 6. Open pywebview window (blocks main thread)
        self._open_window()

        logger.info("Vociferous shutdown complete.")

    def shutdown(self) -> None:
        """Signal all services to stop."""
        logger.info("Shutdown requested...")
        self._shutdown_event.set()

        # Close pywebview windows
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

        if self.engine_client:
            try:
                self.engine_client.shutdown()
            except Exception:
                logger.exception("Engine client cleanup failed")

        if self.db:
            try:
                self.db.close()
            except Exception:
                logger.exception("Database cleanup failed")

        logger.info("Cleanup complete.")

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
        self.command_bus.register(DeleteTranscriptIntent, self._handle_delete_transcript)
        self.command_bus.register(CommitEditsIntent, self._handle_commit_edits)
        self.command_bus.register(RefineTranscriptIntent, self._handle_refine_transcript)

    def _handle_begin_recording(self, intent) -> None:
        logger.info("Begin recording")
        if self.audio_service:
            self.audio_service.start_recording()

    def _handle_stop_recording(self, intent) -> None:
        logger.info("Stop recording")
        if self.audio_service:
            audio_data = self.audio_service.stop_recording()
            if audio_data is not None:
                self._transcribe(audio_data)

    def _handle_cancel_recording(self, intent) -> None:
        logger.info("Cancel recording")
        if self.audio_service:
            self.audio_service.stop_recording()

    def _handle_toggle_recording(self, intent) -> None:
        if self.audio_service and self.audio_service.is_recording:
            from src.core.intents.definitions import StopRecordingIntent
            self.command_bus.dispatch(StopRecordingIntent())
        else:
            from src.core.intents.definitions import BeginRecordingIntent
            self.command_bus.dispatch(BeginRecordingIntent())

    def _handle_delete_transcript(self, intent) -> None:
        if self.db:
            self.db.delete_transcript(intent.transcript_id)

    def _handle_commit_edits(self, intent) -> None:
        if self.db:
            self.db.add_variant(
                intent.transcript_id, "user_edit", intent.content, set_current=True
            )

    def _handle_refine_transcript(self, intent) -> None:
        # TODO: Phase 2 — SLM refinement via llama-cpp-python
        logger.info("Refine transcript %d at level %d (not yet implemented)", intent.transcript_id, intent.level)

    # --- Internal ---

    def _on_hotkey(self) -> None:
        """Callback from input handler when activation key is pressed."""
        from src.core.intents.definitions import ToggleRecordingIntent
        self.command_bus.dispatch(ToggleRecordingIntent())

    def _transcribe(self, audio_data) -> None:
        """Send audio to the engine subprocess for transcription."""
        # TODO: Phase 2 — pywhispercpp engine integration
        logger.info("Transcription requested (engine not yet connected)")

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

        self._server_thread = threading.Thread(target=run_server, daemon=True, name="api-server")
        self._server_thread.start()
        logger.info("API server starting on http://127.0.0.1:18900")

    def _open_window(self) -> None:
        """Open the main pywebview window. Blocks until closed."""
        try:
            import webview

            window = webview.create_window(
                title="Vociferous",
                url="http://127.0.0.1:18900",
                width=1200,
                height=800,
                min_size=(800, 600),
            )
            webview.start(gui="gtk", debug=False)
        except Exception:
            logger.exception("pywebview failed to start")
            # Fallback: keep running headless (API server still active)
            logger.info("Running in headless mode (API server at http://127.0.0.1:18900)")
            self._shutdown_event.wait()
