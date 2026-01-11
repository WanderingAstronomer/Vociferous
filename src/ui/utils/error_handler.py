"""
Centralized error handling and logging for Vociferous.

Provides:
- ErrorLogger: File-based logging with rotation
- Global exception hook for uncaught exceptions
- Utility functions for safe error display
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

if TYPE_CHECKING:
    from types import TracebackType


# Log file configuration
LOG_DIR = Path.home() / ".local" / "share" / "vociferous" / "logs"
LOG_FILE = LOG_DIR / "vociferous.log"
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 3  # Keep 3 rotated log files

# Module-level logger
logger = logging.getLogger(__name__)


class ErrorSignals(QObject):
    """Qt signals for thread-safe error display."""

    # Signal to show error dialog on main thread
    showError = pyqtSignal(str, str, str)  # title, message, details


class ErrorLogger:
    """
    Centralized error logger with file rotation.

    Thread-safe logging to file with automatic rotation.
    Also configures console output for development.
    """

    _instance: "ErrorLogger | None" = None
    _initialized: bool = False

    def __new__(cls) -> "ErrorLogger":
        """Singleton pattern for global error logger."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the error logger (only once)."""
        if ErrorLogger._initialized:
            return
        ErrorLogger._initialized = True

        self._setup_logging()
        self.signals = ErrorSignals()

    def _setup_logging(self) -> None:
        """Configure file and console logging handlers."""
        # Ensure log directory exists
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        # Root logger configuration
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        # Remove any existing handlers to avoid duplicates
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # File handler with rotation
        try:
            file_handler = RotatingFileHandler(
                LOG_FILE,
                maxBytes=MAX_LOG_SIZE,
                backupCount=BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            # Fall back to stderr if file logging fails
            print(f"Warning: Could not set up file logging: {e}", file=sys.stderr)

        # Console handler for development
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            "%(levelname)-8s | %(message)s"
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        logger.info("Error logging initialized")
        logger.info(f"Log file: {LOG_FILE}")

    def log_exception(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: "TracebackType | None",
        context: str = "",
    ) -> str:
        """
        Log an exception with full traceback.

        Args:
            exc_type: Exception type
            exc_value: Exception instance
            exc_tb: Traceback object
            context: Optional context string (e.g., "in on_activation")

        Returns:
            Formatted traceback string for display
        """
        # Format the traceback
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
        tb_string = "".join(tb_lines)

        # Build log message
        context_str = f" {context}" if context else ""
        log_message = f"Uncaught exception{context_str}:\n{tb_string}"

        # Log to file
        logger.error(log_message)

        return tb_string

    def log_error(self, message: str, context: str = "") -> None:
        """
        Log an error message.

        Args:
            message: Error message
            context: Optional context string
        """
        context_str = f" [{context}]" if context else ""
        logger.error(f"{message}{context_str}")

    def log_warning(self, message: str, context: str = "") -> None:
        """
        Log a warning message.

        Args:
            message: Warning message
            context: Optional context string
        """
        context_str = f" [{context}]" if context else ""
        logger.warning(f"{message}{context_str}")

    @staticmethod
    def get_log_file_path() -> Path:
        """Return the path to the current log file."""
        return LOG_FILE

    @staticmethod
    def open_log_file() -> bool:
        """
        Open the log file in the system's default text editor.

        Returns:
            True if successful, False otherwise
        """
        try:
            if not LOG_FILE.exists():
                return False

            # Use xdg-open on Linux
            if sys.platform.startswith("linux"):
                subprocess.Popen(
                    ["xdg-open", str(LOG_FILE)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(LOG_FILE)])
            elif sys.platform == "win32":
                os.startfile(str(LOG_FILE))  # type: ignore[attr-defined]
            else:
                return False

            return True
        except Exception as e:
            logger.error(f"Failed to open log file: {e}")
            return False

    @staticmethod
    def open_log_directory() -> bool:
        """
        Open the log directory in the system's file manager.

        Returns:
            True if successful, False otherwise
        """
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)

            if sys.platform.startswith("linux"):
                subprocess.Popen(
                    ["xdg-open", str(LOG_DIR)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(LOG_DIR)])
            elif sys.platform == "win32":
                os.startfile(str(LOG_DIR))  # type: ignore[attr-defined]
            else:
                return False

            return True
        except Exception as e:
            logger.error(f"Failed to open log directory: {e}")
            return False


# Global error logger instance
_error_logger: ErrorLogger | None = None


