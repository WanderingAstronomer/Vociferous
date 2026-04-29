from __future__ import annotations

import logging
import os
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.application_coordinator import ApplicationCoordinator

logger = logging.getLogger(__name__)


def shutdown_coordinator(
    coordinator: ApplicationCoordinator,
    *,
    stop_server: bool = True,
    close_windows: bool = True,
) -> None:
    """Signal services to stop. Safe to call multiple times."""
    del stop_server

    with coordinator._shutdown_lock:
        if coordinator._shutdown_started:
            return
        coordinator._shutdown_started = True

    logger.info("Shutdown requested...")
    coordinator._shutdown_event.set()

    if coordinator.recording_session is not None:
        coordinator.recording_session.cancel_for_shutdown()

    if coordinator._uvicorn_server:
        coordinator._uvicorn_server.should_exit = True

    if close_windows:
        coordinator.window.destroy_for_shutdown()


def cleanup_coordinator(coordinator: ApplicationCoordinator) -> None:
    """Release resources after event loop exits."""

    def _force_exit() -> None:
        logger.warning("Cleanup watchdog triggered — forcing exit.")
        os._exit(0)

    watchdog = threading.Timer(8.0, _force_exit)
    watchdog.daemon = True
    watchdog.start()

    try:
        do_cleanup(coordinator)
    finally:
        watchdog.cancel()


def do_cleanup(coordinator: ApplicationCoordinator) -> None:
    """Actual cleanup logic, guarded by watchdog timeout."""
    rec_thread = coordinator.recording_session.thread if coordinator.recording_session is not None else None
    if rec_thread is not None and rec_thread.is_alive():
        logger.debug("Waiting for recording thread to finish...")
        rec_thread.join(timeout=5)
        if rec_thread.is_alive():
            logger.warning("Recording thread did not finish within timeout")

    if coordinator.input_listener:
        try:
            coordinator.input_listener.stop()
        except Exception:
            logger.exception("Input listener cleanup failed")

    if coordinator.slm_runtime:
        try:
            coordinator.slm_runtime.shutdown()
        except Exception:
            logger.exception("SLM runtime cleanup failed")

    if coordinator.recording_session is not None:
        coordinator.recording_session.shutdown_models()

    if coordinator.db:
        try:
            coordinator.db.close()
        except Exception:
            logger.exception("Database cleanup failed")

    if coordinator._uvicorn_server:
        coordinator._uvicorn_server.should_exit = True
    if coordinator._server_thread and coordinator._server_thread.is_alive():
        coordinator._server_thread.join(timeout=5)

    coordinator.event_bus.clear()
    logger.info("Cleanup complete.")


def restart_engine(coordinator: ApplicationCoordinator) -> None:
    """Tear down and reload ASR + SLM models on a background thread."""
    if not coordinator._restart_lock.acquire(blocking=False):
        logger.warning("Engine restart already in progress — ignoring duplicate request.")
        return

    def _do_restart() -> None:
        try:
            logger.info("Engine restart requested — tearing down models...")
            coordinator.event_bus.emit("engine_status", {"asr": "restarting", "slm": "restarting"})

            if coordinator.recording_session is not None:
                coordinator.recording_session.unload_asr_model()

            if coordinator.slm_runtime:
                try:
                    coordinator.slm_runtime.disable()
                    coordinator.slm_runtime = None
                except Exception:
                    logger.exception("SLM teardown failed during restart")

            from src.core.log_manager import log_support_diagnostics_snapshot
            from src.core.settings import get_settings

            coordinator.settings = get_settings()
            log_support_diagnostics_snapshot(
                coordinator.settings,
                transcript_count=coordinator.db.transcript_count() if coordinator.db is not None else None,
            )

            if coordinator.recording_session is not None:
                coordinator.recording_session.load_asr_model()
            coordinator._init_slm_runtime()
            coordinator.event_bus.emit("engine_restarted", {})

            logger.info("Engine restart complete.")
        finally:
            coordinator._restart_lock.release()

    thread = threading.Thread(target=_do_restart, name="engine-restart", daemon=True)
    thread.start()
