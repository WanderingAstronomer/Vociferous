"""
TagHandlers — create, update, delete tags and assign tags to transcripts.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from src.database.db import TranscriptDB

logger = logging.getLogger(__name__)


class TagHandlers:
    """Handles tag CRUD and transcript-tag assignment intents."""

    def __init__(
        self,
        *,
        db_provider: Callable[[], TranscriptDB | None],
        event_bus_emit: Callable,
    ) -> None:
        self._db_provider = db_provider
        self._emit = event_bus_emit

    def handle_create(self, intent: Any) -> None:
        db = self._db_provider()
        if not db:
            return
        tag = db.add_tag(name=intent.name, color=intent.color)
        self._emit(
            "tag_created",
            {"id": tag.id, "name": tag.name, "color": tag.color},
        )

    def handle_update(self, intent: Any) -> None:
        db = self._db_provider()
        if not db:
            return
        existing = db.get_tag(intent.tag_id)
        if existing is None or existing.is_system:
            return
        kwargs: dict = {}
        if intent.name is not None:
            kwargs["name"] = intent.name
        if intent.color is not None:
            kwargs["color"] = intent.color
        tag = db.update_tag(intent.tag_id, **kwargs)
        if tag:
            self._emit(
                "tag_updated",
                {"id": tag.id, "name": tag.name, "color": tag.color},
            )

    def handle_delete(self, intent: Any) -> None:
        db = self._db_provider()
        if not db:
            return
        existing = db.get_tag(intent.tag_id)
        if existing is None or existing.is_system:
            return
        deleted = db.delete_tag(intent.tag_id)
        if deleted:
            self._emit("tag_deleted", {"id": intent.tag_id})

    def handle_assign_tags(self, intent: Any) -> None:
        db = self._db_provider()
        if not db:
            return
        tags = db.assign_tags(intent.transcript_id, list(intent.tag_ids))
        self._emit(
            "transcript_updated",
            {
                "id": intent.transcript_id,
                "tags": [{"id": t.id, "name": t.name, "color": t.color, "is_system": t.is_system} for t in tags],
            },
        )

    def handle_batch_toggle_tag(self, intent: Any) -> None:
        db = self._db_provider()
        if not db:
            return
        tag = db.get_tag(intent.tag_id)
        if tag is None or tag.is_system:
            return
        db.batch_toggle_tag(list(intent.transcript_ids), intent.tag_id, add=intent.add)
