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
from collections.abc import Mapping, Sequence
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

_SENSITIVE_KEY_PARTS = ("api_key", "apikey", "authorization", "bearer", "password", "secret", "token")


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            redacted[key_text] = "<redacted>" if _is_sensitive_key(key_text) else _redact(item)
        return redacted
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_redact(item) for item in value]
    return value


def _json_for_log(value: Any) -> str:
    return json.dumps(_redact(value), ensure_ascii=False, sort_keys=True, default=str)


def _display_logger_name(name: str) -> str:
    return name.removeprefix("src.")


def _runtime_label(runtime: Mapping[str, Any]) -> str:
    provider = runtime.get("provider", "unknown")
    model = runtime.get("model_id") or runtime.get("requested_model_id") or "unset"
    device = runtime.get("resolved_device") or runtime.get("device_preference") or "unknown"
    key_state = "key=yes" if runtime.get("has_api_key") else "key=no"
    return f"{provider}/{model} [{device}, {key_state}]"


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
    app = snapshot["app"]
    platform_info = snapshot["platform"]
    python_info = snapshot["python"]
    cpu = snapshot["cpu"]
    gpu = snapshot["gpu"]
    transcript_info = snapshot.get("transcripts", {})
    logger.info(
        "Support snapshot: app=%s python=%s platform=%s-%s cpu=%s cores=%s/%s transcripts=%s",
        app.get("version"),
        python_info.get("version"),
        platform_info.get("system"),
        platform_info.get("release"),
        cpu.get("model"),
        cpu.get("physical_cores", "?"),
        cpu.get("logical_cores", "?"),
        transcript_info.get("count", "n/a"),
    )
    logger.info(
        "Runtime snapshot: asr=%s slm=%s gpu=%s devices=%s vram=%s/%s MB",
        _runtime_label(snapshot["asr"]),
        _runtime_label(snapshot["slm"]),
        "cuda" if gpu.get("cuda_available") else "unavailable",
        gpu.get("cuda_device_count", 0),
        gpu.get("vram_free_mb", "?"),
        gpu.get("vram_total_mb", "?"),
    )
    logger.debug("Support snapshot detail", extra={"context": snapshot})


class AgentFriendlyFormatter(logging.Formatter):
    """
    Formatter that produces structured JSON or rich text suitable for Agents.
    """

    def __init__(self, structured: bool = False):
        self.structured = structured
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        context = getattr(record, "context", None)
        if self.structured:
            log_entry = {
                "timestamp": self.formatTime(record),
                "level": record.levelname,
                "logger": _display_logger_name(record.name),
                "message": record.getMessage(),
                "file": record.pathname,
                "line": record.lineno,
            }
            if record.exc_info:
                log_entry["exception"] = self.formatException(record.exc_info)
            if context is not None:
                log_entry["context"] = _redact(context)

            return json.dumps(log_entry, ensure_ascii=False, default=str)
        else:
            # Rich text format
            timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
            logger_name = _display_logger_name(record.name)
            msg = f"{timestamp} | {record.levelname:<7} | {logger_name}:{record.lineno} | {record.getMessage()}"
            if context is not None:
                msg += f" | context={_json_for_log(context)}"
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
            "httpcore.connection",
            "httpcore.http11",
            "huggingface_hub.utils._http",
            "huggingface_hub.file_download",
            "huggingface_hub.repocard",
            "multipart.multipart",
            "PIL",
            "numba",
            "matplotlib",
        ):
            logging.getLogger(noisy_logger).setLevel(logging.WARNING)

        logger.info(
            "Logging ready: console=%s file=DEBUG structured=%s path=%s",
            logging.getLevelName(console_level),
            structured,
            LOG_FILE,
        )

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
