"""
Vociferous Exception Hierarchy — Flattened.

Base + 3 leaves. No context dict, no doc_ref. ~15 lines.
"""


class VociferousError(Exception):
    """Base class for all application-specific errors."""
    pass


class AudioError(VociferousError):
    """Audio capture or device errors."""
    pass


class EngineError(VociferousError):
    """ASR or SLM inference engine errors."""
    pass


class ConfigError(VociferousError):
    """Configuration validation or loading errors."""
    pass
