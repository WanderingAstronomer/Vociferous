from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.application_coordinator import ApplicationCoordinator

logger = logging.getLogger(__name__)


def init_recording_session(coordinator: ApplicationCoordinator) -> None:
    """Create the recording session and attach audio cache support."""
    from src.core.handlers.recording_handlers import RecordingSession
    from src.services.audio_cache import AudioCacheManager

    coordinator.recording_session = RecordingSession(
        audio_service_provider=lambda: coordinator.audio_service,
        settings_provider=lambda: coordinator.settings,
        db_provider=lambda: coordinator.db,
        event_bus_emit=coordinator.event_bus.emit,
        shutdown_event=coordinator._shutdown_event,
        insight_manager_provider=lambda: coordinator.insight_manager,
        title_generator_provider=lambda: coordinator.title_generator,
    )

    audio_cache = AudioCacheManager(sample_rate=coordinator.settings.recording.sample_rate)
    coordinator.recording_session.audio_cache = audio_cache
    orphans = audio_cache.cleanup_stale_spools()
    if orphans:
        logger.warning(
            "%d orphaned audio spool(s) found from prior crash — see log above for paths",
            len(orphans),
        )


def init_slm_runtime(coordinator: ApplicationCoordinator) -> None:
    """Initialize the SLM refinement runtime if enabled."""
    try:
        from src.services.slm_runtime import SLMRuntime

        def on_slm_state(state):
            coordinator.event_bus.emit("engine_status", {"slm": state.value})
            from src.services.slm_types import SLMState as _SLMState

            if state == _SLMState.READY and coordinator.insight_manager is not None:
                coordinator.insight_manager.maybe_schedule()

        def on_slm_error(msg):
            coordinator.event_bus.emit("refinement_error", {"message": msg})

        def on_slm_text(text):
            del text

        coordinator.slm_runtime = SLMRuntime(
            settings_provider=lambda: coordinator.settings,
            on_state_changed=on_slm_state,
            on_error=on_slm_error,
            on_text_ready=on_slm_text,
        )

        if coordinator.settings.refinement.enabled:
            coordinator.slm_runtime.enable()

    except Exception:
        logger.exception("SLM runtime failed to initialize (non-fatal)")


def init_insight_manager(coordinator: ApplicationCoordinator) -> None:
    """Initialize the unified InsightManager for analytics paragraphs."""
    try:
        from src.core.insight_manager import InsightManager
        from src.core.usage_stats import compute_usage_stats

        coordinator.insight_manager = InsightManager(
            slm_runtime_provider=lambda: coordinator.slm_runtime,
            event_emitter=coordinator.event_bus.emit,
            stats_provider=lambda: (
                compute_usage_stats(coordinator.db, typing_wpm=coordinator.settings.user.typing_wpm)
                if coordinator.db
                else {}
            ),
        )
        logger.info("InsightManager initialized (unified)")
    except Exception:
        logger.exception("InsightManager failed to initialize (non-fatal)")


def init_title_generator(coordinator: ApplicationCoordinator) -> None:
    """Initialize the TitleGenerator for auto-naming transcripts via SLM."""
    try:
        from src.core.title_generator import TitleGenerator

        coordinator.title_generator = TitleGenerator(
            slm_runtime_provider=lambda: coordinator.slm_runtime,
            db_provider=lambda: coordinator.db,
            event_emitter=coordinator.event_bus.emit,
        )
        logger.info("TitleGenerator initialized")
    except Exception:
        logger.exception("TitleGenerator failed to initialize (non-fatal)")


def init_audio_service(coordinator: ApplicationCoordinator) -> None:
    """Initialize the audio capture service with EventBus callbacks."""
    try:
        from src.services.audio_service import AudioService

        def on_level(level: float) -> None:
            coordinator.event_bus.emit("audio_level", {"level": level})

        coordinator.audio_service = AudioService(
            settings_provider=lambda: coordinator.settings,
            on_level_update=on_level,
        )
        logger.info("Audio service ready")
    except Exception:
        logger.exception("Audio service failed to initialize (non-fatal)")


def init_input_handler(coordinator: ApplicationCoordinator) -> None:
    """Initialize the global hotkey listener."""
    try:
        from src.input_handler import create_listener

        coordinator.input_listener = create_listener(
            callback=coordinator._on_hotkey,
            deactivate_callback=coordinator._on_hotkey_release,
            on_degradation=lambda msg: coordinator.event_bus.emit(
                "engine_status",
                {"component": "input", "status": "degraded", "message": msg},
            ),
        )
        if coordinator.input_listener.active_backend is None:
            logger.warning(
                "Input handler started but no backend available — "
                "hotkey will not work. On Linux, ensure your user is "
                "in the 'input' group: sudo usermod -aG input $USER"
            )
            coordinator.event_bus.emit(
                "engine_status",
                {
                    "component": "input",
                    "status": "unavailable",
                    "message": "No input backend available. Hotkey disabled.",
                },
            )
        else:
            backend_name = type(coordinator.input_listener.active_backend).__name__
            logger.info("Input handler ready (backend: %s)", backend_name)
            if backend_name == "PynputBackend" and (
                os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))
            ):
                logger.warning(
                    "Input backend is pynput under Wayland; hotkey capture may be degraded for native Wayland windows."
                )
                coordinator.event_bus.emit(
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
