"""
TranscriptHandlers — commit-edits, revert, append, and analytics-inclusion intents.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from src.core.command_bus import handles
from src.core.intents.definitions import (
    AppendToTranscriptIntent,
    CommitEditsIntent,
    RevertToRawIntent,
    SetAnalyticsInclusionIntent,
)

if TYPE_CHECKING:
    from src.database.db import TranscriptDB

logger = logging.getLogger(__name__)


class TranscriptHandlers:
    """Handles transcript mutation intents: commit edits, revert, append, analytics."""

    def __init__(
        self,
        *,
        db_provider: Callable[[], TranscriptDB | None],
        event_bus_emit: Callable,
    ) -> None:
        self._db_provider = db_provider
        self._emit = event_bus_emit

    @handles(CommitEditsIntent)
    def handle_commit_edits(self, intent: Any) -> None:
        db = self._db_provider()
        if db:
            db.update_normalized_text(intent.transcript_id, intent.content)
            self._emit(
                "transcript_updated",
                {"id": intent.transcript_id},
            )

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

    @handles(SetAnalyticsInclusionIntent)
    def handle_set_analytics_inclusion(self, intent: Any) -> None:
        """Set the include_in_analytics flag for a transcript."""
        db = self._db_provider()
        if db:
            db.set_analytics_inclusion(intent.transcript_id, intent.include)
            self._emit("transcript_updated", {"id": intent.transcript_id})
