"""
Database edge-case and invariant tests.

Covers:
- CASCADE delete (transcript → variants)
- Project-scoped queries and unlink-on-delete
- Variant immutability (raw text never overwritten)
- Search edge cases (empty, special chars, multi-match)
- transcript_count accuracy after mutations
- WAL mode verification
- Concurrent read safety
- Boundary inputs (empty strings, huge text, zero-length recordings)
"""

import sqlite3
import threading
from collections.abc import Generator
from pathlib import Path

import pytest

from src.database.db import TranscriptDB


@pytest.fixture
def db(tmp_path: Path) -> Generator[TranscriptDB, None, None]:
    d = TranscriptDB(db_path=tmp_path / "test.db")
    yield d
    d.close()


# ── Cascade Delete ────────────────────────────────────────────────────────


class TestCascadeDelete:
    """Deleting a transcript must delete all its variants."""

    def test_variants_removed_on_delete(self, db: TranscriptDB) -> None:
        t = db.add_transcript(raw_text="base", duration_ms=100)
        db.add_variant(t.id, "user_edit", "edit 1")
        db.add_variant(t.id, "refined", "refined 1")

        db.delete_transcript(t.id)

        # Directly query variants table — should be empty
        rows = db._conn.execute(
            "SELECT COUNT(*) FROM transcript_variants WHERE transcript_id = ?",
            (t.id,),
        ).fetchone()
        assert rows[0] == 0

    def test_other_transcript_variants_untouched(self, db: TranscriptDB) -> None:
        t1 = db.add_transcript(raw_text="first", duration_ms=100)
        t2 = db.add_transcript(raw_text="second", duration_ms=100)
        db.add_variant(t1.id, "user_edit", "edit-t1")
        db.add_variant(t2.id, "user_edit", "edit-t2")

        db.delete_transcript(t1.id)

        # t2 variants survive
        fetched = db.get_transcript(t2.id)
        assert len(fetched.variants) == 2  # raw + user_edit


# ── Project-Scoped Queries ────────────────────────────────────────────────


class TestProjectScoping:
    """Project-based filtering and unlink behavior."""

    def test_recent_filters_by_project(self, db: TranscriptDB) -> None:
        p1 = db.add_project(name="Alpha")
        p2 = db.add_project(name="Beta")
        db.add_transcript(raw_text="in alpha", duration_ms=100, project_id=p1.id)
        db.add_transcript(raw_text="in beta", duration_ms=100, project_id=p2.id)
        db.add_transcript(raw_text="orphan", duration_ms=100)

        alpha_only = db.recent(project_id=p1.id)
        assert len(alpha_only) == 1
        assert alpha_only[0].raw_text == "in alpha"

    def test_delete_project_unlinks_transcripts(self, db: TranscriptDB) -> None:
        p = db.add_project(name="Doomed")
        t = db.add_transcript(raw_text="linked", duration_ms=100, project_id=p.id)

        db.delete_project(p.id)

        # Transcript survives but is unlinked
        fetched = db.get_transcript(t.id)
        assert fetched is not None
        assert fetched.project_id is None

    def test_assign_project(self, db: TranscriptDB) -> None:
        p = db.add_project(name="Target")
        t = db.add_transcript(raw_text="floating", duration_ms=100)
        assert t.project_id is None

        db.assign_project(t.id, p.id)

        fetched = db.get_transcript(t.id)
        assert fetched.project_id == p.id

    def test_unassign_project(self, db: TranscriptDB) -> None:
        p = db.add_project(name="Temp")
        t = db.add_transcript(raw_text="assigned", duration_ms=100, project_id=p.id)

        db.assign_project(t.id, None)

        fetched = db.get_transcript(t.id)
        assert fetched.project_id is None

    def test_project_name_populated_in_get(self, db: TranscriptDB) -> None:
        p = db.add_project(name="Named")
        t = db.add_transcript(raw_text="text", duration_ms=100, project_id=p.id)

        fetched = db.get_transcript(t.id)
        assert fetched.project_name == "Named"

    def test_project_name_populated_in_recent(self, db: TranscriptDB) -> None:
        p = db.add_project(name="Recent")
        db.add_transcript(raw_text="in recent", duration_ms=100, project_id=p.id)

        results = db.recent()
        assert results[0].project_name == "Recent"

    def test_project_with_color(self, db: TranscriptDB) -> None:
        _p = db.add_project(name="Colored", color="#ff00ff")
        projects = db.get_projects()
        assert projects[0].color == "#ff00ff"

    def test_project_with_parent(self, db: TranscriptDB) -> None:
        parent = db.add_project(name="Parent")
        child = db.add_project(name="Child", parent_id=parent.id)
        assert child.parent_id == parent.id


