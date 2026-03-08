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
    HOTKEY = auto()
    INTERNAL = auto()
    API = auto()


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
class CommitEditsIntent(InteractionIntent):
    """Save edited transcript content as a new variant."""

    transcript_id: int = 0
    content: str = ""
    source: IntentSource = IntentSource.CONTROLS


@dataclass(frozen=True, slots=True)
class DeleteTranscriptIntent(InteractionIntent):
    """Delete a transcript."""

    transcript_id: int = 0
    source: IntentSource = IntentSource.CONTROLS


@dataclass(frozen=True, slots=True)
class BatchDeleteTranscriptsIntent(InteractionIntent):
    """Delete multiple transcripts in a single operation."""

    transcript_ids: tuple[int, ...] = field(default_factory=tuple)
    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class RefineTranscriptIntent(InteractionIntent):
    """Trigger SLM refinement on a transcript."""

    transcript_id: int = 0
    level: int = 2
    instructions: str = ""
    source: IntentSource = IntentSource.CONTROLS


@dataclass(frozen=True, slots=True)
class CommitRefinementIntent(InteractionIntent):
    """Persist accepted refinement text to normalized_text."""

    transcript_id: int = 0
    text: str = ""
    source: IntentSource = IntentSource.API


# --- Tag Intents ---


@dataclass(frozen=True, slots=True)
class CreateTagIntent(InteractionIntent):
    """Create a new tag."""

    name: str = ""
    color: str | None = None
    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class UpdateTagIntent(InteractionIntent):
    """Update a tag's name and/or color."""

    tag_id: int = 0
    name: str | None = None
    color: str | None = None
    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class DeleteTagIntent(InteractionIntent):
    """Delete a tag."""

    tag_id: int = 0
    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class AssignTagsIntent(InteractionIntent):
    """Set the exact tag set for a transcript (replaces existing)."""

    transcript_id: int = 0
    tag_ids: tuple[int, ...] = ()
    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class ClearTranscriptsIntent(InteractionIntent):
    """Delete all transcripts."""

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


@dataclass(frozen=True, slots=True)
class RefreshInsightIntent(InteractionIntent):
    """Force-trigger insight regeneration, bypassing TTL/count guards."""

    source: IntentSource = IntentSource.API
