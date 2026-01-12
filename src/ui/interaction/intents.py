"""
Intent definitions for interaction layer.

Intents are immutable tokens representing user desires. They do not
guarantee execution; they name what the user wants to happen. The
workspace interprets intents and decides whether/how to fulfill them.

Each intent is a frozen dataclass with no behavior. Intents depend on
nothing in ui.components; they are pure data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class IntentSource(Enum):
    """Origin of an intent (for observability, not routing)."""

    CONTROLS = auto()  # Workspace control buttons
    SIDEBAR = auto()  # Sidebar transcript list
    HOTKEY = auto()  # Global hotkey
    CONTEXT_MENU = auto()  # Right-click menu
    INTERNAL = auto()  # System-initiated (e.g., post-transcription)


@dataclass(frozen=True, slots=True)
class InteractionIntent:
    """
    Base class for semantic interaction intents.

    An intent represents the user's desire to perform an action.
    It does not guarantee execution.
    """

    source: IntentSource = IntentSource.CONTROLS


@dataclass(frozen=True, slots=True)
class BeginRecordingIntent(InteractionIntent):
    """User desires to start audio recording."""

    pass


@dataclass(frozen=True, slots=True)
class StopRecordingIntent(InteractionIntent):
    """User desires to stop audio recording and begin transcription."""

    pass


@dataclass(frozen=True, slots=True)
class CancelRecordingIntent(InteractionIntent):
    """User desires to cancel recording without transcription."""

    pass


@dataclass(frozen=True, slots=True)
class ViewTranscriptIntent(InteractionIntent):
    """User desires to view a specific transcript.

    Phase 5: Now carries both timestamp and text for _apply_view_transcript.
    """

    timestamp: str = (
        ""  # Transcript identifier (required but has default for inheritance)
    )
    text: str = ""  # Transcript content (required but has default for inheritance)
    source: IntentSource = field(default=IntentSource.SIDEBAR)
    variants: list = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class EditTranscriptIntent(InteractionIntent):
    """User desires to enter edit mode for the current transcript."""

    pass


@dataclass(frozen=True, slots=True)
class CommitEditsIntent(InteractionIntent):
    """User desires to save edited transcript content."""

    content: str = ""  # Edited text to save (required but has default for inheritance)
    source: IntentSource = field(default=IntentSource.CONTROLS)


@dataclass(frozen=True, slots=True)
class DiscardEditsIntent(InteractionIntent):
    """User desires to discard edits and return to viewing."""

    pass


@dataclass(frozen=True, slots=True)
class DeleteTranscriptIntent(InteractionIntent):
    """User desires to delete the current transcript."""

    timestamp: str = (
        ""  # Transcript identifier (required but has default for inheritance)
    )
    source: IntentSource = field(default=IntentSource.CONTROLS)
