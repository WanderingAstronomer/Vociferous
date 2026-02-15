"""
Intent definitions for Vociferous v4.0.

Intents are immutable frozen dataclasses representing user desires.
They carry no behavior — handlers are registered in the CommandBus.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from src.core.intents import InteractionIntent


class IntentSource(Enum):
    """Origin of an intent (for observability, not routing)."""

    CONTROLS = auto()
    NAVIGATION = auto()
    HOTKEY = auto()
    CONTEXT_MENU = auto()
    INTERNAL = auto()
    API = auto()  # New: from Litestar/WebSocket


@dataclass(frozen=True, slots=True)
class NavigateIntent(InteractionIntent):
    """Switch the active view."""

    target_view_id: str = ""
    source: IntentSource = IntentSource.NAVIGATION


@dataclass(frozen=True, slots=True)
class BeginRecordingIntent(InteractionIntent):
    """Start audio recording."""

    source: IntentSource = IntentSource.CONTROLS


@dataclass(frozen=True, slots=True)
class StopRecordingIntent(InteractionIntent):
    """Stop recording and begin transcription."""

    source: IntentSource = IntentSource.CONTROLS


@dataclass(frozen=True, slots=True)
class CancelRecordingIntent(InteractionIntent):
    """Cancel recording without transcription."""

    source: IntentSource = IntentSource.CONTROLS


@dataclass(frozen=True, slots=True)
class ToggleRecordingIntent(InteractionIntent):
    """Toggle the recording state (Start/Stop)."""

    source: IntentSource = IntentSource.HOTKEY


@dataclass(frozen=True, slots=True)
class ViewTranscriptIntent(InteractionIntent):
    """View a specific transcript."""

    transcript_id: int = 0
    source: IntentSource = IntentSource.NAVIGATION


@dataclass(frozen=True, slots=True)
class EditTranscriptIntent(InteractionIntent):
    """Enter edit mode for a transcript."""

    transcript_id: int = 0
    source: IntentSource = IntentSource.CONTROLS


@dataclass(frozen=True, slots=True)
class CommitEditsIntent(InteractionIntent):
    """Save edited transcript content as a new variant."""

    transcript_id: int = 0
    content: str = ""
    source: IntentSource = IntentSource.CONTROLS


@dataclass(frozen=True, slots=True)
class DiscardEditsIntent(InteractionIntent):
    """Discard edits and return to viewing."""

    source: IntentSource = IntentSource.CONTROLS


@dataclass(frozen=True, slots=True)
class DeleteTranscriptIntent(InteractionIntent):
    """Delete a transcript."""

    transcript_id: int = 0
    source: IntentSource = IntentSource.CONTROLS


@dataclass(frozen=True, slots=True)
class RefineTranscriptIntent(InteractionIntent):
    """Trigger SLM refinement on a transcript."""

    transcript_id: int = 0
    level: int = 2
    instructions: str = ""
    source: IntentSource = IntentSource.CONTROLS
