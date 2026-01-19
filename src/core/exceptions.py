"""
Vociferous Exception Hierarchy.

These exceptions are designed to be "Agentically Self-Healing".
They carry:
1. Contextual data (variables, state)
2. References to documentation (wikis) for resolution
"""

from typing import Any, Optional


class VociferousError(Exception):
    """Base class for all application-specific errors."""

    def __init__(
        self,
        message: str,
        context: Optional[dict[str, Any]] = None,
        doc_ref: Optional[str] = None,
    ) -> None:
        """
        Initialize the error.

        Args:
            message: Human-readable error description.
            context: Dictionary of relevant variables/state at time of error.
            doc_ref: Path to relevant documentation (e.g., 'docs/wiki/Audio-Recording.md').
        """
        self.context = context or {}
        self.doc_ref = doc_ref

        # Build a rich message for the log
        base_msg = message
        if context:
            base_msg += f" | Context: {context}"
        if doc_ref:
            base_msg += f" | See: {doc_ref}"

        super().__init__(base_msg)


class AudioDeviceError(VociferousError):
    """Raised when audio input devices fail or are misconfigured."""

    def __init__(self, message: str, context: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message, context, doc_ref="docs/wiki/Audio-Recording.md")


class ModelLoadError(VociferousError):
    """Raised when the Whisper model fails to load."""

    def __init__(self, message: str, context: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message, context, doc_ref="docs/wiki/Troubleshooting.md")


class TranscriptionError(VociferousError):
    """Raised when inference fails."""

    def __init__(self, message: str, context: Optional[dict[str, Any]] = None) -> None:
        super().__init__(
            message, context, doc_ref="docs/wiki/Refinement-Architecture.md"
        )


class ConfigError(VociferousError):
    """Raised when configuration is invalid."""

    def __init__(self, message: str, context: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message, context, doc_ref="docs/wiki/Configuration-Schema.md")


class DatabaseError(VociferousError):
    """Raised when database operations fail."""

    def __init__(self, message: str, context: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message, context, doc_ref="docs/wiki/History-Storage.md")


class ConfigurationError(VociferousError):
    """Raised when configuration values are invalid or missing."""

    pass
