"""
Centralized error handling and logging for Vociferous.

Provides:
- ErrorLogger: UI-aware wrapper for LogManager (handles ErrorSignals)
- Global exception hook for uncaught exceptions via LogManager
- Utility functions for safe error display
"""

from __future__ import annotations

import json
import logging
import os
import platform
import sys
import datetime
import traceback
import functools
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Tuple

from PyQt6.QtCore import QObject, pyqtSignal

from src.core.exceptions import VociferousError
from src.core.log_manager import LogManager, CRASH_DUMP_DIR

if TYPE_CHECKING:
    from types import TracebackType

# Module-level logger
logger = logging.getLogger(__name__)


class ErrorSignals(QObject):
    """Qt signals for thread-safe error display."""

    # Signal to show error dialog on main thread
    showError = pyqtSignal(str, str, str)  # title, message, details


class ErrorLogger:
    """
    UI Wrapper for the Core LogManager.
    Maintains compatibility with existing code calling get_error_logger().
    Adds Qt signals for error display.
    """

    _instance: "ErrorLogger | None" = None
    _initialized: bool = False

    def __new__(cls) -> "ErrorLogger":
        """Singleton pattern for global error logger."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize."""
        if ErrorLogger._initialized:
            return
        ErrorLogger._initialized = True

        self.signals = ErrorSignals()
        self.log_manager = LogManager()

    def configure_logging(self) -> None:
        """
        Configure logging.
        Delegates to core LogManager.
        """
        self.log_manager.configure_logging()

    def log_exception(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: "TracebackType | None",
        context: str = "",
    ) -> str:
        """Log exception via LogManager."""
        return self.log_manager.log_exception(exc_type, exc_value, exc_tb, context)

    def log_error(self, message: str, context: str = "") -> None:
        """Log error via LogManager."""
        self.log_manager.log_error(message, context)

    def log_warning(self, message: str, context: str = "") -> None:
        """Log warning via LogManager."""
        self.log_manager.log_warning(message, context)

    @staticmethod
    def get_log_file_path() -> Path:
        """Return the path to the current log file."""
        return LogManager.get_log_file_path()

    @staticmethod
    def open_log_file() -> bool:
        """Open the log file."""
        return LogManager.open_log_file()

    @staticmethod
    def open_log_directory() -> bool:
        """Open the log directory."""
        return LogManager.open_log_directory()


# Global error logger instance
_error_logger: ErrorLogger | None = None


def get_error_logger() -> ErrorLogger:
    """Get or create the global error logger instance."""
    global _error_logger
    if _error_logger is None:
        _error_logger = ErrorLogger()
    return _error_logger


def create_crash_dump(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: "TracebackType | None",
) -> str:
    """
    Generate a detailed JSON crash dump for Agent analysis.
    This saves a snapshot of the environment and stack at crash time.
    """
    dump_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dump_file = CRASH_DUMP_DIR / f"crash_{dump_id}.json"

    # Extract stack frames with local variables
    stack_info = []
    tb = exc_tb
    while tb:
        frame = tb.tb_frame
        stack_info.append(
            {
                "filename": frame.f_code.co_filename,
                "lineno": tb.tb_lineno,
                "function": frame.f_code.co_name,
                "locals": {
                    k: str(v)
                    for k, v in frame.f_locals.items()
                    if not k.startswith("_")
                },
            }
        )
        tb = tb.tb_next

    # Gather System Info
    sys_info = {
        "platform": platform.platform(),
        "python_version": sys.version,
        "argv": sys.argv,
        "cwd": os.getcwd(),
        "env": {
            k: v for k, v in os.environ.items() if "TOKEN" not in k and "KEY" not in k
        },  # Filter secrets
    }

    # Gather Exception Data
    error_data = {
        "type": exc_type.__name__,
        "message": str(exc_value),
        "doc_ref": exc_value.doc_ref
        if isinstance(exc_value, VociferousError)
        else None,
        "context": exc_value.context
        if isinstance(exc_value, VociferousError)
        else None,
    }

    report = {
        "timestamp": datetime.datetime.now().isoformat(),
        "error": error_data,
        "stack_trace": stack_info,
        "system_info": sys_info,
    }

    try:
        with open(dump_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return str(dump_file)
    except Exception as e:
        return f"Failed to write crash dump: {e}"


def install_exception_hook(
    error_callback: Callable[[str, str, str], None] | None = None,
) -> None:
    """
    Install a global exception hook to catch uncaught exceptions.

    Args:
        error_callback: Optional callback(title, message, details)
    """
    error_logger = get_error_logger()

    def exception_hook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: "TracebackType | None",
    ) -> None:
        """Custom exception hook that logs and optionally displays errors."""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return

        # 1. Log the exception normally
        tb_string = error_logger.log_exception(exc_type, exc_value, exc_tb)

        # 2. Create Agentic Crash Dump
        dump_path = create_crash_dump(exc_type, exc_value, exc_tb)
        logger.info(f"Crash dump saved to: {dump_path}")

        # 3. Build user-friendly message
        error_name = exc_type.__name__
        error_message = (
            str(exc_value) if str(exc_value) else "An unexpected error occurred"
        )

        if isinstance(exc_value, VociferousError) and exc_value.doc_ref:
            error_message += f"\n\nSee: {exc_value.doc_ref}"

        title = f"Unexpected Error: {error_name}"
        message = error_message
        details = f"Crash Dump: {dump_path}\n\nTraceback:\n{tb_string}"

        # 4. Display Dialog
        if error_callback:
            try:
                error_callback(title, message, details)
            except Exception as callback_error:
                logger.critical(f"Error displaying dialog: {callback_error}")

    sys.excepthook = exception_hook


def format_exception_for_display(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: "TracebackType | None",
) -> Tuple[str, str, str]:
    """
    Format an exception for display in the error dialog.

    Returns:
        (title, message, details)
    """
    error_name = exc_type.__name__
    error_message = str(exc_value)

    if isinstance(exc_value, VociferousError) and exc_value.doc_ref:
        error_message += f"\n\nSee: {exc_value.doc_ref}"

    tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    details = "".join(tb_lines)

    return f"Error: {error_name}", error_message, details


def safe_callback(
    func: Callable[..., Any], context: str | None = None
) -> Callable[..., Any]:
    """
    Decorator to wrap callbacks in a try/except block.
    Logs exceptions and prevents them from crashing the app.

    Args:
        func: The function to wrap
        context: Optional description of the context (e.g. "on_click")
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            ctx = context or func.__name__
            get_error_logger().log_exception(
                type(e), e, e.__traceback__, context=f"in {ctx}"
            )
            return None

    return wrapper


def safe_slot(context: str = "") -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator factory for Qt slots to handle exceptions gracefully.
    Usage: @safe_slot("MyContext")
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        return safe_callback(func, context)

    return decorator


def safe_slot_silent(
    context: str = "",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator factory for Qt slots that suppresses errors (logs as warning only).
    Usage: @safe_slot_silent("MyContext")
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Log as warning
                logger.warning(f"Silenced error in {context or func.__name__}: {e}")
                return None

        return wrapper

    return decorator
