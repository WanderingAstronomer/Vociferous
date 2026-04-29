"""Runtime helpers for coordinator lifecycle, service bootstrapping, and UI/server plumbing."""

from .lifecycle import cleanup_coordinator, do_cleanup, restart_engine, shutdown_coordinator
from .server_window import open_window, start_api_server, wait_for_server
from .services import (
    init_audio_service,
    init_input_handler,
    init_insight_manager,
    init_recording_session,
    init_slm_runtime,
    init_title_generator,
)

__all__ = [
    "cleanup_coordinator",
    "do_cleanup",
    "restart_engine",
    "shutdown_coordinator",
    "open_window",
    "start_api_server",
    "wait_for_server",
    "init_audio_service",
    "init_input_handler",
    "init_insight_manager",
    "init_recording_session",
    "init_slm_runtime",
    "init_title_generator",
]
