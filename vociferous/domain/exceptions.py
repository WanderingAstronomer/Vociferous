"""Domain-specific exceptions for Vociferous.

This module defines custom exception types to replace generic RuntimeError and ValueError,
providing better error categorization and handling throughout the application.
"""

from __future__ import annotations


class VociferousError(Exception):
    """Base exception for all Vociferous errors."""
    pass


class EngineError(VociferousError):
    """Raised when an ASR engine encounters an error during initialization or inference."""
    pass


class AudioDecodeError(VociferousError):
    """Raised when audio decoding fails."""
    pass


class ConfigurationError(VociferousError):
    """Raised when configuration validation fails."""
    pass


class DependencyError(VociferousError):
    """Raised when a required dependency is missing."""
    pass


class AudioProcessingError(VociferousError):
    """Raised when audio processing (decode, condense, VAD) fails."""
    pass


class UnsplittableSegmentError(AudioProcessingError):
    """Raised when a single speech segment exceeds max chunk duration and cannot be split.
    
    This occurs when VAD produces a continuous speech segment longer than the
    engine's maximum input duration (e.g., >60s for Canary). The audio may need
    manual splitting or different VAD parameters.
    """
    pass
