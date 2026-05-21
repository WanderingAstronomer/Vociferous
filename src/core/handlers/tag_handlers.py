"""
TagHandlers — tag mutation intents.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from src.core.command_bus import handles
from src.core.intents.definitions import DeleteTagIntent

if TYPE_CHECKING:
    from src.database.db import TranscriptDB

logger = logging.getLogger(__name__)


class TagHandlers:
    """Handles tag mutation intents."""

    def __init__(
        self,
        *,
        db_provider: Callable[[], TranscriptDB | None],
        event_bus_emit: Callable,
    ) -> None:
        self._db_provider = db_provider
        self._emit = event_bus_emit

    @handles(DeleteTagIntent)
    def handle_delete_tag(self, intent: Any) -> dict[str, bool]:
        db = self._db_provider()
        if not db:
            return {"deleted": False}
        existing = db.get_tag(intent.tag_id)
        if existing is None or existing.is_system:
            return {"deleted": False}
        deleted = db.delete_tag(intent.tag_id)
        if deleted:
            self._emit("tag_deleted", {"id": intent.tag_id})
        return {"deleted": bool(deleted)}