"""
Centralized Logging Manager.

Handles the configuration, rotation, and formatting of application logs.
"""

from __future__ import annotations

import json
import logging
import sys
from logging.handlers import RotatingFileHandler

from src.core.exceptions import ConfigError
from src.core.resource_manager import ResourceManager

# Log file configuration
LOG_DIR = ResourceManager.get_user_log_dir()
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

            settings = get_settings()
            console_level = getattr(logging, settings.logging.level.upper(), logging.INFO)
            enable_console = settings.logging.console_echo
            structured = settings.logging.structured_output
        except (RuntimeError, ImportError, ConfigError):
            console_level = logging.INFO
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
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            # Fall back to stderr if file logging fails
            sys.stderr.write(f"Warning: Could not set up file logging: {e}\n")

        # Console handler
        if enable_console:
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(console_level)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)

        # Silence chatty third-party loggers that are not useful at INFO level.
        # httpx logs every HTTP request; huggingface_hub logs each file HEAD/GET
        # during snapshot_download(). Both are noise unless actively debugging.
        for noisy_logger in (
            "httpx",
            "httpcore",
            "huggingface_hub.utils._http",
            "huggingface_hub.file_download",
            "huggingface_hub.repocard",
        ):
            logging.getLogger(noisy_logger).setLevel(logging.WARNING)

        logger.info(
            "LogManager initialized. Console level: %s, file level: DEBUG, Structured: %s",
            console_level,
            structured,
        )
        logger.info("Log file: %s", LOG_FILE)

    def set_console_level(self, level: int) -> None:
        """Override the console handler's log level (e.g. for --verbose flag)."""
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, RotatingFileHandler):
                handler.setLevel(level)
                logger.debug("Console log level set to %s", logging.getLevelName(level))
                return


def setup_logging() -> LogManager:
    """Convenience function to initialize logging at startup."""
    return LogManager()
