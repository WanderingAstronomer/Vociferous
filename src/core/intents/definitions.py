"""
Intent definitions for Vociferous v4.0.

Intents are immutable frozen dataclasses representing user desires.
They carry no behavior — handlers are registered in the CommandBus.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum, auto
from types import MappingProxyType
from typing import Any

from src.core.intents import InteractionIntent


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze_value(item) for item in value)
    return value


def thaw_value(value: Any) -> Any:
    """Return plain mutable containers for code that needs to merge intent payloads."""
    if isinstance(value, Mapping):
        return {key: thaw_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_value(item) for item in value]
    return value


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
class RevertToRawIntent(InteractionIntent):
    """Revert a transcript to its original raw text, clearing edits/refinement."""

    transcript_id: int = 0
    source: IntentSource = IntentSource.CONTROLS


@dataclass(frozen=True, slots=True)
class DeleteTranscriptIntent(InteractionIntent):
    """Delete a single transcript."""

    transcript_id: int = 0
    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class BatchDeleteTranscriptsIntent(InteractionIntent):
    """Delete multiple transcripts."""

    transcript_ids: tuple[int, ...] = field(default_factory=tuple)
    source: IntentSource = IntentSource.API

    def __post_init__(self) -> None:
        object.__setattr__(self, "transcript_ids", tuple(self.transcript_ids))


@dataclass(frozen=True, slots=True)
class ClearAllTranscriptsIntent(InteractionIntent):
    """Delete all non-protected transcripts."""

    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class DeleteTagIntent(InteractionIntent):
    """Delete a user tag."""

    tag_id: int = 0
    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class RefineTranscriptIntent(InteractionIntent):
    """Trigger SLM refinement on a transcript."""

    transcript_id: int = 0
    level: int = 2
    instructions: str = ""
    prompt_transcript_id: int | None = None
    source: IntentSource = IntentSource.CONTROLS

    def __post_init__(self) -> None:
        if not isinstance(self.level, int) or not (1 <= self.level <= 5):
            raise ValueError("level must be an integer between 1 and 5")


@dataclass(frozen=True, slots=True)
class CommitRefinementIntent(InteractionIntent):
    """Persist accepted refinement text to normalized_text."""

    transcript_id: int = 0
    text: str = ""
    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class BulkRefineTranscriptsIntent(InteractionIntent):
    """Trigger SLM refinement on multiple transcripts sequentially (auto-commit)."""

    transcript_ids: tuple[int, ...] = field(default_factory=tuple)
    level: int = 2
    instructions: str = ""
    skip_refined: bool = True
    source: IntentSource = IntentSource.API

    def __post_init__(self) -> None:
        object.__setattr__(self, "transcript_ids", tuple(self.transcript_ids))
        if not isinstance(self.level, int) or not (1 <= self.level <= 5):
            raise ValueError("level must be an integer between 1 and 5")


@dataclass(frozen=True, slots=True)
class CancelBulkRefinementIntent(InteractionIntent):
    """Cancel an in-progress bulk refinement between transcript boundaries."""

    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class UpdateConfigIntent(InteractionIntent):
    """Update application configuration settings."""

    settings: Mapping[str, Any] = field(default_factory=dict)
    source: IntentSource = IntentSource.API

    def __post_init__(self) -> None:
        object.__setattr__(self, "settings", _freeze_value(self.settings))


@dataclass(frozen=True, slots=True)
class SetAnalyticsInclusionIntent(InteractionIntent):
    """Set the include_in_analytics flag for a transcript."""

    transcript_id: int = 0
    include: bool = True
    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class AppendToTranscriptIntent(InteractionIntent):
    """Append a new recording segment's text to an existing transcript."""

    transcript_id: int = 0
    source_transcript_id: int = 0
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
class ImportAudioFileIntent(InteractionIntent):
    """Import an audio file from disk for transcription."""

    file_path: str = ""
    cleanup_source: bool = False
    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class RetranscribeIntent(InteractionIntent):
    """Re-transcribe a transcript from its cached audio."""

    transcript_id: int = 0
    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class TranscribeRecoveredRecordingIntent(InteractionIntent):
    """Transcribe a crash-recovered durable recording."""

    recording_id: str = ""
    source: IntentSource = IntentSource.API


@dataclass(frozen=True, slots=True)
class DeleteRecoveredRecordingIntent(InteractionIntent):
    """Delete a crash-recovered durable recording."""

    recording_id: str = ""
    source: IntentSource = IntentSource.API
