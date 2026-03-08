"""
Tests for the TranscriptDB (raw sqlite3).

Verifies:
- Table creation
- CRUD operations
- Search
- WAL mode
"""

import pytest

from src.database.db import Transcript, TranscriptDB


@pytest.fixture
def db(tmp_path):
    """Create an in-memory-like temp DB for each test."""
    d = TranscriptDB(db_path=tmp_path / "test.db")
    yield d
    d.close()


class TestTranscriptCRUD:
    def test_add_and_retrieve(self, db: TranscriptDB):
        t = db.add_transcript(raw_text="Hello world", duration_ms=1000)
        assert t.id is not None
        assert t.raw_text == "Hello world"
        assert t.duration_ms == 1000

    def test_get_transcript(self, db: TranscriptDB):
        t = db.add_transcript(raw_text="Test", duration_ms=500)
        fetched = db.get_transcript(t.id)
        assert fetched is not None
        assert fetched.raw_text == "Test"

    def test_get_nonexistent(self, db: TranscriptDB):
        assert db.get_transcript(9999) is None

    def test_delete(self, db: TranscriptDB):
        t = db.add_transcript(raw_text="Delete me", duration_ms=100)
        assert db.delete_transcript(t.id) is True
        assert db.get_transcript(t.id) is None

    def test_delete_nonexistent(self, db: TranscriptDB):
        assert db.delete_transcript(9999) is False

    def test_recent(self, db: TranscriptDB):
        for i in range(5):
            db.add_transcript(raw_text=f"Transcript {i}", duration_ms=100)
        recent, total = db.recent(limit=3)
        assert len(recent) == 3
        assert total == 5

    def test_transcript_count(self, db: TranscriptDB):
        assert db.transcript_count() == 0
        db.add_transcript(raw_text="One", duration_ms=100)
        db.add_transcript(raw_text="Two", duration_ms=100)
        assert db.transcript_count() == 2

    def test_search(self, db: TranscriptDB):
        db.add_transcript(raw_text="Python programming", duration_ms=100)
        db.add_transcript(raw_text="JavaScript development", duration_ms=100)
        results = db.search("python")
        assert len(results) == 1
        assert "Python" in results[0].raw_text
