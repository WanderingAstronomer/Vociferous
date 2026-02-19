"""
Application Coordinator — Composition Root for Vociferous v4.0.

Plain Python class. No QObject. Owns lifecycle of all services.
Starts Litestar API server and pywebview window.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import threading
from typing import TYPE_CHECKING, Any

from src.core.command_bus import CommandBus
from src.core.event_bus import EventBus
from src.core.settings import VociferousSettings

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
        self.motd_manager: Any = None  # InsightManager | None (MOTD)
        self.title_generator: Any = None  # TitleGenerator | None

        # Recording session (created in start())
        self.recording_session: Any = None  # RecordingSession

        # Window references
        self._main_window: Any = None  # webview.Window
        self._window_maximized: bool = False

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

        # 2. Recording session (created here; ASR model loaded AFTER SLM init
        #    to guarantee llama_cpp is imported before pywhispercpp — both bundle
        #    private libggml.so copies and whisper's ggml CUDA init corrupts global
        #    state that llama.cpp then walks into if it loads second).
        from src.core.handlers.recording_handlers import RecordingSession

        self.recording_session = RecordingSession(
            audio_service_provider=lambda: self.audio_service,
            settings_provider=lambda: self.settings,
            db_provider=lambda: self.db,
            event_bus_emit=self.event_bus.emit,
            shutdown_event=self._shutdown_event,
            insight_manager_provider=lambda: self.insight_manager,
            motd_manager_provider=lambda: self.motd_manager,
            title_generator_provider=lambda: self.title_generator,
        )

        # 3. SLM runtime — MUST come before load_asr_model() so that llama_cpp
        #    is imported (and its libggml.so resolved) before pywhispercpp's
        #    ggml_cuda_init() runs.  The pre-import below is synchronous so the
        #    ordering is guaranteed even though the actual model load is async.
        self._init_slm_runtime()

        # 3b. Insight manager (lazy background SLM insight for idle screen)
        self._init_insight_manager()

        # 3c. MOTD manager (short punchy header line for TranscribeView)
        self._init_motd_manager()

        # 3d. Title generator (auto-title transcripts via SLM)
        self._init_title_generator()

        # 3e. Load ASR model — AFTER llama_cpp has been imported above.
        self.recording_session.load_asr_model()

        # 4. Audio service with event callbacks
        self._init_audio_service()

        # 5. Input handler
        self._init_input_handler()

        # 6. Register intent handlers with CommandBus
        self._register_handlers()

        # 7. Start API server in background thread
        self._start_api_server()

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
            try:
                if self._main_window is not None:
                    self._main_window.destroy()
            except Exception:
                # Window may already be in close sequence.
                logger.debug("Window destroy skipped during shutdown", exc_info=True)

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
                self.slm_runtime.disable()
            except Exception:
                logger.exception("SLM runtime cleanup failed")

        if self.recording_session is not None:
            self.recording_session.unload_asr_model()

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
        """Initialize the SLM refinement runtime if enabled.

        IMPORTANT: This method must be called before load_asr_model().
        Both llama-cpp-python and pywhispercpp bundle private copies of libggml.
        The library whose ggml_cuda_init() runs FIRST wins the global CUDA
        allocator state; if whisper's ggml runs first, llama's subsequent init
        segfaults.  Pre-importing llama_cpp here (synchronously, in the main
        thread) before pywhispercpp is ever touched guarantees the correct order.
        """
        # Pre-import llama_cpp synchronously so its libggml.so is resolved in the
        # dynamic linker BEFORE pywhispercpp's libggml.so ever loads.  The actual
        # model weights are still loaded asynchronously via enable() below.
        try:
            import llama_cpp as _llama_cpp_preload  # noqa: F401
        except ImportError:
            pass  # llama-cpp-python not installed; SLM will be unavailable

        try:
            from src.services.slm_runtime import SLMRuntime

            def on_slm_state(state):
                self.event_bus.emit("engine_status", {"slm": state.value})
                # When SLM becomes idle, opportunistically try MOTD generation.
                # This fires both on startup (LOADING→READY) and after any inference job finishes.
                from src.services.slm_types import SLMState as _SLMState

                if state == _SLMState.READY and self.motd_manager is not None:
                    self.motd_manager.maybe_schedule()

            def on_slm_error(msg):
                self.event_bus.emit("refinement_error", {"message": msg})

            def on_slm_text(text):
                # Text result from async refinement — handled per-request in _handle_refine_transcript
                pass

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
        """Initialize the InsightManager for lazy UserView dashboard insight generation."""
        try:
            from src.core.insight_manager import InsightManager
            from src.core.usage_stats import compute_usage_stats

            self.insight_manager = InsightManager(
                slm_runtime_provider=lambda: self.slm_runtime,
                event_emitter=self.event_bus.emit,
                stats_provider=lambda: compute_usage_stats(self.db) if self.db else {},
            )
            logger.info("InsightManager initialized")
        except Exception:
            logger.exception("InsightManager failed to initialize (non-fatal)")

    def _init_motd_manager(self) -> None:
        """Initialize the MOTD InsightManager for the TranscribeView header line."""
        try:
            from src.core.insight_manager import _MOTD_PROMPT, InsightManager
            from src.core.usage_stats import compute_usage_stats

            self.motd_manager = InsightManager(
                slm_runtime_provider=lambda: self.slm_runtime,
                event_emitter=self.event_bus.emit,
                stats_provider=lambda: compute_usage_stats(self.db) if self.db else {},
                prompt_template=_MOTD_PROMPT,
                cache_filename="motd_cache.json",
                event_name="motd_ready",
            )
            logger.info("MOTD InsightManager initialized")
        except Exception:
            logger.exception("MOTD InsightManager failed to initialize (non-fatal)")

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

        def _do_restart() -> None:
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
            logger.info("Engine restart complete.")

        t = threading.Thread(target=_do_restart, name="engine-restart", daemon=True)
        t.start()

    def _init_audio_service(self) -> None:
        """Initialize the audio capture service with EventBus callbacks."""
        try:
            from src.services.audio_service import AudioService

            def on_level(level: float) -> None:
                self.event_bus.emit("audio_level", {"level": level})

            def on_spectrum(bands: list[float]) -> None:
                self.event_bus.emit("audio_spectrum", {"bands": bands})

            self.audio_service = AudioService(
                settings_provider=lambda: self.settings,
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

            self.input_listener = create_listener(
                callback=self._on_hotkey,
                deactivate_callback=self._on_hotkey_release,
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
                logger.info(f"Input handler ready (backend: {backend_name})")
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
        """Instantiate domain handler objects and wire them into the CommandBus."""
        from src.core.handlers.project_handlers import ProjectHandlers
        from src.core.handlers.refinement_handlers import RefinementHandlers
        from src.core.handlers.system_handlers import SystemHandlers
        from src.core.handlers.transcript_handlers import TranscriptHandlers
        from src.core.intents.definitions import (
            AssignProjectIntent,
            BatchRetitleIntent,
            BeginRecordingIntent,
            CancelRecordingIntent,
            ClearTranscriptsIntent,
            CommitEditsIntent,
            CreateProjectIntent,
            DeleteProjectIntent,
            DeleteTranscriptIntent,
            DeleteTranscriptVariantIntent,
            RefineTranscriptIntent,
            RenameTranscriptIntent,
            RestartEngineIntent,
            RetitleTranscriptIntent,
            StopRecordingIntent,
            ToggleRecordingIntent,
            UpdateConfigIntent,
            UpdateProjectIntent,
        )

        transcript = TranscriptHandlers(
            db_provider=lambda: self.db,
            event_bus_emit=self.event_bus.emit,
        )
        project = ProjectHandlers(
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
        )

        bus = self.command_bus
        bus.register(BeginRecordingIntent, self.recording_session.handle_begin)
        bus.register(StopRecordingIntent, self.recording_session.handle_stop)
        bus.register(CancelRecordingIntent, self.recording_session.handle_cancel)
        bus.register(ToggleRecordingIntent, self.recording_session.handle_toggle)
        bus.register(DeleteTranscriptIntent, transcript.handle_delete)
        bus.register(DeleteTranscriptVariantIntent, transcript.handle_delete_variant)
        bus.register(ClearTranscriptsIntent, transcript.handle_clear)
        bus.register(CommitEditsIntent, transcript.handle_commit_edits)
        bus.register(RenameTranscriptIntent, transcript.handle_rename)
        bus.register(RefineTranscriptIntent, refinement.handle_refine)
        bus.register(CreateProjectIntent, project.handle_create)
        bus.register(UpdateProjectIntent, project.handle_update)
        bus.register(DeleteProjectIntent, project.handle_delete)
        bus.register(AssignProjectIntent, project.handle_assign)
        bus.register(UpdateConfigIntent, system.handle_update_config)
        bus.register(RestartEngineIntent, system.handle_restart_engine)
        bus.register(BatchRetitleIntent, self._handle_batch_retitle)
        bus.register(RetitleTranscriptIntent, self._handle_retitle_transcript)

    def _handle_retitle_transcript(self, intent: Any) -> None:
        """Re-generate the SLM title for a single transcript."""
        if self.title_generator is None or self.db is None:
            return
        t = self.db.get_transcript(intent.transcript_id)
        if t is None:
            return
        text = t.normalized_text or t.raw_text or ""
        if not text.strip():
            return
        self.title_generator.schedule(intent.transcript_id, text)

    def _handle_batch_retitle(self, intent: Any) -> None:
        """Dispatch batch retitling to TitleGenerator."""
        if self.title_generator is None:
            self.event_bus.emit(
                "batch_retitle_progress",
                {
                    "status": "error",
                    "message": "Title generator not initialized.",
                },
            )
            return
        self.title_generator.batch_retitle()

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
                config = uvicorn.Config(app, log_level="warning")
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

            def on_maximized() -> None:
                self._window_maximized = True

            def on_restored() -> None:
                self._window_maximized = False

            self._main_window = webview.create_window(
                title="Vociferous",
                url="http://127.0.0.1:18900",
                width=1200,
                height=800,
                min_size=(800, 600),
                frameless=True,
                easy_drag=False,
                background_color="#1e1e1e",
            )
            self._main_window.events.closing += on_closing
            self._main_window.events.maximized += on_maximized
            self._main_window.events.restored += on_restored

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

    # --- Window control (frameless title-bar) ---

    def minimize_window(self) -> None:
        """Minimize the main window."""
        if self._main_window is not None:
            self._main_window.minimize()

    def maximize_window(self) -> None:
        """Toggle maximize/restore on the main window."""
        if self._main_window is None:
            return
        if self._window_maximized:
            self._main_window.restore()
            self._window_maximized = False
        else:
            self._main_window.maximize()
            self._window_maximized = True

    def is_window_maximized(self) -> bool:
        """Return current maximize state tracked by window events."""
        return self._window_maximized

    def close_window(self) -> None:
        """Close the main window, triggering graceful shutdown."""
        if self._main_window is not None:
            self._main_window.destroy()

    def show_save_dialog(self, suggested_name: str) -> str | None:
        """Show a native save-file dialog and return the chosen path, or None if cancelled."""
        if self._main_window is None:
            return None
        try:
            import webview

            result = self._main_window.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=suggested_name,
            )
            if result and len(result) > 0:
                return str(result[0])
            return None
        except Exception:
            logger.exception("Native save dialog failed")
            return None
