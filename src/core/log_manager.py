"""
Centralized Logging Manager.

Handles the configuration, rotation, and formatting of application logs.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import sys
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING, Any

from src.core.constants import APP_VERSION
from src.core.cuda_runtime import detect_cuda_runtime
from src.core.exceptions import ConfigError
from src.core.resource_manager import ResourceManager

if TYPE_CHECKING:
    from src.core.settings import VociferousSettings

# Log file configuration
LOG_DIR = ResourceManager.get_user_log_dir()
LOG_FILE = LOG_DIR / "vociferous.log"
CRASH_DUMP_DIR = LOG_DIR / "crash_dumps"
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 3  # Keep 3 rotated log files

# Module-level logger
logger = logging.getLogger(__name__)


def _detect_cpu_details() -> dict[str, Any]:
    """Return best-effort CPU details without hard depending on psutil."""
    processor = platform.processor() or platform.uname().processor or ""

    if not processor and platform.system() == "Linux":
        try:
            with open("/proc/cpuinfo", encoding="utf-8") as cpuinfo:
                for line in cpuinfo:
                    if line.lower().startswith("model name"):
                        processor = line.split(":", 1)[1].strip()
                        break
        except OSError:
            pass

    details: dict[str, Any] = {
        "model": processor or platform.machine(),
        "machine": platform.machine(),
        "logical_cores": os.cpu_count() or 0,
    }

    try:
        import psutil

        physical = psutil.cpu_count(logical=False)
        if physical is not None:
            details["physical_cores"] = physical
    except Exception:
        pass

    return details


def build_support_diagnostics_snapshot(
    settings: "VociferousSettings",
    *,
    transcript_count: int | None = None,
) -> dict[str, Any]:
    """Collect a support-safe startup snapshot for persistent logs."""
    from src.services.slm_runtime import describe_slm_runtime
    from src.services.transcription_service import describe_asr_runtime

    cuda_status = detect_cuda_runtime()
    snapshot: dict[str, Any] = {
        "app": {
            "version": APP_VERSION,
            "log_file": str(LOG_FILE),
            "log_dir": str(LOG_DIR),
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        "cpu": _detect_cpu_details(),
        "gpu": {
            "driver_detected": cuda_status.driver_detected,
            "cuda_available": cuda_status.cuda_available,
            "cuda_device_count": cuda_status.cuda_device_count,
            "gpu_name": cuda_status.gpu_name,
            "vram_total_mb": cuda_status.vram_total_mb,
            "vram_free_mb": cuda_status.vram_free_mb,
            "detail": cuda_status.detail,
        },
        "asr": describe_asr_runtime(settings, cuda_status=cuda_status),
        "slm": describe_slm_runtime(settings, cuda_status=cuda_status),
    }
    if transcript_count is not None:
        snapshot["transcripts"] = {"count": transcript_count}
    return snapshot


def log_support_diagnostics_snapshot(settings: "VociferousSettings", *, transcript_count: int | None = None) -> None:
    """Emit a one-shot diagnostics snapshot to the persistent log."""
    snapshot = build_support_diagnostics_snapshot(settings, transcript_count=transcript_count)
    logger.info("Support diagnostics snapshot", extra={"context": snapshot})


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
