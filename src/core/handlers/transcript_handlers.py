"""
TranscriptHandlers — commit-edits, revert, append, and analytics-inclusion intents.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from src.core.command_bus import handles
from src.core.intents.definitions import (
    AppendToTranscriptIntent,
    BatchDeleteTranscriptsIntent,
    ClearAllTranscriptsIntent,
    CommitEditsIntent,
    DeleteTranscriptIntent,
    RevertToRawIntent,
    SetAnalyticsInclusionIntent,
)

if TYPE_CHECKING:
    from src.core.settings import VociferousSettings
    from src.database.db import TranscriptDB

logger = logging.getLogger(__name__)


class TranscriptHandlers:
    """Handles transcript mutation intents: commit edits, revert, append, analytics."""

    def __init__(
        self,
        *,
        db_provider: Callable[[], TranscriptDB | None],
        event_bus_emit: Callable,
        settings_provider: Callable[[], VociferousSettings],
        on_settings_updated: Callable[[VociferousSettings], None],
        insight_manager_provider: Callable[[], Any] = lambda: None,
    ) -> None:
        self._db_provider = db_provider
        self._emit = event_bus_emit
        self._settings_provider = settings_provider
        self._on_settings_updated = on_settings_updated
        self._insight_manager_provider = insight_manager_provider

    def _mark_insight_dirty(self, reason: str) -> None:
        insight_manager = self._insight_manager_provider()
        if insight_manager is not None:
            insight_manager.mark_dirty(reason)

    def _clear_insight_cache(self, reason: str) -> None:
        insight_manager = self._insight_manager_provider()
        if insight_manager is not None:
            insight_manager.clear_cache(reason)

    def _clear_default_prompt_if_deleted(self, transcript_id: int) -> None:
        from src.core.settings import update_settings

        settings = self._settings_provider()
        if settings.refinement.default_prompt_transcript_id != transcript_id:
            return
        new_settings = update_settings(refinement={"default_prompt_transcript_id": None})
        self._on_settings_updated(new_settings)
        self._emit("config_updated", new_settings.model_dump())

    @handles(CommitEditsIntent)
    def handle_commit_edits(self, intent: Any) -> None:
        db = self._db_provider()
        if db:
            db.update_normalized_text(intent.transcript_id, intent.content)
            self._emit(
                "transcript_updated",
                {"id": intent.transcript_id},
            )
            self._mark_insight_dirty("transcript_edited")

    @handles(RevertToRawIntent)
    def handle_revert_to_raw(self, intent: Any) -> None:
        """Clear normalized_text and remove the Refined system tag."""
        db = self._db_provider()
        if db:
            db.update_normalized_text(intent.transcript_id, "")
            db.remove_system_tag_from_transcript(intent.transcript_id, "Refined")
            self._emit(
                "transcript_updated",
                {"id": intent.transcript_id},
            )
            self._mark_insight_dirty("transcript_reverted")

    @handles(DeleteTranscriptIntent)
    def handle_delete_transcript(self, intent: Any) -> dict[str, bool]:
        db = self._db_provider()
        if not db:
            return {"deleted": False}
        transcript = db.get_transcript(intent.transcript_id)
        if transcript is None or transcript.is_protected:
            return {"deleted": False}
        deleted = db.delete_transcript(intent.transcript_id)
        if deleted:
            self._clear_default_prompt_if_deleted(intent.transcript_id)
            self._emit("transcript_deleted", {"id": intent.transcript_id})
            self._mark_insight_dirty("transcript_deleted")
        return {"deleted": bool(deleted)}

    @handles(BatchDeleteTranscriptsIntent)
    def handle_batch_delete_transcripts(self, intent: Any) -> dict[str, int]:
        db = self._db_provider()
        ids = list(intent.transcript_ids)
        if not db or not ids:
            return {"deleted": 0}
        default_prompt_id = self._settings_provider().refinement.default_prompt_transcript_id
        default_prompt = db.get_transcript(default_prompt_id) if default_prompt_id in ids else None
        count = db.batch_delete_transcripts(ids)
        if count and default_prompt_id in ids and (default_prompt is None or not default_prompt.is_protected):
            self._clear_default_prompt_if_deleted(default_prompt_id)
        if count:
            self._emit("transcripts_batch_deleted", {"ids": ids, "count": count})
            self._mark_insight_dirty("transcripts_deleted")
        return {"deleted": count}

    @handles(ClearAllTranscriptsIntent)
    def handle_clear_all_transcripts(self, intent: Any) -> dict[str, int]:
        db = self._db_provider()
        if not db:
            return {"deleted": 0}
        default_prompt_id = self._settings_provider().refinement.default_prompt_transcript_id
        default_prompt = db.get_transcript(default_prompt_id) if default_prompt_id is not None else None
        deleted = db.clear_all_transcripts()
        if deleted and default_prompt_id is not None and (default_prompt is None or not default_prompt.is_protected):
            self._clear_default_prompt_if_deleted(default_prompt_id)
        if deleted:
            self._emit("transcripts_cleared", {"count": deleted})
            self._clear_insight_cache("transcripts_cleared")
        return {"deleted": deleted}

    @handles(AppendToTranscriptIntent)
    def handle_append(self, intent: Any) -> None:
        """Append a new recording segment to an existing transcript."""
        db = self._db_provider()
        if db:
            root_id = db.append_to_transcript(
                intent.transcript_id,
                intent.source_transcript_id,
            )
            if root_id is not None:
                self._emit("transcript_updated", {"id": root_id})
                self._mark_insight_dirty("transcript_appended")

    @handles(SetAnalyticsInclusionIntent)
    def handle_set_analytics_inclusion(self, intent: Any) -> None:
        """Set the include_in_analytics flag for a transcript."""
        db = self._db_provider()
        if db:
            db.set_analytics_inclusion(intent.transcript_id, intent.include)
            self._emit("transcript_updated", {"id": intent.transcript_id})
            self._mark_insight_dirty("analytics_inclusion_changed")
