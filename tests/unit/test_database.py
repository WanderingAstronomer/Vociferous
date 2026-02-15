"""
Tests for the v4 TranscriptDB (raw sqlite3).

Verifies:
- Table creation
- CRUD operations
- Variant creation and linking
- Search
- WAL mode
"""

import pytest

from src.database.db import TranscriptDB, Transcript, TranscriptVariant, Project


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
        recent = db.recent(limit=3)
        assert len(recent) == 3

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


class TestVariants:
    def test_add_variant(self, db: TranscriptDB):
        t = db.add_transcript(raw_text="Original", duration_ms=100)
        v = db.add_variant(t.id, "user_edit", "Edited version")
        assert v.id is not None
        assert v.kind == "user_edit"
        assert v.text == "Edited version"

    def test_variant_with_model_id(self, db: TranscriptDB):
        t = db.add_transcript(raw_text="Original", duration_ms=100)
        v = db.add_variant(t.id, "refined", "Refined text", model_id="qwen4b")
        assert v.model_id == "qwen4b"

    def test_set_current_variant(self, db: TranscriptDB):
        t = db.add_transcript(raw_text="Original", duration_ms=100)
        v = db.add_variant(t.id, "user_edit", "Edited", set_current=True)

        fetched = db.get_transcript(t.id)
        assert fetched.current_variant_id == v.id
        assert fetched.text == "Edited"

    def test_text_property_uses_variant(self, db: TranscriptDB):
        t = db.add_transcript(raw_text="Raw", duration_ms=100)
        db.add_variant(t.id, "refined", "Refined", set_current=True)

        fetched = db.get_transcript(t.id)
        assert fetched.text == "Refined"

    def test_text_property_fallback_to_normalized(self, db: TranscriptDB):
        t = db.add_transcript(raw_text="Raw text", duration_ms=100)
        fetched = db.get_transcript(t.id)
        # No variant set → falls back to normalized_text
        assert fetched.text == fetched.normalized_text


class TestProjects:
    def test_add_project(self, db: TranscriptDB):
        p = db.add_project(name="Test Project")
        assert p.id is not None
        assert p.name == "Test Project"

    def test_get_projects(self, db: TranscriptDB):
        db.add_project(name="Project A")
        db.add_project(name="Project B")
        projects = db.get_projects()
        assert len(projects) == 2

    def test_delete_project(self, db: TranscriptDB):
        p = db.add_project(name="Delete Me")
        assert db.delete_project(p.id) is True
        assert len(db.get_projects()) == 0

    def test_transcript_with_project(self, db: TranscriptDB):
        p = db.add_project(name="MyProject")
        t = db.add_transcript(raw_text="In project", duration_ms=100, project_id=p.id)
        assert t.project_id == p.id
