"""
Core utilities and base classes for Vociferous.

This module contains fundamental types and exceptions used throughout
the application.
"""

from .exceptions import (
    VociferousError,
    ConfigError,
    DatabaseError,
    ModelLoadError,
    TranscriptionError,
    AudioDeviceError,
)

__all__ = [
    "VociferousError",
    "ConfigError",
    "DatabaseError",
    "ModelLoadError",
    "TranscriptionError",
    "AudioDeviceError",
]