# ── Variant Immutability ─────────────────────────────────────────────────


class TestVariantImmutability:
    """The raw transcript text must never be overwritten."""

    def test_raw_text_preserved_after_variant(self, db: TranscriptDB) -> None:
        t = db.add_transcript(raw_text="original raw", duration_ms=100)
        db.add_variant(t.id, "user_edit", "completely different")

        fetched = db.get_transcript(t.id)
        assert fetched.raw_text == "original raw"

    def test_raw_text_preserved_after_normalized_update(self, db: TranscriptDB) -> None:
        t = db.add_transcript(raw_text="raw", duration_ms=100)
        db.update_normalized_text(t.id, "normalized version")

        fetched = db.get_transcript(t.id)
        assert fetched.raw_text == "raw"
        assert fetched.normalized_text == "normalized version"

    def test_raw_variant_always_first(self, db: TranscriptDB) -> None:
        t = db.add_transcript(raw_text="original", duration_ms=100)
        db.add_variant(t.id, "refined", "refined")
        db.add_variant(t.id, "user_edit", "edited")

        fetched = db.get_transcript(t.id)
        assert fetched.variants[0].kind == "raw"
        assert fetched.variants[0].text == "original"

    def test_variant_set_current_false(self, db: TranscriptDB) -> None:
        """Adding variant with set_current=False doesn't change current_variant_id."""
        t = db.add_transcript(raw_text="base", duration_ms=100)
        original_vid = t.current_variant_id

        db.add_variant(t.id, "refined", "alt text", set_current=False)

        fetched = db.get_transcript(t.id)
        assert fetched.current_variant_id == original_vid


# ── Search Edge Cases ─────────────────────────────────────────────────────


class TestSearchEdgeCases:

    def test_search_empty_query(self, db: TranscriptDB) -> None:
        db.add_transcript(raw_text="anything", duration_ms=100)
        # Empty query matches everything (LIKE '%%')
        results = db.search("")
        assert len(results) == 1

    def test_search_no_match(self, db: TranscriptDB) -> None:
        db.add_transcript(raw_text="hello world", duration_ms=100)
        results = db.search("xyzzy")
        assert len(results) == 0

    def test_search_matches_normalized_text(self, db: TranscriptDB) -> None:
        db.add_transcript(raw_text="raw", normalized_text="the normalized version", duration_ms=100)
        results = db.search("normalized")
        assert len(results) == 1

    def test_search_case_insensitive(self, db: TranscriptDB) -> None:
        db.add_transcript(raw_text="Python Programming", duration_ms=100)
        results = db.search("python")
        assert len(results) == 1

    def test_search_special_characters(self, db: TranscriptDB) -> None:
        db.add_transcript(raw_text="foo % bar _ baz", duration_ms=100)
        # LIKE patterns: % and _ are wildcards. Our search wraps in %...%
        # so searching for literal "%" will match because it's embedded.
        results = db.search("foo")
        assert len(results) == 1

    def test_search_respects_limit(self, db: TranscriptDB) -> None:
        for i in range(10):
            db.add_transcript(raw_text=f"common word {i}", duration_ms=100)
        results = db.search("common", limit=3)
        assert len(results) == 3


# ── Count Accuracy ────────────────────────────────────────────────────────


