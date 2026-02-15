"""
Vociferous v4.0 — Main Entry Point.

Starts Litestar API server + pywebview native window.
Replaces PyQt6 QApplication bootstrap.
"""

import logging
import os
import signal
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_lock_file_path() -> str:
    """Get the lock file path, respecting environment override."""
    override = os.environ.get("VOCIFEROUS_LOCK_PATH")
    if override:
        return override
    return os.path.join(tempfile.gettempdir(), "vociferous.lock")


def _acquire_lock() -> bool:
    """Simple file-based single instance lock. Returns True if acquired."""
    import fcntl

    lock_path = _get_lock_file_path()
    try:
        lock_fd = open(lock_path, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        # Keep fd open (lock is held while process lives)
        _acquire_lock._fd = lock_fd  # type: ignore[attr-defined]
        return True
    except (OSError, IOError):
        return False


def main() -> int:
    # 1. Logging (basic — LogManager will enhance later)
    from src.core.log_manager import setup_logging
    setup_logging()

    # 2. Single instance check
    if not _acquire_lock():
        sys.stderr.write(
            "ERROR: Vociferous is already running. Only one instance allowed.\n"
        )
        return 1

    # 3. Settings
    from src.core.settings import init_settings
    settings = init_settings()

    # 4. Application Coordinator (composition root)
    from src.core.application_coordinator import ApplicationCoordinator
    coordinator = ApplicationCoordinator(settings)

    # 5. Signal handlers for graceful shutdown
    def signal_handler(signum: int, frame: object) -> None:
        logger.info("Received signal %d, initiating shutdown...", signum)
        coordinator.shutdown()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # 6. Start
    try:
        coordinator.start()
    except KeyboardInterrupt:
        pass
    finally:
        coordinator.cleanup()

    return 0


if __name__ == "__main__":
    sys.exit(main())
