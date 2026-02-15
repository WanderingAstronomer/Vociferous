"""
Centralized Logging Manager.

Handles the configuration, rotation, and formatting of application logs.
Moved from src.ui.utils.error_handler to core to decouple logging from UI.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING

from src.core.resource_manager import ResourceManager

if TYPE_CHECKING:
    from types import TracebackType


# Log file configuration
LOG_DIR = ResourceManager.get_user_data_dir() / "logs"
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


class LogManager:
    """
    Centralized Log Manager.

    Handles logging configuration, file rotation, and structured output.
    Designated singleton for all logging operations.
    """

    _instance: "LogManager | None" = None
    _initialized: bool = False

    def __new__(cls) -> "LogManager":
        """Singleton pattern for global log manager."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the log manager (only once)."""
        if LogManager._initialized:
            return
        LogManager._initialized = True
        self.configure_logging()

    def configure_logging(self) -> None:
        """Configure file and console logging handlers based on config."""
        # Ensure log directory exists
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        # Ensure crash dump directory exists (managed here for consistency)
        CRASH_DUMP_DIR.mkdir(parents=True, exist_ok=True)

        # Get settings (graceful fallback if not yet initialized)
        try:
            from src.core.settings import get_settings
            s = get_settings()
            log_level = getattr(logging, s.logging.level.upper(), logging.INFO)
            enable_console = s.logging.console_echo
            structured = s.logging.structured_output
        except (RuntimeError, ImportError):
            log_level = logging.INFO
            enable_console = True
            structured = False

        # Root logger configuration
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)  # capture everything, handlers filter

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
            sys.stderr.write(f"Warning: Could not set up file logging: {e}\n")

        # Console handler
        if enable_console:
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(log_level)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)

        logger.info(
            f"LogManager initialized. Level: {log_level}, Structured: {structured}"
        )
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

        extra = {}

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
            subprocess.Popen(
                ["xdg-open", target],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
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


def setup_logging() -> LogManager:
    """Convenience function to initialize logging at startup."""
    return LogManager()
