"""
Database edge-case and invariant tests.

Covers:
- Raw text immutability (never overwritten by edits)
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


# ── Raw Text Immutability ─────────────────────────────────────────────────


class TestRawTextImmutability:
    """The raw transcript text must never be overwritten."""

    def test_raw_text_preserved_after_normalized_update(self, db: TranscriptDB) -> None:
        t = db.add_transcript(raw_text="raw", duration_ms=100)
        db.update_normalized_text(t.id, "normalized version")

        fetched = db.get_transcript(t.id)
        assert fetched.raw_text == "raw"
        assert fetched.normalized_text == "normalized version"

    def test_text_property_uses_normalized(self, db: TranscriptDB) -> None:
        t = db.add_transcript(raw_text="raw", duration_ms=100)
        db.update_normalized_text(t.id, "better version")

        fetched = db.get_transcript(t.id)
        assert fetched.text == "better version"

    def test_text_property_falls_back_to_raw(self, db: TranscriptDB) -> None:
        t = db.add_transcript(raw_text="raw text", normalized_text="", duration_ms=100)
        fetched = db.get_transcript(t.id)
        assert fetched.text == "raw text"


# ── Search Edge Cases ─────────────────────────────────────────────────────


class TestSearchEdgeCases:
    def test_search_empty_query(self, db: TranscriptDB) -> None:
        db.add_transcript(raw_text="anything", duration_ms=100)
        # Empty query falls back to recent() — returns all transcripts
        results = db.search("")
        assert len(results) == 2  # 1 added + 1 seeded

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
        assert db.transcript_count() == 3  # 2 added + 1 seeded

        db.delete_transcript(t1.id)
        assert db.transcript_count() == 2

    def test_count_after_bulk_insert(self, db: TranscriptDB) -> None:
        for i in range(25):
            db.add_transcript(raw_text=f"bulk {i}", duration_ms=100)
        assert db.transcript_count() == 26  # 25 added + 1 seeded


# ── WAL & Connection ─────────────────────────────────────────────────────


class TestWALMode:
    def test_wal_mode_enabled(self, db: TranscriptDB) -> None:
        mode = db._conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"

    def test_foreign_keys_enabled(self, db: TranscriptDB) -> None:
        fk = db._conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1


class TestLegacySchemaBootstrap:
    def test_pre_v11_database_bootstraps_and_migrates(self, tmp_path: Path) -> None:
        db_path = tmp_path / "legacy_v10.db"

        conn = sqlite3.connect(str(db_path))
        conn.executescript(
            """
            CREATE TABLE transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT UNIQUE NOT NULL,
                raw_text TEXT NOT NULL,
                normalized_text TEXT NOT NULL,
                display_name TEXT,
                duration_ms INTEGER DEFAULT 0,
                speech_duration_ms INTEGER DEFAULT 0,
                transcription_time_ms INTEGER DEFAULT 0,
                refinement_time_ms INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
                include_in_analytics INTEGER NOT NULL DEFAULT 1,
                has_audio_cached INTEGER NOT NULL DEFAULT 0,
                is_protected INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX idx_transcripts_timestamp ON transcripts(timestamp);

            CREATE TABLE schema_version (
                version INTEGER NOT NULL
            );

            INSERT INTO schema_version (version) VALUES (10);
            """
        )
        conn.commit()
        conn.close()

        db = TranscriptDB(db_path=db_path)

        cols = {row["name"] for row in db._conn.execute("PRAGMA table_info(transcripts)").fetchall()}
        index_names = {row[1] for row in db._conn.execute("PRAGMA index_list('transcripts')").fetchall()}

        assert "compound_root_id" in cols
        assert "compound_order" in cols
        assert "idx_transcripts_compound_root" in index_names
        assert "idx_transcripts_compound_member_order" in index_names

        db.close()


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
        assert all(c == 11 for c in results)  # 10 added + 1 seeded


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
        assert backup_db.transcript_count() == 2  # 1 added + 1 seeded
        recent_items = backup_db.recent()[0]
        assert any(t.raw_text == "verify backup" for t in recent_items)
        backup_db.close()
