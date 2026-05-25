"""Vociferous database dataclass models.

These dataclasses describe rows materialised from the SQLite tables managed
by ``src.database.db``. They live in their own module so callers can
import the models without pulling in the full ``TranscriptDB`` class and
its sqlite connection machinery.

For backwards compatibility, all symbols here are re-exported from
``src.database.db``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now() -> str:
    """ISO-format UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class Tag:
    id: int | None = None
    name: str = ""
    color: str | None = None
    is_system: bool = False
    created_at: str = ""

    def to_dict(self) -> dict:
        """JSON-serializable representation used by API responses and WS events."""
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "is_system": self.is_system,
        }


@dataclass(slots=True)
class Transcript:
    id: int | None = None
    timestamp: str = ""
    raw_text: str = ""
    normalized_text: str = ""
    display_name: str | None = None
    duration_ms: int = 0
    speech_duration_ms: int = 0
    transcription_time_ms: int = 0
    refinement_time_ms: int = 0
    transcription_provider: str = ""
    transcription_model_id: str = ""
    transcription_resolved_device: str = ""
    transcription_compute_type: str = ""
    transcription_cpu_threads: int = 0
    transcription_prompt_text: str = ""
    transcription_prompt_chars: int = 0
    transcription_prompt_words: int = 0
    retranscription_count: int = 0
    last_retranscription_at: str = ""
    last_retranscription_time_ms: int = 0
    last_retranscription_provider: str = ""
    last_retranscription_model_id: str = ""
    last_retranscription_resolved_device: str = ""
    last_retranscription_compute_type: str = ""
    last_retranscription_cpu_threads: int = 0
    last_retranscription_prompt_text: str = ""
    last_retranscription_prompt_chars: int = 0
    last_retranscription_prompt_words: int = 0
    refinement_provider: str = ""
    refinement_model_id: str = ""
    refinement_resolved_device: str = ""
    refinement_compute_type: str = ""
    refinement_cpu_threads: int = 0
    refinement_gpu_layers: int = 0
    refinement_use_thinking: bool = False
    refinement_prompt_text: str = ""
    refinement_prompt_chars: int = 0
    refinement_prompt_words: int = 0
    refinement_prompt_tokens: int = 0
    refinement_completion_tokens: int = 0
    refinement_total_tokens: int = 0
    created_at: str = ""
    include_in_analytics: bool = True
    has_audio_cached: bool = False
    is_protected: bool = False
    compound_root_id: int | None = None
    compound_order: int | None = None
    # Populated by joins, not stored in transcripts table
    tags: list[Tag] = field(default_factory=list)

    @property
    def text(self) -> str:
        """Current display text: normalized_text (edited/refined) or raw_text."""
        return self.normalized_text or self.raw_text

    def to_dict(self) -> dict:
        """JSON-serializable representation used by API responses."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "text": self.text,
            "display_name": self.display_name,
            "duration_ms": self.duration_ms,
            "speech_duration_ms": self.speech_duration_ms,
            "transcription_time_ms": self.transcription_time_ms,
            "refinement_time_ms": self.refinement_time_ms,
            "transcription_provider": self.transcription_provider,
            "transcription_model_id": self.transcription_model_id,
            "transcription_resolved_device": self.transcription_resolved_device,
            "transcription_compute_type": self.transcription_compute_type,
            "transcription_cpu_threads": self.transcription_cpu_threads,
            "transcription_prompt_text": self.transcription_prompt_text,
            "transcription_prompt_chars": self.transcription_prompt_chars,
            "transcription_prompt_words": self.transcription_prompt_words,
            "retranscription_count": self.retranscription_count,
            "last_retranscription_at": self.last_retranscription_at,
            "last_retranscription_time_ms": self.last_retranscription_time_ms,
            "last_retranscription_provider": self.last_retranscription_provider,
            "last_retranscription_model_id": self.last_retranscription_model_id,
            "last_retranscription_resolved_device": self.last_retranscription_resolved_device,
            "last_retranscription_compute_type": self.last_retranscription_compute_type,
            "last_retranscription_cpu_threads": self.last_retranscription_cpu_threads,
            "last_retranscription_prompt_text": self.last_retranscription_prompt_text,
            "last_retranscription_prompt_chars": self.last_retranscription_prompt_chars,
            "last_retranscription_prompt_words": self.last_retranscription_prompt_words,
            "refinement_provider": self.refinement_provider,
            "refinement_model_id": self.refinement_model_id,
            "refinement_resolved_device": self.refinement_resolved_device,
            "refinement_compute_type": self.refinement_compute_type,
            "refinement_cpu_threads": self.refinement_cpu_threads,
            "refinement_gpu_layers": self.refinement_gpu_layers,
            "refinement_use_thinking": self.refinement_use_thinking,
            "refinement_prompt_text": self.refinement_prompt_text,
            "refinement_prompt_chars": self.refinement_prompt_chars,
            "refinement_prompt_words": self.refinement_prompt_words,
            "refinement_prompt_tokens": self.refinement_prompt_tokens,
            "refinement_completion_tokens": self.refinement_completion_tokens,
            "refinement_total_tokens": self.refinement_total_tokens,
            "created_at": self.created_at,
            "include_in_analytics": self.include_in_analytics,
            "has_audio_cached": self.has_audio_cached,
            "is_protected": self.is_protected,
            "tags": [tag.to_dict() for tag in self.tags],
        }


@dataclass(slots=True)
class RecordingSessionRecord:
    id: str
    status: str
    started_at: str
    updated_at: str
    finalized_at: str | None
    sample_rate: int
    channels: int
    sample_width_bytes: int
    duration_ms: int
    frame_count: int
    byte_count: int
    last_durable_chunk: int
    audio_path: str
    encrypted: bool = False
    encryption_key_id: str | None = None
    transcript_id: int | None = None
    failure_reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "finalized_at": self.finalized_at,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "sample_width_bytes": self.sample_width_bytes,
            "duration_ms": self.duration_ms,
            "frame_count": self.frame_count,
            "byte_count": self.byte_count,
            "last_durable_chunk": self.last_durable_chunk,
            "audio_path": self.audio_path,
            "encrypted": self.encrypted,
            "encryption_key_id": self.encryption_key_id,
            "transcript_id": self.transcript_id,
            "failure_reason": self.failure_reason,
        }


@dataclass(slots=True)
class AudioAsset:
    id: int | None = None
    recording_id: str | None = None
    transcript_id: int | None = None
    role: str = "transcript_source"
    path: str = ""
    duration_ms: int = 0
    size_bytes: int = 0
    encrypted: bool = False
    pinned: bool = False
    retain_until: str | None = None
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "recording_id": self.recording_id,
            "transcript_id": self.transcript_id,
            "role": self.role,
            "path": self.path,
            "duration_ms": self.duration_ms,
            "size_bytes": self.size_bytes,
            "encrypted": self.encrypted,
            "pinned": self.pinned,
            "retain_until": self.retain_until,
            "created_at": self.created_at,
        }


__all__ = ["AudioAsset", "RecordingSessionRecord", "Tag", "Transcript", "utc_now"]
