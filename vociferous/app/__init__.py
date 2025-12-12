"""Application-layer orchestration."""

import logging

import structlog

from .batch import (
    BatchResult,
    BatchStats,
    BatchTranscriptionRunner,
    compute_batch_stats,
    generate_combined_transcript,
)
from .progress import (
    NullProgressTracker,
    ProgressTracker,
    RichProgressTracker,
    SimpleProgressTracker,
    TranscriptionProgress,
    transcription_progress,
)
from .workflow import transcribe_file_workflow, transcribe_workflow


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    # Silence verbose third-party logging that pollutes Rich progress display
    # These libraries produce INFO/WARNING messages during model loading
    noisy_loggers = [
        "whisper",           # OpenAI Whisper
        "nemo",              # NVIDIA NeMo framework
        "nemo_logging",      # NeMo internal logging
        "nemo.collections",  # NeMo collections
        "transformers",      # Hugging Face Transformers
        "huggingface_hub",   # HF Hub downloads
        "pytorch_lightning", # Lightning framework
        "lightning",         # Lightning framework
        "peft",              # LoRA adapters
        "onelogger",         # NeMo OneLogger
        "numexpr",           # NumExpr threading
        "urllib3",           # HTTP client
        "filelock",          # File locking
        "tqdm",              # Progress bars (we use Rich instead)
    ]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.ERROR)
    
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
    "BatchResult",
    "BatchStats",
    "BatchTranscriptionRunner",
    "NullProgressTracker",
    "ProgressTracker",
    "RichProgressTracker",
    "SimpleProgressTracker",
    "TranscriptionProgress",
    "compute_batch_stats",
    "configure_logging",
    "generate_combined_transcript",
    "transcribe_file_workflow",
    "transcribe_workflow",
    "transcription_progress",
]

