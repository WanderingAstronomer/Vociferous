"""
Vociferous - Main Entry Point.

Refactored to use ApplicationCoordinator as the composition root.
Maintains Single Instance Lock and Global Exception Handling.
"""

import logging
import os
import signal
import sys
import tempfile

from PyQt6.QtCore import QLockFile, qInstallMessageHandler
from PyQt6.QtWidgets import QApplication

from src.core.application_coordinator import ApplicationCoordinator
from src.ui.utils.error_handler import install_exception_hook
from src.ui.widgets.dialogs.error_dialog import show_error_dialog

# Prefer client-side decorations on Wayland
os.environ.setdefault("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1")

logger = logging.getLogger(__name__)

_QT_MESSAGE_HANDLER_INSTALLED = False
_TRAY_DBUS_ERROR_SEEN = False


def _qt_message_handler(_mode, _context, message: str) -> None:
    global _TRAY_DBUS_ERROR_SEEN
    if "QDBusTrayIcon encountered a D-Bus error" in message:
        _TRAY_DBUS_ERROR_SEEN = True
        return
    # Default handler equivalent or simple output
    sys.stderr.write(f"{message}\n")


def _install_qt_message_handler() -> None:
    global _QT_MESSAGE_HANDLER_INSTALLED
    if _QT_MESSAGE_HANDLER_INSTALLED:
        return
    qInstallMessageHandler(_qt_message_handler)
    _QT_MESSAGE_HANDLER_INSTALLED = True


def _get_lock_file_path() -> str:
    """Get the lock file path, respecting environment override."""
    override = os.environ.get("VOCIFEROUS_LOCK_PATH")
    if override:
        return override
    return os.path.join(tempfile.gettempdir(), "vociferous.lock")


def _global_exception_handler(title: str, message: str, details: str) -> None:
    """Callback for error dialog display (invoked by error_handler)."""
    # Note: Exception logging is handled by src/ui/utils/error_handler.py
    try:
        if QApplication.instance():
            parent = QApplication.activeWindow()
            show_error_dialog(
                title=title,
                message=message,
                details=details,
                parent=parent,
            )
    except Exception as e:
        sys.stderr.write(f"Critical Error (Dialog failed): {message} | {e}\n")


def main():
    # 1. Setup Exception Hooks
    install_exception_hook(_global_exception_handler)
    _install_qt_message_handler()

    # 2. Single Instance Check
    lock_file_path = _get_lock_file_path()
    lock = QLockFile(lock_file_path)
    lock.setStaleLockTime(10_000)

    if not lock.tryLock():
        if lock.removeStaleLockFile() and lock.tryLock():
            pass
        else:
            sys.stderr.write(
                "ERROR: Vociferous is already running. Only one instance allowed.\n"
            )
            return 1

    # 3. Application Setup
    app = QApplication(sys.argv)
    app.setApplicationName("Vociferous")
    app.setQuitOnLastWindowClosed(False)

    # 4. Font Configuration
    font = app.font()
    font.setPointSize(18)
    app.setFont(font)

    # 5. Coordinator (Composition Root)
    coordinator = ApplicationCoordinator(app)

    # 6. Install Signal Handlers for graceful shutdown
    def signal_handler(signum, frame):
        """Handle SIGTERM and SIGINT by triggering shutdown."""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        coordinator.shutdown()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # 7. Start
    try:
        coordinator.start()
        ret = app.exec()
    finally:
        # Cleanup
        coordinator.cleanup()
        lock.unlock()

    return ret


if __name__ == "__main__":
    sys.exit(main())
