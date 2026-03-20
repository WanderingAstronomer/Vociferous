"""
TitleHandlers — single-transcript retitle intent.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from src.core.command_bus import handles
from src.core.intents.definitions import RetitleTranscriptIntent

if TYPE_CHECKING:
    from src.core.title_generator import TitleGenerator
    from src.database.db import TranscriptDB

logger = logging.getLogger(__name__)


class TitleHandlers:
    """Handles transcript titling intents."""

    def __init__(
        self,
        *,
        db_provider: Callable[[], "TranscriptDB | None"],
        title_generator_provider: Callable[[], "TitleGenerator | None"],
        event_bus_emit: Callable,
    ) -> None:
        self._db_provider = db_provider
        self._title_generator_provider = title_generator_provider
        self._emit = event_bus_emit

    @handles(RetitleTranscriptIntent)
    def handle_retitle(self, intent: Any) -> None:
        """Re-generate the SLM title for a single transcript."""
        title_gen = self._title_generator_provider()
        db = self._db_provider()
        if title_gen is None or db is None:
            return
        t = db.get_transcript(intent.transcript_id)
        if t is None:
            return
        text = t.normalized_text or t.raw_text or ""
        if not text.strip():
            return
        title_gen.schedule(intent.transcript_id, text)
