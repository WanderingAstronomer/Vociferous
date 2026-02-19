"""
Intent definitions for Vociferous v4.0.

Intents are immutable frozen dataclasses representing user desires.
They carry no behavior — handlers are registered in the CommandBus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass(frozen=True, slots=True)
class CreateProjectIntent(InteractionIntent):
    """Create a new project."""

    name: str = ""
    color: str | None = None
    parent_id: int | None = None
    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class DeleteProjectIntent(InteractionIntent):
    """Delete a project."""

    project_id: int = 0
    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class UpdateProjectIntent(InteractionIntent):
    """Update a project's name, color, or parent."""

    project_id: int = 0
    name: str | None = None
    color: str | None = None
    parent_id: int | None = None
    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class AssignProjectIntent(InteractionIntent):
    """Assign (or unassign) a transcript to a project."""

    transcript_id: int = 0
    project_id: int | None = None
    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class ClearTranscriptsIntent(InteractionIntent):
    """Delete all transcripts."""

    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class DeleteTranscriptVariantIntent(InteractionIntent):
    """Delete a specific variant of a transcript."""

    transcript_id: int = 0
    variant_id: int = 0
    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class UpdateConfigIntent(InteractionIntent):
    """Update application configuration settings."""

    settings: dict = field(default_factory=dict)
    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class RenameTranscriptIntent(InteractionIntent):
    """Manually rename a transcript (set display_name)."""

    transcript_id: int = 0
    title: str = ""
    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class BatchRetitleIntent(InteractionIntent):
    """Trigger batch retitling of all untitled transcripts via SLM."""

    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class RetitleTranscriptIntent(InteractionIntent):
    """Re-generate the SLM title for a single transcript."""

    transcript_id: int = 0
    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class RestartEngineIntent(InteractionIntent):
    """Restart ASR + SLM engine models."""

    source: IntentSource = IntentSource.INTERNAL