def get_error_logger() -> ErrorLogger:
    """Get or create the global error logger instance."""
    global _error_logger
    if _error_logger is None:
        _error_logger = ErrorLogger()
    return _error_logger


def install_exception_hook(error_callback: Callable[[str, str, str], None] | None = None) -> None:
    """
    Install a global exception hook to catch uncaught exceptions.

    Args:
        error_callback: Optional callback(title, message, details) to display errors.
                       If None, errors are logged but not displayed.
    """
    error_logger = get_error_logger()

    def exception_hook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: "TracebackType | None",
    ) -> None:
        """Custom exception hook that logs and optionally displays errors."""
        # Don't catch KeyboardInterrupt
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return

        # Log the exception
        tb_string = error_logger.log_exception(exc_type, exc_value, exc_tb)

        # Build user-friendly message
        error_name = exc_type.__name__
        error_message = str(exc_value) if str(exc_value) else "An unexpected error occurred"

        title = f"Unexpected Error: {error_name}"
        message = error_message
        details = tb_string

        # Call error callback if provided (to show dialog)
        if error_callback:
            try:
                error_callback(title, message, details)
            except Exception as callback_error:
                # If the callback itself fails, at least log it
                logger.error(f"Error callback failed: {callback_error}")
                print(f"CRITICAL: Error displaying error dialog: {callback_error}", file=sys.stderr)
                print(f"Original error: {tb_string}", file=sys.stderr)

    sys.excepthook = exception_hook
    logger.info("Global exception hook installed")


def safe_slot(context: str = "") -> Callable:
    """
    Decorator to wrap Qt slots with exception handling.

    Usage:
        @pyqtSlot()
        @safe_slot("on_button_click")
        def on_button_click(self):
            ...

    Args:
        context: Description of the slot for error logging
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Log the exception
                error_logger = get_error_logger()
                exc_type, exc_value, exc_tb = sys.exc_info()
                tb_string = error_logger.log_exception(
                    exc_type, exc_value, exc_tb, context=context or func.__name__
                )

                # Try to show error dialog
                try:
                    from ui.widgets.dialogs.error_dialog import show_error_dialog
                    show_error_dialog(
                        title=f"Error in {context or func.__name__}",
                        message=str(e),
                        details=tb_string,
                    )
                except ImportError:
                    # ErrorDialog not available yet, fall back to logging
                    logger.error(f"Could not show error dialog: {e}")
                except Exception as dialog_error:
                    logger.error(f"Error showing error dialog: {dialog_error}")

        # Preserve function metadata
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator


def format_exception_for_display(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: "TracebackType | None",
) -> tuple[str, str, str]:
    """
    Format an exception for user display.

    Returns:
        tuple[str, str, str]: (title, message, details)
    """
    error_name = exc_type.__name__
    error_message = str(exc_value) if str(exc_value) else "An unexpected error occurred"
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    tb_string = "".join(tb_lines)

    return (
        f"Error: {error_name}",
        error_message,
        tb_string,
    )


def safe_callback(func: Callable, context: str = "") -> Callable:
    """
    Wrap a callback function with exception handling (log-only, no dialog).

    Use this for background operations like signal handlers, model updates,
    file watching, and timer callbacks where showing a dialog would be
    disruptive or inappropriate.

    Usage:
        # For lambda connections:
        signal.connect(safe_callback(lambda: self.do_something(), "on_signal"))

        # For method references:
        timer.timeout.connect(safe_callback(self._on_timeout, "timeout_handler"))

    Args:
        func: The callback function to wrap
        context: Description for error logging (defaults to function name)

    Returns:
        Wrapped function that catches and logs exceptions
    """
    ctx = context or getattr(func, "__name__", "callback")

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            logger.exception(f"Error in callback [{ctx}]")

    # Preserve function metadata
    wrapper.__name__ = getattr(func, "__name__", "callback")
    wrapper.__doc__ = getattr(func, "__doc__", None)
    return wrapper


def safe_slot_silent(context: str = "") -> Callable:
    """
    Decorator to wrap Qt slots with exception handling (log-only, no dialog).

    Use this for background operations where showing an error dialog would
    be disruptive. Errors are logged but the slot fails silently from the
    user's perspective.

    Usage:
        @pyqtSlot()
        @safe_slot_silent("file_watcher_update")
        def _on_file_changed(self):
            ...

    Args:
        context: Description of the slot for error logging
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception:
                ctx = context or func.__name__
                logger.exception(f"Error in slot [{ctx}]")

        # Preserve function metadata
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator
