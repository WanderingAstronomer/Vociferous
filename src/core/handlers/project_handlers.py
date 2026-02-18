"""
ProjectHandlers — create, update, delete, and assign-project intents.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from src.database.db import TranscriptDB

logger = logging.getLogger(__name__)


class ProjectHandlers:
    """Handles project CRUD and transcript-assignment intents."""

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
        project = db.add_project(
            name=intent.name,
            color=intent.color,
            parent_id=intent.parent_id,
        )
        self._emit(
            "project_created",
            {
                "id": project.id,
                "name": project.name,
                "color": project.color,
                "parent_id": project.parent_id,
            },
        )

    def handle_update(self, intent: Any) -> None:
        db = self._db_provider()
        if not db:
            return
        kwargs: dict = {}
        if intent.name is not None:
            kwargs["name"] = intent.name
        if intent.color is not None:
            kwargs["color"] = intent.color
        # parent_id is passed through as-is (None means move to root)
        kwargs["parent_id"] = intent.parent_id
        project = db.update_project(intent.project_id, **kwargs)
        if project:
            self._emit(
                "project_updated",
                {
                    "id": project.id,
                    "name": project.name,
                    "color": project.color,
                    "parent_id": project.parent_id,
                },
            )

    def handle_delete(self, intent: Any) -> None:
        db = self._db_provider()
        if not db:
            return
        deleted = db.delete_project(intent.project_id)
        if deleted:
            self._emit("project_deleted", {"id": intent.project_id})

    def handle_assign(self, intent: Any) -> None:
        db = self._db_provider()
        if not db:
            return
        db.assign_project(intent.transcript_id, intent.project_id)
        self._emit(
            "transcript_updated",
            {"id": intent.transcript_id, "project_id": intent.project_id},
        )
