"""
Centralized error handling and logging for Vociferous.

Provides:
- ErrorLogger: File-based logging with rotation and dynamic configuration
- Global exception hook for uncaught exceptions with "Agentic" crash dumps
- Utility functions for safe error display
"""

from __future__ import annotations

import json
import logging
import os
import platform
import subprocess
import sys
import traceback
import datetime
import functools
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Tuple, Type

from PyQt6.QtCore import QObject, pyqtSignal

from exceptions import VociferousError
from utils import ConfigManager

if TYPE_CHECKING:
    from types import TracebackType


# Log file configuration
LOG_DIR = Path.home() / ".local" / "share" / "vociferous" / "logs"
LOG_FILE = LOG_DIR / "vociferous.log"
CRASH_DUMP_DIR = LOG_DIR / "crash_dumps"
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 3  # Keep 3 rotated log files

# Module-level logger
logger = logging.getLogger(__name__)


class AgentFriendlyFormatter(logging.Formatter):
    """
    Formatter that produces structured JSON or rich text suitable for Agents.
    """

    def __init__(self, structured: bool = False):
        self.structured = structured
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        if self.structured:
            log_entry = {
                "timestamp": self.formatTime(record),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "file": record.pathname,
                "line": record.lineno,
            }
            if record.exc_info:
                log_entry["exception"] = self.formatException(record.exc_info)
            if hasattr(record, "context"):
                 log_entry["context"] = record.context
            
            return json.dumps(log_entry)
        else:
             # Rich text format
            timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
            msg = f"{timestamp} | {record.levelname:<8} | {record.name}:{record.lineno} | {record.getMessage()}"
            if hasattr(record, "context"):
                msg += f" | Context: {record.context}"
            if record.exc_info:
                # Indent tracebacks for readability
                tb = self.formatException(record.exc_info)
                msg += "\n" + "\n".join("    " + line for line in tb.splitlines())
            return msg


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

        self.signals = ErrorSignals()
        self.configure_logging()

    def configure_logging(self) -> None:
        """Configure file and console logging handlers based on config."""
        # Ensure log directory exists
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        CRASH_DUMP_DIR.mkdir(parents=True, exist_ok=True)

        # Get settings from ConfigManager (if initialized, else defaults)
        try:
            log_level_str = ConfigManager.get_config_value("logging", "level") or "INFO"
            log_level = getattr(logging, log_level_str.upper(), logging.INFO)
            
            enable_console = ConfigManager.get_config_value("logging", "console_echo")
            if enable_console is None:
                enable_console = True  # Default true

            structured = ConfigManager.get_config_value("logging", "structured_output") or False
        except RuntimeError:
            # ConfigManager might not be ready yet during early startup
            log_level = logging.INFO
            enable_console = True
            structured = False

        # Root logger configuration
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG) # capture everything, handlers filter

        # Remove any existing handlers to avoid duplicates
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        formatter = AgentFriendlyFormatter(structured=structured)

        # File handler with rotation
        try:
            file_handler = RotatingFileHandler(
                LOG_FILE,
                maxBytes=MAX_LOG_SIZE,
                backupCount=BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            # Fall back to stderr if file logging fails
            print(f"Warning: Could not set up file logging: {e}", file=sys.stderr)

        # Console handler
        if enable_console:
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(log_level)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)

        logger.info(f"Error logging initialized. Level: {log_level}, Structured: {structured}")
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
        log_message = f"Uncaught exception{context_str}: {exc_value}"

        # Capture extra context if available
        extra = {}
        if isinstance(exc_value, VociferousError):
            extra["context"] = exc_value.context
            log_message += f" | Doc Ref: {exc_value.doc_ref}"

        # Log to file
        logger.error(log_message, exc_info=(exc_type, exc_value, exc_tb), extra=extra)

        return tb_string

    def log_error(self, message: str, context: str = "") -> None:
        """Log an error message."""
        context_str = f" [{context}]" if context else ""
        logger.error(f"{message}{context_str}")

    def log_warning(self, message: str, context: str = "") -> None:
        """Log a warning message."""
        context_str = f" [{context}]" if context else ""
        logger.warning(f"{message}{context_str}")

    @staticmethod
    def get_log_file_path() -> Path:
        """Return the path to the current log file."""
        return LOG_FILE

    @staticmethod
    def open_log_file() -> bool:
        """Open the log file in the system's default text editor."""
        return _open_path(LOG_FILE)

    @staticmethod
    def open_log_directory() -> bool:
        """Open the log directory in the system's file manager."""
        return _open_path(LOG_DIR)


