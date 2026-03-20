"""
Application Coordinator — Composition Root for Vociferous v4.0.

Plain Python class. No QObject. Owns lifecycle of all services.
Starts Litestar API server and pywebview window.
"""

from __future__ import annotations

import logging
import os
import platform
import threading
from typing import TYPE_CHECKING, Any

from src.core.command_bus import CommandBus
from src.core.event_bus import EventBus
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

        logger.info("Starting Vociferous %s...", APP_VERSION)

        # 1. Database
        from src.database.db import TranscriptDB

        self.db = TranscriptDB()
        logger.info("Database initialized (%d transcripts)", self.db.transcript_count())

        # 2. Recording session (created here; ASR model loaded after SLM init).
        from src.core.handlers.recording_handlers import RecordingSession

        self.recording_session = RecordingSession(
            audio_service_provider=lambda: self.audio_service,
            settings_provider=lambda: self.settings,
            db_provider=lambda: self.db,
            event_bus_emit=self.event_bus.emit,
            shutdown_event=self._shutdown_event,
            insight_manager_provider=lambda: self.insight_manager,
            title_generator_provider=lambda: self.title_generator,
        )

        # 2b. Audio cache manager (WAV cache + orphan spool detection).
        from src.services.audio_cache import AudioCacheManager

        audio_cache = AudioCacheManager(sample_rate=self.settings.recording.sample_rate)
        self.recording_session.audio_cache = audio_cache
        orphans = audio_cache.cleanup_stale_spools()
        if orphans:
            logger.warning(
                "%d orphaned audio spool(s) found from prior crash — see log above for paths",
                len(orphans),
            )

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
        with self._shutdown_lock:
            if self._shutdown_started:
                return
            self._shutdown_started = True

        logger.info("Shutdown requested...")
        self._shutdown_event.set()

        # Cancel any in-progress recording so the recording loop
        # treats this as a cancellation (not a normal stop).
        if self.recording_session is not None:
            self.recording_session.cancel_for_shutdown()

        # Always signal the uvicorn server to exit — even when called from
        # the window-closing callback (stop_server=False only means we skip
        # waiting for it here; cleanup() handles the join).
        if self._uvicorn_server:
            self._uvicorn_server.should_exit = True

        if close_windows:
            self.window.destroy_for_shutdown()

    def cleanup(self) -> None:
        """Release resources after event loop exits."""
        # Watchdog: if cleanup takes more than 8 seconds, force-exit the process.
        # Desktop apps must not hang on shutdown — daemon threads are fine to orphan.
        import os

        def _force_exit() -> None:
            logger.warning("Cleanup watchdog triggered — forcing exit.")
            os._exit(0)

        watchdog = threading.Timer(8.0, _force_exit)
        watchdog.daemon = True
        watchdog.start()

        try:
            self._do_cleanup()
        finally:
            watchdog.cancel()

    def _do_cleanup(self) -> None:
        """Actual cleanup logic, guarded by watchdog timeout."""
        # Wait for the recording thread to finish before tearing down
        # resources it may still be using (ASR model, database).
        rec_thread = self.recording_session.thread if self.recording_session is not None else None
        if rec_thread is not None and rec_thread.is_alive():
            logger.debug("Waiting for recording thread to finish...")
            rec_thread.join(timeout=5)
            if rec_thread.is_alive():
                logger.warning("Recording thread did not finish within timeout")

        if self.input_listener:
            try:
                self.input_listener.stop()
            except Exception:
                logger.exception("Input listener cleanup failed")

        if self.slm_runtime:
            try:
                self.slm_runtime.shutdown()
            except Exception:
                logger.exception("SLM runtime cleanup failed")

        if self.recording_session is not None:
            self.recording_session.shutdown_models()

        if self.db:
            try:
                self.db.close()
            except Exception:
                logger.exception("Database cleanup failed")

        # Ensure uvicorn server thread finishes
        if self._uvicorn_server:
            self._uvicorn_server.should_exit = True
        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=5)

        self.event_bus.clear()
        logger.info("Cleanup complete.")

    # --- Service Initialization ---

    def _init_slm_runtime(self) -> None:
        """Initialize the SLM refinement runtime if enabled."""
        try:
            from src.services.slm_runtime import SLMRuntime

            def on_slm_state(state):
                self.event_bus.emit("engine_status", {"slm": state.value})
                # When SLM becomes idle, opportunistically try insight generation.
                # This fires both on startup (LOADING→READY) and after any inference job finishes.
                from src.services.slm_types import SLMState as _SLMState

                if state == _SLMState.READY and self.insight_manager is not None:
                    self.insight_manager.maybe_schedule()

            def on_slm_error(msg):
                self.event_bus.emit("refinement_error", {"message": msg})

            def on_slm_text(text):
                pass  # Async path unused; refinement uses refine_text_sync via RefinementHandlers

            self.slm_runtime = SLMRuntime(
                settings_provider=lambda: self.settings,
                on_state_changed=on_slm_state,
                on_error=on_slm_error,
                on_text_ready=on_slm_text,
            )

            if self.settings.refinement.enabled:
                self.slm_runtime.enable()

        except Exception:
            logger.exception("SLM runtime failed to initialize (non-fatal)")

    def _init_insight_manager(self) -> None:
        """Initialize the unified InsightManager for analytics paragraphs (UserView + TranscribeView)."""
        try:
            from src.core.insight_manager import InsightManager
            from src.core.usage_stats import compute_usage_stats

            self.insight_manager = InsightManager(
                slm_runtime_provider=lambda: self.slm_runtime,
                event_emitter=self.event_bus.emit,
                stats_provider=lambda: (
                    compute_usage_stats(self.db, typing_wpm=self.settings.user.typing_wpm) if self.db else {}
                ),
            )
            logger.info("InsightManager initialized (unified)")
        except Exception:
            logger.exception("InsightManager failed to initialize (non-fatal)")

    def _init_title_generator(self) -> None:
        """Initialize the TitleGenerator for auto-naming transcripts via SLM."""
        try:
            from src.core.title_generator import TitleGenerator

            self.title_generator = TitleGenerator(
                slm_runtime_provider=lambda: self.slm_runtime,
                db_provider=lambda: self.db,
                event_emitter=self.event_bus.emit,
            )
            logger.info("TitleGenerator initialized")
        except Exception:
            logger.exception("TitleGenerator failed to initialize (non-fatal)")

    def restart_engine(self) -> None:
        """Tear down and reload ASR + SLM models on a background thread.

        Called when the user clicks "Restart Engine" in settings, typically
        after changing model selection or GPU/CPU preference.
        """
        if not self._restart_lock.acquire(blocking=False):
            logger.warning("Engine restart already in progress — ignoring duplicate request.")
            return

        def _do_restart() -> None:
            try:
                logger.info("Engine restart requested — tearing down models...")
                self.event_bus.emit("engine_status", {"asr": "restarting", "slm": "restarting"})

                # Tear down ASR
                if self.recording_session is not None:
                    self.recording_session.unload_asr_model()

                # Tear down SLM
                if self.slm_runtime:
                    try:
                        self.slm_runtime.disable()
                        self.slm_runtime = None
                    except Exception:
                        logger.exception("SLM teardown failed during restart")

                # Reload settings in case model/device changed
                from src.core.settings import get_settings

                self.settings = get_settings()

                # Reload models
                if self.recording_session is not None:
                    self.recording_session.load_asr_model()
                self._init_slm_runtime()

                # Notify the API layer that the engine has been restarted so it
                # can clear any caches that depend on engine state (e.g. GPU status).
                # Using the event bus here keeps the core layer free of any
                # dependency on the API layer.
                self.event_bus.emit("engine_restarted", {})

                logger.info("Engine restart complete.")
            finally:
                self._restart_lock.release()

        t = threading.Thread(target=_do_restart, name="engine-restart", daemon=True)
        t.start()

    def _init_audio_service(self) -> None:
        """Initialize the audio capture service with EventBus callbacks."""
        try:
            from src.services.audio_service import AudioService

            def on_level(level: float) -> None:
                self.event_bus.emit("audio_level", {"level": level})

            self.audio_service = AudioService(
                settings_provider=lambda: self.settings,
                on_level_update=on_level,
            )
            logger.info("Audio service ready")
        except Exception:
            logger.exception("Audio service failed to initialize (non-fatal)")

    def _init_input_handler(self) -> None:
        """Initialize the global hotkey listener."""
        try:
            from src.input_handler import create_listener

            self.input_listener = create_listener(
                callback=self._on_hotkey,
                deactivate_callback=self._on_hotkey_release,
                on_degradation=lambda msg: self.event_bus.emit(
                    "engine_status",
                    {"component": "input", "status": "degraded", "message": msg},
                ),
            )
            if self.input_listener.active_backend is None:
                logger.warning(
                    "Input handler started but no backend available — "
                    "hotkey will not work. On Linux, ensure your user is "
                    "in the 'input' group: sudo usermod -aG input $USER"
                )
                self.event_bus.emit(
                    "engine_status",
                    {
                        "component": "input",
                        "status": "unavailable",
                        "message": "No input backend available. Hotkey disabled.",
                    },
                )
            else:
                backend_name = type(self.input_listener.active_backend).__name__
                logger.info("Input handler ready (backend: %s)", backend_name)
                if backend_name == "PynputBackend" and (
                    os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
                    or bool(os.environ.get("WAYLAND_DISPLAY"))
                ):
                    logger.warning(
                        "Input backend is pynput under Wayland; hotkey capture may be "
                        "degraded for native Wayland windows."
                    )
                    self.event_bus.emit(
                        "engine_status",
                        {
                            "component": "input",
                            "status": "degraded",
                            "message": (
                                "Pynput under Wayland may not capture hotkeys. "
                                "Prefer evdev backend with input-group permissions."
                            ),
                        },
                    )
        except Exception:
            logger.exception("Input handler failed to initialize (non-fatal)")

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

        def _detect_port_conflict(port: int) -> tuple[bool, str]:
            """Detect if another process is using our port.

            Returns (conflict_detected, error_message).
            """
            try:
                import psutil
            except ImportError:
                # Without psutil, we can't provide helpful diagnostics
                return False, ""

            try:
                current_pid = psutil.Process().pid
                for conn in psutil.net_connections(kind="inet"):
                    if conn.laddr.port == port and conn.status == "LISTEN":
                        try:
                            proc = psutil.Process(conn.pid)
                            if proc.pid == current_pid:
                                # This process already owns it (shouldn't happen, but skip)
                                continue

                            cmdline = " ".join(proc.cmdline())
                            username = proc.username()

                            # Provide actionable error message
                            msg = (
                                f"Port {port} is already in use by PID {conn.pid} ({username}).\n"
                                f"Command: {cmdline}\n\n"
                                f"To fix:\n"
                                f"  1. Kill the process: kill {conn.pid}\n"
                                f"  2. If unresponsive: kill -9 {conn.pid}\n"
                                f"  3. Or check with: ss -tlnp | grep {port}"
                            )
                            return True, msg
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
            except Exception:
                logger.debug("Port conflict detection failed", exc_info=True)

            return False, ""

        def run_server():
            import socket as socket_mod

            import uvicorn

            from src.api.app import create_app

            # Check for port conflicts and provide helpful error
            conflict, conflict_msg = _detect_port_conflict(18900)
            if conflict:
                logger.error(conflict_msg)
                return

            app = create_app(self)

            # Pre-create socket with SO_REUSEADDR so the kernel lets us rebind
            # immediately after an unclean shutdown (socket stuck in TIME_WAIT).
            # This is the standard production-server approach.
            sock = socket_mod.socket(socket_mod.AF_INET, socket_mod.SOCK_STREAM)
            sock.setsockopt(socket_mod.SOL_SOCKET, socket_mod.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", 18900))
            except OSError as exc:
                logger.error(
                    "Cannot bind port 18900 — another process owns it. "
                    "Kill the existing Vociferous instance manually: %s",
                    exc,
                )
                sock.close()
                return

            try:
                config = uvicorn.Config(app, log_level="warning", log_config=None)
                server = uvicorn.Server(config)
                self._uvicorn_server = server
                # Pass our pre-bound socket; uvicorn skips its own bind.
                server.run(sockets=[sock])
            except Exception:
                logger.exception("API server failed")
            finally:
                # Belt-and-suspenders: close if uvicorn didn't already.
                try:
                    sock.close()
                except OSError:
                    pass

        self._server_thread = threading.Thread(target=run_server, daemon=True, name="api-server")
        self._server_thread.start()
        logger.info("API server starting on http://127.0.0.1:18900")

    def _wait_for_server(self, host: str = "127.0.0.1", port: int = 18900, timeout: float = 15.0) -> None:
        """Block until the API server is accepting TCP connections or timeout expires."""
        import socket
        import time

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with socket.create_connection((host, port), timeout=0.1):
                    logger.info("API server ready (http://%s:%d)", host, port)
                    return
            except OSError:
                time.sleep(0.05)
        logger.warning("API server did not become ready within %.1fs — opening window anyway", timeout)

    def _open_window(self) -> None:
        """Open the main pywebview window. Blocks until closed."""
        try:
            import webview

            if platform.system() == "Linux":
                try:
                    from gi.repository import GLib

                    GLib.set_prgname("vociferous")
                    GLib.set_application_name("Vociferous")
                except Exception:
                    logger.debug("Could not set GTK app identity", exc_info=True)

            from src.core.resource_manager import ResourceManager

            # Resolve app icon path
            icon_path = ResourceManager.get_icon_path("vociferous_icon")

            def on_closing() -> bool:
                """Called when main window is closing. Trigger graceful shutdown."""
                logger.info("Main window closing, initiating shutdown...")
                self.shutdown(stop_server=True, close_windows=False)
                return True  # Allow main window to close naturally

            self._main_window = webview.create_window(
                title="Vociferous",
                url="http://127.0.0.1:18900",
                width=1200,
                height=800,
                min_size=(800, 600),
                background_color="#1e1e1e",
            )
            self.window.set_window(self._main_window)
            self._main_window.events.closing += on_closing
            self._main_window.events.maximized += self.window.on_maximized
            self._main_window.events.restored += self.window.on_restored

            webview.start(debug=False, icon=icon_path)
        except Exception:
            logger.exception("pywebview failed to start")
            # Fail fast to avoid leaving background services alive without UI.
            self.shutdown()
            raise RuntimeError("pywebview failed to start")
        finally:
            # Ensure shutdown is called even if webview exits unexpectedly
            if not self._shutdown_event.is_set():
                self.shutdown(stop_server=False, close_windows=False)

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
