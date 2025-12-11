"""Sink implementations for transcription output."""

from .sinks import (  # noqa: F401
    ClipboardSink,
    CompositeSink,
    FileSink,
    StdoutSink,
)
from .polishing import RefiningSink  # noqa: F401

__all__ = [
    "ClipboardSink",
    "CompositeSink",
    "FileSink",
    "StdoutSink",
    "RefiningSink",
]
