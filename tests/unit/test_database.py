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
        assert total == 6  # 5 added + 1 seeded

    def test_transcript_count(self, db: TranscriptDB):
        assert db.transcript_count() == 1  # v9 seeds 1 protected prompt transcript
        db.add_transcript(raw_text="One", duration_ms=100)
        db.add_transcript(raw_text="Two", duration_ms=100)
        assert db.transcript_count() == 3

    def test_search(self, db: TranscriptDB):
        db.add_transcript(raw_text="Python programming", duration_ms=100)
        db.add_transcript(raw_text="JavaScript development", duration_ms=100)
        results = db.search("python")
        assert len(results) == 1
        assert "Python" in results[0].raw_text

    def test_append_preserves_source_and_hides_child_from_default_queries(self, db: TranscriptDB):
        root = db.add_transcript(raw_text="Root text", duration_ms=1000, speech_duration_ms=900)
        source = db.add_transcript(raw_text="New segment", duration_ms=500, speech_duration_ms=450)

        root_id = db.append_to_transcript(root.id, source.id)

        assert root_id == root.id

        preserved_source = db.get_transcript(source.id)
        assert preserved_source is not None
        assert preserved_source.compound_root_id == root.id
        assert preserved_source.compound_order == 1

        updated_root = db.get_transcript(root.id)
        assert updated_root is not None
        assert updated_root.raw_text == "Root text\n\nNew segment"
        assert updated_root.duration_ms == 1500
        assert updated_root.speech_duration_ms == 1350
        assert any(tag.name == "Compound" for tag in updated_root.tags)

        visible_items, visible_total = db.recent(limit=10)
        visible_ids = {item.id for item in visible_items}
        assert root.id in visible_ids
        assert source.id not in visible_ids
        assert visible_total == 2  # seeded prompt + visible root
        assert db.transcript_count() == 2
        assert db.transcript_count(include_compound_children=True) == 3

    def test_search_excludes_hidden_compound_children_by_default(self, db: TranscriptDB):
        root = db.add_transcript(raw_text="Alpha", duration_ms=100)
        source = db.add_transcript(raw_text="Beta keyword", duration_ms=100)

        db.append_to_transcript(root.id, source.id)

        default_results = db.search("beta")
        assert [item.id for item in default_results] == [root.id]
        assert db.search_count("beta") == 1

        all_results = db.search("beta", include_compound_children=True)
        assert {item.id for item in all_results} == {root.id, source.id}
        assert db.search_count("beta", include_compound_children=True) == 2
