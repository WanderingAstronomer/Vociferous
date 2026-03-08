"""
Unit tests for TitleGenerator — SLM-based auto-titling of transcripts.

Tests the scheduling guard-rails, background generation, batch retitling,
and edge-case handling. Uses mock SLM runtime and in-memory DB.
"""

from __future__ import annotations

import threading
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.core.constants import TitleGeneration
from src.core.title_generator import TitleGenerator
from src.database.db import TranscriptDB
from src.services.slm_types import SLMState

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> Generator[TranscriptDB, None, None]:
    database = TranscriptDB(db_path=tmp_path / "title_test.db")
    yield database
    database.close()


@pytest.fixture()
def mock_slm() -> MagicMock:
    slm = MagicMock()
    slm.state = SLMState.READY
    slm.generate_custom_sync.return_value = "Generated Title"
    return slm


@pytest.fixture()
def emitted_events() -> list[tuple[str, dict]]:
    return []


@pytest.fixture()
def generator(db, mock_slm, emitted_events) -> TitleGenerator:
    def emit(event_type: str, data: dict) -> None:
        emitted_events.append((event_type, data))

    return TitleGenerator(
        slm_runtime_provider=lambda: mock_slm,
        db_provider=lambda: db,
        event_emitter=emit,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wait_for_threads(prefix: str, timeout: float = 5.0) -> None:
    """Wait for all background threads with the given name prefix to finish."""
    for t in threading.enumerate():
        if t.name.startswith(prefix) and t.is_alive():
            t.join(timeout=timeout)


# ---------------------------------------------------------------------------
# schedule() guard-rails
# ---------------------------------------------------------------------------


class TestScheduleGuards:
    """Verify that schedule() correctly rejects invalid or untimely calls."""

    def test_text_too_short_skips(self, generator, mock_slm):
        """Text shorter than MIN_TEXT_CHARS is not scheduled."""
        generator.schedule(1, "x" * (TitleGeneration.MIN_TEXT_CHARS - 1))
        _wait_for_threads("title-gen-")
        mock_slm.generate_custom_sync.assert_not_called()

    def test_text_at_minimum_length_proceeds(self, generator, mock_slm, db, emitted_events):
        """Text exactly at MIN_TEXT_CHARS should be scheduled."""
        t = db.add_transcript(raw_text="x" * TitleGeneration.MIN_TEXT_CHARS, duration_ms=1000)
        generator.schedule(t.id, "x" * TitleGeneration.MIN_TEXT_CHARS)
        _wait_for_threads("title-gen-")
        mock_slm.generate_custom_sync.assert_called_once()

    def test_slm_none_skips(self, db, emitted_events):
        """If SLM provider returns None, schedule is a no-op."""
        gen = TitleGenerator(
            slm_runtime_provider=lambda: None,
            db_provider=lambda: db,
            event_emitter=lambda *a: emitted_events.append(a),
        )
        gen.schedule(1, "x" * 200)
        _wait_for_threads("title-gen-")
        assert len(emitted_events) == 0

    def test_slm_not_ready_skips(self, generator, mock_slm, emitted_events):
        """If SLM state is not READY, schedule is a no-op."""
        mock_slm.state = SLMState.INFERRING
        generator.schedule(1, "x" * 200)
        _wait_for_threads("title-gen-")
        mock_slm.generate_custom_sync.assert_not_called()

    def test_duplicate_transcript_id_skips(self, generator, mock_slm, db):
        """A second schedule() for the same transcript ID is rejected while in-flight."""
        # Block the first call so the second hits the dedup guard
        barrier = threading.Event()
        original_generate = mock_slm.generate_custom_sync

        def slow_generate(**kwargs):
            barrier.wait(timeout=5)
            return original_generate(**kwargs)

        mock_slm.generate_custom_sync = slow_generate

        t = db.add_transcript(raw_text="x" * 200, duration_ms=1000)
        generator.schedule(t.id, "x" * 200)
        generator.schedule(t.id, "x" * 200)  # should be rejected
        barrier.set()
        _wait_for_threads("title-gen-")

        # Only one call should have gone through
        assert original_generate.call_count == 1


# ---------------------------------------------------------------------------
# _generate_task (single-transcript background generation)
# ---------------------------------------------------------------------------


class TestGenerateTask:
    """Verify the background title generation logic."""

    def test_successful_generation_writes_db_and_emits(self, generator, mock_slm, db, emitted_events):
        """A successful generation writes the title to DB and emits transcript_updated."""
        t = db.add_transcript(raw_text="x" * 200, duration_ms=1000)
        mock_slm.generate_custom_sync.return_value = "My Great Title"

        generator.schedule(t.id, "x" * 200)
        _wait_for_threads("title-gen-")

        refreshed = db.get_transcript(t.id)
        assert refreshed.display_name == "My Great Title"

        updated = [e for et, e in emitted_events if et == "transcript_updated"]
        assert len(updated) == 1
        assert updated[0]["id"] == t.id

    def test_empty_title_from_slm_does_not_write(self, generator, mock_slm, db, emitted_events):
        """If SLM returns empty string, no DB write or event."""
        t = db.add_transcript(raw_text="x" * 200, duration_ms=1000)
        mock_slm.generate_custom_sync.return_value = ""

        generator.schedule(t.id, "x" * 200)
        _wait_for_threads("title-gen-")

        refreshed = db.get_transcript(t.id)
        assert refreshed.display_name is None
        assert len([e for et, e in emitted_events if et == "transcript_updated"]) == 0

    def test_title_with_quotes_stripped(self, generator, mock_slm, db, emitted_events):
        """Surrounding quotes from the SLM are stripped."""
        t = db.add_transcript(raw_text="x" * 200, duration_ms=1000)
        mock_slm.generate_custom_sync.return_value = '"Quoted Title"'

        generator.schedule(t.id, "x" * 200)
        _wait_for_threads("title-gen-")

        assert db.get_transcript(t.id).display_name == "Quoted Title"

    def test_multiline_title_takes_first_line(self, generator, mock_slm, db, emitted_events):
        """If the SLM hallucinates a paragraph, only the first line is kept."""
        t = db.add_transcript(raw_text="x" * 200, duration_ms=1000)
        mock_slm.generate_custom_sync.return_value = "Good Title\nBut this is junk"

        generator.schedule(t.id, "x" * 200)
        _wait_for_threads("title-gen-")

        assert db.get_transcript(t.id).display_name == "Good Title"

    def test_slm_disappears_mid_generation(self, db, emitted_events):
        """If SLM becomes None between schedule check and generation, no crash."""
        call_count = 0
        mock_slm = MagicMock()
        mock_slm.state = SLMState.READY

        def disappearing_provider():
            nonlocal call_count
            call_count += 1
            return mock_slm if call_count <= 1 else None

        gen = TitleGenerator(
            slm_runtime_provider=disappearing_provider,
            db_provider=lambda: db,
            event_emitter=lambda et, d: emitted_events.append((et, d)),
        )

        gen.schedule(1, "x" * 200)
        _wait_for_threads("title-gen-")
        # Should not crash, no event emitted
        assert len([e for et, e in emitted_events if et == "transcript_updated"]) == 0

    def test_pending_set_cleared_after_generation(self, generator, mock_slm, db):
        """The transcript ID is removed from _pending after generation completes."""
        t = db.add_transcript(raw_text="x" * 200, duration_ms=1000)
        generator.schedule(t.id, "x" * 200)
        _wait_for_threads("title-gen-")

        assert t.id not in generator._pending

    def test_pending_set_cleared_on_exception(self, generator, mock_slm, db):
        """The transcript ID is removed from _pending even if generation throws."""
        t = db.add_transcript(raw_text="x" * 200, duration_ms=1000)
        mock_slm.generate_custom_sync.side_effect = RuntimeError("boom")

        generator.schedule(t.id, "x" * 200)
        _wait_for_threads("title-gen-")

        assert t.id not in generator._pending

    def test_long_text_truncated_to_max(self, generator, mock_slm, db, emitted_events):
        """Input text longer than MAX_TEXT_CHARS is truncated before SLM call."""
        huge_text = "x" * (TitleGeneration.MAX_TEXT_CHARS + 5000)
        t = db.add_transcript(raw_text=huge_text, duration_ms=1000)

        generator.schedule(t.id, huge_text)
        _wait_for_threads("title-gen-")

        call_kwargs = mock_slm.generate_custom_sync.call_args
        passed_text = call_kwargs.kwargs["user_prompt"]
        assert len(passed_text) == TitleGeneration.MAX_TEXT_CHARS