class TestTranscriptCount:

    def test_count_after_delete(self, db: TranscriptDB) -> None:
        t1 = db.add_transcript(raw_text="one", duration_ms=100)
        db.add_transcript(raw_text="two", duration_ms=100)
        assert db.transcript_count() == 2

        db.delete_transcript(t1.id)
        assert db.transcript_count() == 1

    def test_count_after_bulk_insert(self, db: TranscriptDB) -> None:
        for i in range(25):
            db.add_transcript(raw_text=f"bulk {i}", duration_ms=100)
        assert db.transcript_count() == 25


# ── WAL & Connection ─────────────────────────────────────────────────────


class TestWALMode:

    def test_wal_mode_enabled(self, db: TranscriptDB) -> None:
        mode = db._conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"

    def test_foreign_keys_enabled(self, db: TranscriptDB) -> None:
        fk = db._conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1


class TestConcurrentReads:
    """Multiple threads can read simultaneously under WAL."""

    def test_concurrent_reads_dont_block(self, tmp_path: Path) -> None:
        db_path = tmp_path / "concurrent.db"
        db = TranscriptDB(db_path=db_path)
        for i in range(10):
            db.add_transcript(raw_text=f"item {i}", duration_ms=100)

        results: list[int] = []
        errors: list[Exception] = []

        def reader() -> None:
            try:
                # Open a second connection (simulating concurrent reader)
                conn2 = sqlite3.connect(str(db_path))
                conn2.execute("PRAGMA journal_mode=WAL")
                count = conn2.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]
                results.append(count)
                conn2.close()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(5)]
        for th in threads:
            th.start()
        for th in threads:
            th.join(timeout=5)

        db.close()

        assert not errors, f"Concurrent read errors: {errors}"
        assert all(c == 10 for c in results)


# ── Boundary Inputs ───────────────────────────────────────────────────────


class TestBoundaryInputs:

    def test_empty_string_text(self, db: TranscriptDB) -> None:
        t = db.add_transcript(raw_text="", duration_ms=0)
        fetched = db.get_transcript(t.id)
        assert fetched.raw_text == ""

    def test_very_long_text(self, db: TranscriptDB) -> None:
        long_text = "word " * 10_000
        t = db.add_transcript(raw_text=long_text, duration_ms=60_000)
        fetched = db.get_transcript(t.id)
        assert fetched.raw_text == long_text

    def test_unicode_text(self, db: TranscriptDB) -> None:
        text = "日本語テスト 🎤 émojis café naïve"
        t = db.add_transcript(raw_text=text, duration_ms=100)
        fetched = db.get_transcript(t.id)
        assert fetched.raw_text == text

    def test_newlines_in_text(self, db: TranscriptDB) -> None:
        text = "line one\nline two\n\nline four"
        t = db.add_transcript(raw_text=text, duration_ms=100)
        fetched = db.get_transcript(t.id)
        assert fetched.raw_text == text

    def test_zero_duration(self, db: TranscriptDB) -> None:
        t = db.add_transcript(raw_text="short", duration_ms=0)
        assert t.duration_ms == 0


# ── Export Backup ─────────────────────────────────────────────────────────


class TestExportBackup:

    def test_backup_creates_file(self, db: TranscriptDB, tmp_path: Path) -> None:
        db.add_transcript(raw_text="backup test", duration_ms=100)
        backup_path = tmp_path / "backup.db"
        db.export_backup(backup_path)
        assert backup_path.exists()

    def test_backup_is_valid_db(self, db: TranscriptDB, tmp_path: Path) -> None:
        db.add_transcript(raw_text="verify backup", duration_ms=100)
        backup_path = tmp_path / "backup.db"
        db.export_backup(backup_path)

        # Open backup and verify data
        backup_db = TranscriptDB(db_path=backup_path)
        assert backup_db.transcript_count() == 1
        t = backup_db.recent()[0]
        assert t.raw_text == "verify backup"
        backup_db.close()
