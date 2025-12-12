"""Application-layer orchestration."""

import logging
import structlog

from .workflow import transcribe_file_workflow, transcribe_workflow  # noqa: F401
from .progress import (  # noqa: F401
    TranscriptionProgress,
    ProgressTracker,
    RichProgressTracker,
    SimpleProgressTracker,
    NullProgressTracker,
    transcription_progress,
)

def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # Silence verbose engine/VAD progress logs that write to stdout
    logging.getLogger("whisper").setLevel(logging.ERROR)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

__all__ = [
    "transcribe_workflow",
    "transcribe_file_workflow",
    "configure_logging",
    "TranscriptionProgress",
    "ProgressTracker",
    "RichProgressTracker",
    "SimpleProgressTracker", 
    "NullProgressTracker",
    "transcription_progress",
]

