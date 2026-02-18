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
        self._asr_model: Any = None  # pywhispercpp Model instance
        self._uvicorn_server: Any = None  # uvicorn.Server for graceful shutdown
        self.insight_manager: Any = None  # InsightManager | None
        self.motd_manager: Any = None  # InsightManager | None (MOTD)

        # Recording state
        self._is_recording = False
        self._recording_lock = threading.Lock()
        self._recording_stop = threading.Event()
        self._recording_thread: threading.Thread | None = None

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

        # 2. ASR model (optional warm load)
        self._load_asr_model()

        # 3. SLM runtime
        self._init_slm_runtime()

        # 3b. Insight manager (lazy background SLM insight for idle screen)
        self._init_insight_manager()

        # 3c. MOTD manager (short punchy header line for TranscribeView)
        self._init_motd_manager()

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
        self._recording_stop.set()
        self._is_recording = False

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
        if self._recording_thread is not None and self._recording_thread.is_alive():
            logger.debug("Waiting for recording thread to finish...")
            self._recording_thread.join(timeout=5)
            if self._recording_thread.is_alive():
                logger.warning("Recording thread did not finish within timeout")
            self._recording_thread = None

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

        # Ensure uvicorn server thread finishes
        if self._uvicorn_server:
            self._uvicorn_server.should_exit = True
        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=5)

        self.event_bus.clear()
        logger.info("Cleanup complete.")

    # --- Service Initialization ---

    def _load_asr_model(self) -> None:
        """Warm-load the whisper.cpp model at startup."""
        try:
            from src.services.transcription_service import create_local_model

            self._asr_model = create_local_model(self.settings)
            self.event_bus.emit("engine_status", {"asr": "ready"})
        except Exception:
            logger.exception("ASR model failed to load (will retry on first transcription)")
            self.event_bus.emit("engine_status", {"asr": "unavailable"})

    def _init_slm_runtime(self) -> None:
        """Initialize the SLM refinement runtime if enabled."""
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

            SPEAKING_WPM = 150
            TYPING_WPM = 40
            FILLER_SINGLE = {
                "um",
                "uh",
                "uhm",
                "umm",
                "er",
                "err",
                "like",
                "basically",
                "literally",
                "actually",
                "so",
                "well",
                "right",
                "okay",
            }
            FILLER_MULTI = ["you know", "i mean", "kind of", "sort of"]

            def _compute_stats() -> dict:
                """Compute usage statistics from DB — mirrors UserView's derived metrics."""
                if not self.db:
                    return {}
                transcripts = self.db.recent(limit=10000)
                if not transcripts:
                    return {}

                count = len(transcripts)
                total_words = 0
                all_words: list[str] = []
                recorded_seconds = 0.0
                total_silence = 0.0
                filler_count = 0

                for t in transcripts:
                    text = t.normalized_text or t.raw_text or ""
                    words = text.split()
                    total_words += len(words)

                    lower = text.lower()
                    # Filler multi-word
                    for f in FILLER_MULTI:
                        idx = 0
                        while (idx := lower.find(f, idx)) != -1:
                            filler_count += 1
                            idx += len(f)
                    # Filler single-word
                    for w in lower.split():
                        cleaned = w.strip(".,!?;:'\"()[]{}").lower()
                        if cleaned in FILLER_SINGLE:
                            filler_count += 1

                    # Collect cleaned words for vocab diversity
                    for w in lower.split():
                        c = w.strip(".,!?;:'\"()[]{}").lower()
                        if c:
                            all_words.append(c)

                    dur = (t.duration_ms or 0) / 1000
                    if dur > 0:
                        recorded_seconds += dur
                        expected = (len(words) / SPEAKING_WPM) * 60
                        total_silence += max(0.0, dur - expected)

                # Fallback estimate if no durations available
                if recorded_seconds == 0 and total_words > 0:
                    recorded_seconds = (total_words / SPEAKING_WPM) * 60

                typing_seconds = (total_words / TYPING_WPM) * 60
                time_saved = max(0.0, typing_seconds - recorded_seconds)
                avg_seconds = recorded_seconds / count if count > 0 else 0
                vocab_ratio = len(set(all_words)) / len(all_words) if all_words else 0

                return {
                    "count": count,
                    "total_words": total_words,
                    "recorded_seconds": recorded_seconds,
                    "time_saved_seconds": time_saved,
                    "avg_seconds": avg_seconds,
                    "vocab_ratio": vocab_ratio,
                    "total_silence_seconds": total_silence,
                    "filler_count": filler_count,
                }

            self.insight_manager = InsightManager(
                slm_runtime_provider=lambda: self.slm_runtime,
                event_emitter=self.event_bus.emit,
                stats_provider=_compute_stats,
            )
            logger.info("InsightManager initialized")
        except Exception:
            logger.exception("InsightManager failed to initialize (non-fatal)")

    def _init_motd_manager(self) -> None:
        """Initialize the MOTD InsightManager for the TranscribeView header line."""
        try:
            from src.core.insight_manager import _MOTD_PROMPT, InsightManager

            def _compute_stats() -> dict:
                if self.insight_manager is None:
                    return {}
                # Reuse the same stats the insight_manager computes — no point duplicating
                return self.insight_manager._get_stats()  # noqa: SLF001

            self.motd_manager = InsightManager(
                slm_runtime_provider=lambda: self.slm_runtime,
                event_emitter=self.event_bus.emit,
                stats_provider=_compute_stats,
                prompt_template=_MOTD_PROMPT,
                cache_filename="motd_cache.json",
                event_name="motd_ready",
            )
            logger.info("MOTD InsightManager initialized")
        except Exception:
            logger.exception("MOTD InsightManager failed to initialize (non-fatal)")

    def restart_engine(self) -> None:
        """Tear down and reload ASR + SLM models on a background thread.

        Called when the user clicks "Restart Engine" in settings, typically
        after changing model selection or GPU/CPU preference.
        """

        def _do_restart() -> None:
            logger.info("Engine restart requested — tearing down models...")
            self.event_bus.emit("engine_status", {"asr": "restarting", "slm": "restarting"})

            # Tear down ASR
            if self._asr_model:
                try:
                    del self._asr_model
                    self._asr_model = None
                except Exception:
                    logger.exception("ASR teardown failed during restart")

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
            self._load_asr_model()
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
        """Register all intent handlers with the CommandBus."""
        from src.core.intents.definitions import (
            AssignProjectIntent,
            BeginRecordingIntent,
            CancelRecordingIntent,
            ClearTranscriptsIntent,
            CommitEditsIntent,
            CreateProjectIntent,
            DeleteProjectIntent,
            DeleteTranscriptIntent,
            DeleteTranscriptVariantIntent,
            RefineTranscriptIntent,
            RestartEngineIntent,
            StopRecordingIntent,
            ToggleRecordingIntent,
            UpdateConfigIntent,
            UpdateProjectIntent,
        )

        self.command_bus.register(BeginRecordingIntent, self._handle_begin_recording)
        self.command_bus.register(StopRecordingIntent, self._handle_stop_recording)
        self.command_bus.register(CancelRecordingIntent, self._handle_cancel_recording)
        self.command_bus.register(ToggleRecordingIntent, self._handle_toggle_recording)
        self.command_bus.register(DeleteTranscriptIntent, self._handle_delete_transcript)
        self.command_bus.register(DeleteTranscriptVariantIntent, self._handle_delete_transcript_variant)
        self.command_bus.register(ClearTranscriptsIntent, self._handle_clear_transcripts)
        self.command_bus.register(CommitEditsIntent, self._handle_commit_edits)
        self.command_bus.register(RefineTranscriptIntent, self._handle_refine_transcript)
        self.command_bus.register(CreateProjectIntent, self._handle_create_project)
        self.command_bus.register(UpdateProjectIntent, self._handle_update_project)
        self.command_bus.register(DeleteProjectIntent, self._handle_delete_project)
        self.command_bus.register(AssignProjectIntent, self._handle_assign_project)
        self.command_bus.register(UpdateConfigIntent, self._handle_update_config)
        self.command_bus.register(RestartEngineIntent, self._handle_restart_engine)

    def _handle_begin_recording(self, intent) -> None:
        with self._recording_lock:
            if self._is_recording or not self.audio_service:
                return

            # Pre-check: is the ASR model file actually available?
            from src.core.model_registry import ASR_MODELS, get_asr_model
            from src.core.resource_manager import ResourceManager

            model_id = self.settings.model.model
            asr_model = get_asr_model(model_id) or ASR_MODELS.get("large-v3-turbo-q5_0")
            if asr_model:
                model_path = ResourceManager.get_user_cache_dir("models") / asr_model.filename
                if not model_path.exists():
                    self.event_bus.emit(
                        "transcription_error",
                        {"message": "No ASR model downloaded. Go to Settings to download a speech recognition model."},
                    )
                    return

            self._is_recording = True

        self._recording_stop.clear()
        self.event_bus.emit("recording_started", {})

        t = threading.Thread(target=self._recording_loop, daemon=True, name="recording")
        self._recording_thread = t
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

    def _handle_delete_transcript_variant(self, intent) -> None:
        if self.db:
            deleted = self.db.delete_variant(intent.transcript_id, intent.variant_id)
            if deleted:
                # Refresh entire transcript for simplicity, or just notify variant deleted
                # The frontend likely re-fetches or we need to send updated transcript object
                # For now just notify updated.
                t = self.db.get_transcript(intent.transcript_id)
                if t:
                    # Convert to dict manually or use a helper if available, but coordinator imports are tricky.
                    # Ideally we just emit the ID and let frontend fetch.
                    self.event_bus.emit("transcript_updated", {"id": intent.transcript_id})

    def _handle_clear_transcripts(self, intent) -> None:
        if self.db:
            count = self.db.clear_all_transcripts()
            logger.info("Cleared all transcripts: %d deleted", count)
            self.event_bus.emit("transcripts_cleared", {"count": count})

    def _handle_commit_edits(self, intent) -> None:
        if self.db:
            variant = self.db.add_variant(intent.transcript_id, "user_edit", intent.content, set_current=True)
            self.event_bus.emit(
                "transcript_updated",
                {"id": intent.transcript_id, "variant_id": variant.id},
            )

    def _handle_create_project(self, intent) -> None:
        """Create a new project and emit an event."""
        if not self.db:
            return
        project = self.db.add_project(
            name=intent.name,
            color=intent.color,
            parent_id=intent.parent_id,
        )
        self.event_bus.emit(
            "project_created",
            {
                "id": project.id,
                "name": project.name,
                "color": project.color,
                "parent_id": project.parent_id,
            },
        )

    def _handle_update_project(self, intent) -> None:
        """Update a project's name/color/parent and emit an event."""
        if not self.db:
            return
        kwargs: dict = {}
        if intent.name is not None:
            kwargs["name"] = intent.name
        if intent.color is not None:
            kwargs["color"] = intent.color
        # parent_id is passed through as-is (None means move to root)
        kwargs["parent_id"] = intent.parent_id
        project = self.db.update_project(intent.project_id, **kwargs)
        if project:
            self.event_bus.emit(
                "project_updated",
                {
                    "id": project.id,
                    "name": project.name,
                    "color": project.color,
                    "parent_id": project.parent_id,
                },
            )

    def _handle_delete_project(self, intent) -> None:
        """Delete a project (re-parents children to root) and emit an event."""
        if not self.db:
            return
        deleted = self.db.delete_project(intent.project_id)
        if deleted:
            self.event_bus.emit("project_deleted", {"id": intent.project_id})

    def _handle_assign_project(self, intent) -> None:
        """Assign or unassign a transcript to/from a project."""
        if not self.db:
            return
        self.db.assign_project(intent.transcript_id, intent.project_id)
        self.event_bus.emit(
            "transcript_updated",
            {"id": intent.transcript_id, "project_id": intent.project_id},
        )

    def _handle_update_config(self, intent) -> None:
        from src.core.settings import update_settings

        new_settings = update_settings(**intent.settings)
        self.settings = new_settings
        self.event_bus.emit("config_updated", new_settings.model_dump())

        # Reload activation keys if the input handler is running
        if self.input_listener:
            try:
                self.input_listener.update_activation_keys()
                logger.info("Input handler activation keys reloaded")
            except Exception:
                logger.exception("Failed to reload activation keys")

    def _handle_restart_engine(self, intent) -> None:
        """Restart ASR + SLM models (background thread)."""
        self.restart_engine()

    def _handle_refine_transcript(self, intent) -> None:
        """Refine a transcript using the SLM runtime."""
        if not self.db:
            self.event_bus.emit("refinement_error", {"message": "Database not available"})
            return

        if not self.slm_runtime:
            self.event_bus.emit("refinement_error", {"message": "Refinement is not configured. Enable it in Settings."})
            return

        from src.services.slm_types import SLMState

        state = self.slm_runtime.state
        if state == SLMState.DISABLED:
            self.event_bus.emit(
                "refinement_error",
                {"message": "Refinement is disabled. Enable it in Settings and ensure a model is downloaded."},
            )
            return
        if state == SLMState.LOADING:
            self.event_bus.emit(
                "refinement_error",
                {"message": "The refinement model is still loading. Please wait a moment and try again."},
            )
            return
        if state == SLMState.ERROR:
            self.event_bus.emit(
                "refinement_error",
                {"message": "The refinement model failed to load. Check Settings to verify a model is downloaded."},
            )
            return
        if state == SLMState.INFERRING:
            self.event_bus.emit(
                "refinement_error", {"message": "A refinement is already in progress. Please wait for it to finish."}
            )
            return
        if state != SLMState.READY:
            self.event_bus.emit("refinement_error", {"message": f"Refinement model not ready (state: {state.value})"})
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
            import time

            start_time = time.monotonic()
            try:
                # ALWAYS refine from the immutable original, never a previous variant.
                # transcript.text returns the current variant if set, which would
                # cause re-refining the already-refined output on subsequent runs.
                text = transcript.normalized_text or transcript.raw_text

                self.event_bus.emit(
                    "refinement_progress",
                    {
                        "transcript_id": intent.transcript_id,
                        "status": "inferring",
                        "message": "Running inference…",
                    },
                )

                refined = self.slm_runtime.refine_text_sync(
                    text,
                    level=intent.level,
                    instructions=intent.instructions,
                )

                elapsed = round(time.monotonic() - start_time, 1)

                # Store as variant
                variant = self.db.add_variant(
                    intent.transcript_id,
                    f"refinement_L{intent.level}",
                    refined,
                    model_id=self.settings.refinement.model_id,
                    set_current=True,
                )

                # Prune old refinement variants: keep only the 3 most recent.
                self.db.prune_refinement_variants(intent.transcript_id, keep=3)

                self.event_bus.emit(
                    "refinement_complete",
                    {
                        "transcript_id": intent.transcript_id,
                        "variant_id": variant.id,
                        "text": refined,
                        "level": intent.level,
                        "elapsed_seconds": elapsed,
                    },
                )
            except Exception as e:
                logger.exception("Refinement failed for transcript %d", intent.transcript_id)
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
            audio_data = self.audio_service.record_audio(should_stop=lambda: self._recording_stop.is_set())

            # Check if cancelled during recording
            if not self._is_recording:
                return

            self._is_recording = False
            self.event_bus.emit("recording_stopped", {"cancelled": False})

            if audio_data is None or len(audio_data) == 0:
                self.event_bus.emit("transcription_error", {"message": "Recording too short or empty"})
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
        # Do not start transcription if shutdown is in progress.
        if self._shutdown_event.is_set():
            logger.debug("Transcription skipped — shutdown in progress")
            return

        from src.services.transcription_service import create_local_model, transcribe

        try:
            # Lazy-load ASR model if not already loaded
            if self._asr_model is None:
                self._asr_model = create_local_model(self.settings)

            text, speech_duration_ms = transcribe(
                audio_data,
                settings=self.settings,
                local_model=self._asr_model,
            )

            if not text.strip():
                self.event_bus.emit("transcription_error", {"message": "No speech detected"})
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

            # Schedule a lazy insight generation if the cache is stale.
            # Runs off-thread and only proceeds if the SLM is idle.
            if self.insight_manager is not None:
                self.insight_manager.maybe_schedule()
            if self.motd_manager is not None:
                self.motd_manager.maybe_schedule()

            # Auto-copy to system clipboard (works without window focus)
            if self.settings.output.auto_copy_to_clipboard:
                self._copy_to_system_clipboard(text)

            logger.info("Transcription complete: %d chars, %dms", len(text), duration_ms)

        except Exception as e:
            logger.exception("Transcription failed")
            self.event_bus.emit("transcription_error", {"message": str(e)})

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

    def _on_hotkey_release(self) -> None:
        """Callback from input handler when activation key is released."""
        mode = self.settings.recording.recording_mode
        if mode == "hold_to_record" and self._is_recording:
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

    # --- Clipboard ---

    @staticmethod
    def _copy_to_system_clipboard(text: str) -> None:
        """Copy text to the system clipboard without requiring window focus.

        Uses platform-native CLI tools so it works even when the
        pywebview window is not focused or is hidden behind other windows.
        """
        system = platform.system()
        try:
            if system == "Linux":
                # Try xclip first (more common), fall back to xsel
                for cmd in (
                    ["xclip", "-selection", "clipboard"],
                    ["xsel", "--clipboard", "--input"],
                ):
                    try:
                        subprocess.run(
                            cmd,
                            input=text.encode("utf-8"),
                            check=True,
                            timeout=3,
                        )
                        logger.debug("Copied %d chars to clipboard via %s", len(text), cmd[0])
                        return
                    except FileNotFoundError:
                        continue
                logger.warning("No clipboard tool found (install xclip or xsel)")
            elif system == "Darwin":
                subprocess.run(
                    ["pbcopy"],
                    input=text.encode("utf-8"),
                    check=True,
                    timeout=3,
                )
                logger.debug("Copied %d chars to clipboard via pbcopy", len(text))
            elif system == "Windows":
                subprocess.run(
                    ["clip.exe"],
                    input=text.encode("utf-16le"),
                    check=True,
                    timeout=3,
                )
                logger.debug("Copied %d chars to clipboard via clip.exe", len(text))
            else:
                logger.warning("Auto-copy not supported on %s", system)
        except Exception:
            logger.warning("Failed to copy to system clipboard", exc_info=True)

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