def _open_path(path: Path) -> bool:
    """Helper to open a file or directory."""
    try:
        path = path if path.is_dir() else path.parent
        path.mkdir(parents=True, exist_ok=True)
        
        target = str(path) if path.is_file() else str(path)

        if sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target])
        elif sys.platform == "win32":
            os.startfile(target)  # type: ignore
        else:
            return False
        return True
    except Exception as e:
        logger.error(f"Failed to open {path}: {e}")
        return False


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
        stack_info.append({
            "filename": frame.f_code.co_filename,
            "lineno": tb.tb_lineno,
            "function": frame.f_code.co_name,
            "locals": {k: str(v) for k, v in frame.f_locals.items() if not k.startswith('_')}
        })
        tb = tb.tb_next

    # Gather System Info
    sys_info = {
        "platform": platform.platform(),
        "python_version": sys.version,
        "argv": sys.argv,
        "cwd": os.getcwd(),
        "env": {k: v for k, v in os.environ.items() if "TOKEN" not in k and "KEY" not in k} # Filter secrets
    }
    
    # Gather Exception Data
    error_data = {
        "type": exc_type.__name__,
        "message": str(exc_value),
        "doc_ref": exc_value.doc_ref if isinstance(exc_value, VociferousError) else None,
        "context": exc_value.context if isinstance(exc_value, VociferousError) else None,
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
        details = (
            f"Crash Dump: {dump_path}\n\n"
            f"Traceback:\n{tb_string}"
        )

        # 4. Display Dialog
        if error_callback:
            try:
                error_callback(title, message, details)
            except Exception as callback_error:
                logger.error(f"Error callback failed: {callback_error}")
                print(f"CRITICAL: Error displaying dialog: {callback_error}", file=sys.stderr)

    sys.excepthook = exception_hook

def format_exception_for_display(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: "TracebackType | None",
) -> Tuple[str, str, str]:
    """
    Format an exception for display in the error dialog.

    Args:
        exc_type: Exception type
        exc_value: Exception instance
        exc_tb: Traceback object

    Returns:
        Tuple of (title, message, details)
    """
    error_name = exc_type.__name__
    error_message = str(exc_value) if str(exc_value) else "An unexpected error occurred"

    # Capture extra context if available
    if isinstance(exc_value, VociferousError) and exc_value.doc_ref:
        error_message += f"\n\nSee: {exc_value.doc_ref}"

    tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    tb_string = "".join(tb_lines)

    title = f"Error: {error_name}"
    message = error_message
    details = f"Traceback:\n{tb_string}"

    return title, message, details


def safe_slot(context: str = "") -> Callable:
    """
    Decorator to wrap Qt slots with exception handling.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception:
                # Use our robust logger
                exc_info = sys.exc_info()
                get_error_logger().log_exception(exc_info[0], exc_info[1], exc_info[2], context=context)
                
                # Show generic error if possible, but don't crash app
                # This could catch exceptions that happen during button clicks
                return None
        return wrapper
    return decorator


def safe_slot_silent(context: str = "") -> Callable:
    """
    Decorator to wrap Qt slots with exception handling (logging only, no propagation).
    Same as safe_slot in this implementation as safe_slot is already silent UI-wise.
    """
    return safe_slot(context)


def safe_callback(func: Callable, context: str = "") -> Callable:
    """
    Decorator to wrap standard callbacks with exception handling.
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception:
            exc_info = sys.exc_info()
            get_error_logger().log_exception(exc_info[0], exc_info[1], exc_info[2], context=context or "Callback")
            return None
    return wrapper
