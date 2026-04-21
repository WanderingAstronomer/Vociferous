"""
Vociferous — Main Entry Point.

Starts the Litestar API server in a background thread and the pywebview native
window on the main thread.
"""

import faulthandler
import logging
import os
import signal
import sys
import tempfile

# Enable faulthandler EARLY so SIGSEGV in C extensions prints a Python
# traceback instead of a silent "Segmentation fault" exit.
faulthandler.enable()

logger = logging.getLogger(__name__)


def _get_lock_file_path() -> str:
    """Get the lock file path, respecting environment override."""
    override = os.environ.get("VOCIFEROUS_LOCK_PATH")
    if override:
        return override
    return os.path.join(tempfile.gettempdir(), "vociferous.lock")


def _is_pid_alive(pid: int) -> bool:
    """Check if a process with the given PID is still running."""
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    else:
        try:
            os.kill(pid, 0)  # Signal 0 = existence check, no actual signal sent
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True  # Process exists but we can't signal it


def _get_unix_process_state(pid: int) -> str | None:
    """Return Linux process state code from /proc/<pid>/stat, or None if unavailable."""
    if sys.platform == "win32":
        return None

    try:
        with open(f"/proc/{pid}/stat") as f:
            stat_content = f.read().strip()
        parts = stat_content.split()
        if len(parts) >= 3:
            return parts[2]
    except OSError:
        return None

    return None


def _is_vociferous_process(pid: int) -> bool:
    """Best-effort check that PID belongs to this application.

    On Linux/macOS, uses /proc cmdline when available. On Windows,
    returns True (best-effort fallback).
    """
    if sys.platform == "win32":
        return True

    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            raw_cmdline = f.read()
        cmdline = raw_cmdline.replace(b"\x00", b" ").decode("utf-8", errors="ignore").lower()
        return "src.main" in cmdline or "vociferous" in cmdline
    except OSError:
        # If inspection is unavailable, avoid aggressive stale cleanup.
        return True


def _should_break_lock_for_pid(pid: int) -> bool:
    """Return True when lock owner is unusable/stale and lock should be reclaimed."""
    if not _is_pid_alive(pid):
        return True

    state = _get_unix_process_state(pid)

    # Zombie/dead-task states should never hold a live app instance.
    if state in {"Z", "X"}:
        return True

    # Stopped (e.g. Ctrl+Z) causes practical deadlock for single-instance desktop apps.
    if state in {"T", "t"} and _is_vociferous_process(pid):
        return True

    # PID reuse: lock file points at a different process.
    if not _is_vociferous_process(pid):
        return True

    return False


def _cleanup_stale_lock() -> None:
    """Remove lock files left by dead, stopped, or PID-reused processes."""
    pid_path = _get_lock_file_path()
    lock_path = pid_path + ".lock"

    try:
        if os.path.exists(pid_path):
            with open(pid_path) as f:
                old_pid = int(f.read().strip())
            if _should_break_lock_for_pid(old_pid):
                # Process is gone — clean up stale files
                for p in (lock_path, pid_path):
                    try:
                        os.unlink(p)
                    except OSError:
                        pass
    except (ValueError, OSError):
        # Corrupt PID file — remove it
        for p in (lock_path, pid_path):
            try:
                os.unlink(p)
            except OSError:
                pass


def _acquire_lock() -> bool:
    """Cross-platform single instance lock using filelock.

    Uses filelock (already a dependency) for portable file locking
    across Linux, macOS, and Windows. If the lock is held by a dead
    process (e.g. after Ctrl+Z or a crash), the stale lock is cleaned
    up and re-acquired.
    """
    from filelock import FileLock, Timeout

    lock_path = _get_lock_file_path() + ".lock"
    lock = FileLock(lock_path, timeout=0)
    try:
        lock.acquire()
    except Timeout:
        # Lock held — check if the holder is actually alive
        _cleanup_stale_lock()
        try:
            lock.acquire()
        except Timeout:
            return False

    # Write PID for diagnostics and stale-lock detection
    pid_path = _get_lock_file_path()
    with open(pid_path, "w") as f:
        f.write(str(os.getpid()))
    # Keep lock object alive for process lifetime
    _acquire_lock._lock = lock  # type: ignore[attr-defined]
    return True


def _release_lock() -> None:
    """Release instance lock and remove PID marker file."""
    lock = getattr(_acquire_lock, "_lock", None)
    if lock is not None:
        try:
            lock.release()
        except Exception:
            logger.exception("Failed to release instance lock")
        try:
            delattr(_acquire_lock, "_lock")
        except AttributeError:
            pass

    pid_path = _get_lock_file_path()
    try:
        os.unlink(pid_path)
    except OSError:
        pass


def _register_nvidia_dll_dirs() -> None:
    """Add nvidia pip-package bin dirs to the DLL search path (Windows only).

    Packages like nvidia-cublas-cu12 install DLLs under
    site-packages/nvidia/<lib>/bin/.  Without this, CTranslate2 fails with
    'cublas64_12.dll is not found or cannot be loaded'.

    Two mechanisms are used because native extensions vary in how they load
    DLLs:
      - os.add_dll_directory:  for LoadLibraryExW(LOAD_LIBRARY_SEARCH_USER_DIRS)
      - PATH prepend:          for plain LoadLibrary (what CTranslate2 uses)
    """
    import importlib.util
    import pathlib

    spec = importlib.util.find_spec("nvidia")
    if spec is None or spec.submodule_search_locations is None:
        return

    extra_dirs: list[str] = []
    for nvidia_root in spec.submodule_search_locations:
        for bin_dir in pathlib.Path(nvidia_root).glob("*/bin"):
            if bin_dir.is_dir():
                d = str(bin_dir)
                extra_dirs.append(d)
                try:
                    os.add_dll_directory(d)
                except OSError:
                    pass

    if extra_dirs:
        os.environ["PATH"] = os.pathsep.join(extra_dirs) + os.pathsep + os.environ.get("PATH", "")


def main() -> int:
    # 0. Parse startup flags
    import argparse

    parser = argparse.ArgumentParser(description="Vociferous — Speech to Text")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG-level) console logging",
    )
    args = parser.parse_args()

    # 1. Logging
    from src.core.log_manager import setup_logging

    log_manager = setup_logging()
    if args.verbose:
        log_manager.set_console_level(logging.DEBUG)

    # 2. Single instance check
    if not _acquire_lock():
        sys.stderr.write("ERROR: Vociferous is already running. Only one instance allowed.\n")
        return 1

    # 2.5. Register NVIDIA DLL paths (Windows only).
    # pip-installed nvidia-cublas-cu12 drops DLLs in site-packages but
    # Python's default DLL search won't find them.  os.add_dll_directory
    # fixes that before CTranslate2 / faster-whisper try to load cuBLAS.
    if sys.platform == "win32":
        _register_nvidia_dll_dirs()

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
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, signal_handler)
    if hasattr(signal, "SIGQUIT"):
        signal.signal(signal.SIGQUIT, signal_handler)
    # Prevent Ctrl+Z from stopping the process (creates zombies).
    # Desktop GUI apps should shut down cleanly instead of suspending.
    if hasattr(signal, "SIGTSTP"):
        signal.signal(signal.SIGTSTP, signal_handler)

    # 6. Start
    try:
        coordinator.start()
    except KeyboardInterrupt:
        pass
    finally:
        coordinator.cleanup()
        _release_lock()

    return 0


if __name__ == "__main__":
    sys.exit(main())
