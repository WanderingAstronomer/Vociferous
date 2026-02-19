"""
TranscriptHandlers — delete, clear, and commit-edits intents.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from src.database.db import TranscriptDB

logger = logging.getLogger(__name__)


class TranscriptHandlers:
    """Handles transcript mutation intents: delete, clear, and commit edits."""

    def __init__(
        self,
        *,
        db_provider: Callable[[], TranscriptDB | None],
        event_bus_emit: Callable,
    ) -> None:
        self._db_provider = db_provider
        self._emit = event_bus_emit

    def handle_delete(self, intent: Any) -> None:
        db = self._db_provider()
        if db:
            db.delete_transcript(intent.transcript_id)
            self._emit("transcript_deleted", {"id": intent.transcript_id})

    def handle_delete_variant(self, intent: Any) -> None:
        db = self._db_provider()
        if db:
            deleted = db.delete_variant(intent.transcript_id, intent.variant_id)
            if deleted:
                t = db.get_transcript(intent.transcript_id)
                if t:
                    self._emit("transcript_updated", {"id": intent.transcript_id})

    def handle_clear(self, intent: Any) -> None:
        db = self._db_provider()
        if db:
            count = db.clear_all_transcripts()
            logger.info("Cleared all transcripts: %d deleted", count)
            self._emit("transcripts_cleared", {"count": count})

    def handle_commit_edits(self, intent: Any) -> None:
        db = self._db_provider()
        if db:
            variant = db.add_variant(intent.transcript_id, "user_edit", intent.content, set_current=True)
            self._emit(
                "transcript_updated",
                {"id": intent.transcript_id, "variant_id": variant.id},
            )

    def handle_rename(self, intent: Any) -> None:
        """Set or update a transcript's display_name."""
        db = self._db_provider()
        if db:
            title = (intent.title or "").strip()
            if not title:
                return
            db.update_display_name(intent.transcript_id, title)
            self._emit("transcript_updated", {"id": intent.transcript_id})
