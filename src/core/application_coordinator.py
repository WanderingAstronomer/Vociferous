"""
Application Coordinator — Composition Root for Vociferous v4.0.

Plain Python class. No QObject. Owns lifecycle of all services.
Starts Litestar API server and pywebview window.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

from src.core.command_bus import CommandBus
from src.core.event_bus import EventBus
from src.core.runtime import (
    cleanup_coordinator,
    do_cleanup,
    init_audio_service,
    init_input_handler,
    init_insight_manager,
    init_recording_session,
    init_slm_runtime,
    init_title_generator,
    open_window,
    shutdown_coordinator,
    start_api_server,
    wait_for_server,
)
from src.core.runtime import (
    restart_engine as restart_engine_runtime,
)
from src.core.settings import VociferousSettings
from src.core.window_controller import WindowController

if TYPE_CHECKING:
    from src.database.db import TranscriptDB
    from src.input_handler.listener import KeyListener
    from src.services.audio_service import AudioService
    from src.services.slm_runtime import SLMRuntime

logger = logging.getLogger(__name__)


class ApplicationCoordinator:
    """
    Composition root for the Vociferous application.

    Owns and manages the lifecycle of:
    - Settings (already initialized before construction)
    - Database
    - CommandBus + EventBus
    - Transcription model (CTranslate2 Whisper)
    - SLM runtime (CTranslate2 Generator refinement)
    - Audio service
    - Input handler
    - Litestar API server
    - pywebview window
    """

    def __init__(self, settings: VociferousSettings) -> None:
        self.settings = settings
        self._shutdown_event = threading.Event()
        self._shutdown_lock = threading.Lock()
        self._shutdown_started = False

        # Core buses
        self.command_bus = CommandBus()
        self.event_bus = EventBus()

        # Services (initialized in start())
        self.db: TranscriptDB | None = None
        self.audio_service: AudioService | None = None
        self.input_listener: KeyListener | None = None
        self.slm_runtime: SLMRuntime | None = None
        self._uvicorn_server: Any = None  # uvicorn.Server for graceful shutdown
        self.insight_manager: Any = None  # InsightManager | None
        self.title_generator: Any = None  # TitleGenerator | None

        # Recording session (created in start())
        self.recording_session: Any = None  # RecordingSession

        # Window controller (frameless title-bar + native dialogs)
        self.window = WindowController()

        self._server_thread: threading.Thread | None = None

        # Engine restart serialization — initialized here so it is always present
        # (previously created lazily with hasattr(), which is a code smell).
        self._restart_lock = threading.Lock()

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
        from src.core.constants import APP_VERSION
        from src.core.log_manager import log_support_diagnostics_snapshot

        logger.info("Starting Vociferous %s...", APP_VERSION)

        # 1. Database
        from src.database.db import TranscriptDB

        self.db = TranscriptDB()
        logger.info("Database initialized (%d transcripts)", self.db.transcript_count())
        log_support_diagnostics_snapshot(self.settings, transcript_count=self.db.transcript_count())

        # 2. Recording session (created here; ASR model loaded after SLM init).
        init_recording_session(self)

        # 3. SLM runtime (CTranslate2 Generator).
        self._init_slm_runtime()

        # 3b. Insight manager (unified analytics paragraph for UserView + TranscribeView)
        self._init_insight_manager()

        # 3c. Title generator (auto-title transcripts via SLM)
        self._init_title_generator()

        # 3e. Load ASR model (CTranslate2 Whisper).
        self.recording_session.load_asr_model()

        # 3f. Preload Silero VAD model (eliminates cold-start on first transcription).
        self.recording_session.load_vad_model()

        # 4. Audio service with event callbacks
        self._init_audio_service()

        # 5. Input handler
        self._init_input_handler()

        # 6. Register intent handlers with CommandBus
        self._register_handlers()

        # 7. Start API server in background thread
        self._start_api_server()

        # 7b. Wait until the server is actually accepting connections before
        #     handing the URL to WebKit — eliminates the "Connection refused"
        #     race on fast hardware where the window opens before uvicorn binds.
        self._wait_for_server()

        # 8. Open pywebview window (blocks main thread)
        self._open_window()

        logger.info("Vociferous shutdown complete.")

    def shutdown(self, *, stop_server: bool = True, close_windows: bool = True) -> None:
        """Signal services to stop. Safe to call multiple times."""
        shutdown_coordinator(self, stop_server=stop_server, close_windows=close_windows)

    def cleanup(self) -> None:
        """Release resources after event loop exits."""
        cleanup_coordinator(self)

    def _do_cleanup(self) -> None:
        """Actual cleanup logic, guarded by watchdog timeout."""
        do_cleanup(self)

    # --- Service Initialization ---

    def _init_slm_runtime(self) -> None:
        """Initialize the SLM refinement runtime if enabled."""
        init_slm_runtime(self)

    def _init_insight_manager(self) -> None:
        """Initialize the unified InsightManager for analytics paragraphs (UserView + TranscribeView)."""
        init_insight_manager(self)

    def _init_title_generator(self) -> None:
        """Initialize the TitleGenerator for auto-naming transcripts via SLM."""
        init_title_generator(self)

    def restart_engine(self) -> None:
        """Tear down and reload ASR + SLM models on a background thread.

        Called when the user clicks "Restart Engine" in settings, typically
        after changing model selection or GPU/CPU preference.
        """
        restart_engine_runtime(self)

    def _init_audio_service(self) -> None:
        """Initialize the audio capture service with EventBus callbacks."""
        init_audio_service(self)

    def _init_input_handler(self) -> None:
        """Initialize the global hotkey listener."""
        init_input_handler(self)

    # --- Intent Handlers ---

    def _register_handlers(self) -> None:
        """Instantiate domain handler objects and wire them into the CommandBus.

        Each handler method is decorated with @handles(IntentType), so
        register_all() discovers and wires them automatically.
        """
        from src.core.handlers.refinement_handlers import RefinementHandlers
        from src.core.handlers.system_handlers import SystemHandlers
        from src.core.handlers.title_handlers import TitleHandlers
        from src.core.handlers.transcript_handlers import TranscriptHandlers

        transcript = TranscriptHandlers(
            db_provider=lambda: self.db,
            event_bus_emit=self.event_bus.emit,
        )
        refinement = RefinementHandlers(
            db_provider=lambda: self.db,
            slm_runtime_provider=lambda: self.slm_runtime,
            settings_provider=lambda: self.settings,
            event_bus_emit=self.event_bus.emit,
            title_generator_provider=lambda: self.title_generator,
        )
        system = SystemHandlers(
            event_bus_emit=self.event_bus.emit,
            input_listener_provider=lambda: self.input_listener,
            on_settings_updated=lambda s: setattr(self, "settings", s),
            restart_engine=self.restart_engine,
            insight_manager_provider=lambda: self.insight_manager,
        )
        title = TitleHandlers(
            db_provider=lambda: self.db,
            title_generator_provider=lambda: self.title_generator,
            event_bus_emit=self.event_bus.emit,
        )

        bus = self.command_bus
        bus.register_all(self.recording_session)
        bus.register_all(transcript)
        bus.register_all(refinement)
        bus.register_all(system)
        bus.register_all(title)

    # --- Hotkey ---

    def _on_hotkey(self) -> None:
        """Callback from input handler when activation key is pressed."""
        from src.core.intents.definitions import ToggleRecordingIntent

        mode = self.settings.recording.recording_mode
        if mode == "hold_to_record":
            # Hold mode: press starts recording
            from src.core.intents.definitions import BeginRecordingIntent

            self.command_bus.dispatch(BeginRecordingIntent())
        else:
            # Toggle mode (default): press toggles recording state
            self.command_bus.dispatch(ToggleRecordingIntent())
            if self.input_listener:
                self.input_listener.reset_chord_state()

    def _on_hotkey_release(self) -> None:
        """Callback from input handler when activation key is released."""
        mode = self.settings.recording.recording_mode
        if mode == "hold_to_record" and self.recording_session is not None and self.recording_session.is_recording:
            from src.core.intents.definitions import StopRecordingIntent

            self.command_bus.dispatch(StopRecordingIntent())

    # --- Server + Window ---

    def _start_api_server(self) -> None:
        """Start the Litestar API server in a background thread."""
        start_api_server(self)

    def _wait_for_server(self, host: str = "127.0.0.1", port: int = 18900, timeout: float = 15.0) -> None:
        """Block until the API server is accepting TCP connections or timeout expires."""
        wait_for_server(host=host, port=port, timeout=timeout)

    def _open_window(self) -> None:
        """Open the main pywebview window. Blocks until closed."""
        open_window(self)

    # --- Window control (delegated to WindowController) ---

    def minimize_window(self) -> None:
        """Minimize the main window."""
        self.window.minimize()

    def maximize_window(self) -> None:
        """Toggle maximize/restore on the main window."""
        self.window.maximize()

    def is_window_maximized(self) -> bool:
        """Return current maximize state tracked by window events."""
        return self.window.is_maximized

    def close_window(self) -> None:
        """Close the main window, triggering graceful shutdown."""
        self.window.close()

    def show_save_dialog(self, suggested_name: str) -> str | None:
        """Show a native save-file dialog and return the chosen path, or None if cancelled."""
        return self.window.show_save_dialog(suggested_name)

    def show_open_dialog(self, file_types: tuple[str, ...] = ()) -> str | None:
        """Show a native open-file dialog and return the chosen path, or None if cancelled."""
        return self.window.show_open_dialog(file_types)

    # --- Query accessors (used by the API layer to avoid drilling into internals) ---

    def get_transcript_count(self) -> int:
        """Return the number of transcripts in the database."""
        return self.db.transcript_count() if self.db else 0

    def is_recording_active(self) -> bool:
        """Return whether a recording is currently in progress."""
        return self.recording_session is not None and self.recording_session.is_recording

    def get_insight_text(self) -> str:
        """Return the cached insight text, or empty string if unavailable."""
        if self.insight_manager is not None:
            return self.insight_manager.cached_text
        return ""

    def get_motd_text(self) -> str:
        """Return the cached insight text (same as get_insight_text; kept for API compat)."""
        if self.insight_manager is not None:
            return self.insight_manager.cached_text
        return ""
