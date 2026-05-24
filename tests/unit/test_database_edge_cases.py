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


class TestAudioVaultTables:
    def test_recording_session_chunk_and_asset_roundtrip(self, db: TranscriptDB, tmp_path: Path) -> None:
        audio_path = tmp_path / "rec.vocaud"
        record = db.create_recording_session(
            recording_id="rec_db",
            audio_path=audio_path,
            sample_rate=16000,
            encrypted=True,
            encryption_key_id="rec_db",
        )
        assert record.status == "active"
        assert record.encrypted is True

        db.add_recording_chunk(
            recording_id="rec_db",
            chunk_index=0,
            start_frame=0,
            frame_count=16000,
            byte_offset=32,
            byte_count=32000,
            sha256="abc123",
        )
        updated = db.get_recording_session("rec_db")
        assert updated is not None
        assert updated.duration_ms == 1000
        assert updated.last_durable_chunk == 0

        transcript = db.add_transcript(raw_text="hello", duration_ms=1000)
        asset = db.add_audio_asset(
            recording_id="rec_db",
            transcript_id=transcript.id,
            role="transcript_source",
            path=audio_path,
            duration_ms=1000,
            size_bytes=32032,
            encrypted=True,
            pinned=True,
        )
        assert asset.id is not None
        assets = db.get_audio_assets_for_transcript(transcript.id)
        assert len(assets) == 1
        assert assets[0].recording_id == "rec_db"

        db.mark_recording_status("rec_db", "completed", transcript_id=transcript.id, finalized=True)
        completed = db.get_recording_session("rec_db")
        assert completed is not None
        assert completed.status == "completed"
        assert completed.transcript_id == transcript.id


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

    def test_audio_vault_foreign_keys_repaired_after_transcripts_rebuild(self, tmp_path: Path) -> None:
        db_path = tmp_path / "legacy_v11_audio_vault_fk.db"

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
                is_protected INTEGER NOT NULL DEFAULT 0,
                compound_root_id INTEGER REFERENCES transcripts(id) ON DELETE CASCADE,
                compound_order INTEGER
            );

            CREATE UNIQUE INDEX idx_transcripts_timestamp_unique ON transcripts(timestamp);

            INSERT INTO transcripts (
                timestamp, raw_text, normalized_text, display_name, created_at
            ) VALUES (
                '2026-01-01T00:00:00.000000+00:00', 'legacy raw', 'legacy normalized', 'Legacy',
                '2026-01-01T00:00:00.000000+00:00'
            );

            CREATE TABLE schema_version (
                version INTEGER NOT NULL
            );

            INSERT INTO schema_version (version) VALUES (11);
            """
        )
        conn.commit()
        conn.close()

        db = TranscriptDB(db_path=db_path)
        try:
            recording_fks = {
                (row[3], row[2]) for row in db._conn.execute("PRAGMA foreign_key_list(recording_sessions)").fetchall()
            }
            asset_fks = {
                (row[3], row[2]) for row in db._conn.execute("PRAGMA foreign_key_list(audio_assets)").fetchall()
            }

            assert ("transcript_id", "transcripts") in recording_fks
            assert ("transcript_id", "transcripts") in asset_fks
            assert all(target != "transcripts_old" for _column, target in recording_fks | asset_fks)

            record = db.create_recording_session(
                recording_id="rec_after_migration",
                audio_path=tmp_path / "rec_after_migration.pcm",
                sample_rate=16000,
            )
            assert record.id == "rec_after_migration"
            assert db._conn.execute("PRAGMA foreign_key_check").fetchall() == []
        finally:
            db.close()

    def test_v15_database_gains_processing_provenance_columns(self, tmp_path: Path) -> None:
        db_path = tmp_path / "legacy_v15_processing_provenance.db"

        conn = sqlite3.connect(str(db_path))
        conn.executescript(
            """
            CREATE TABLE transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
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
                is_protected INTEGER NOT NULL DEFAULT 0,
                compound_root_id INTEGER REFERENCES transcripts(id) ON DELETE CASCADE,
                compound_order INTEGER
            );

            CREATE TABLE schema_version (
                version INTEGER NOT NULL
            );

            INSERT INTO schema_version (version) VALUES (15);
            INSERT INTO transcripts (timestamp, raw_text, normalized_text, created_at)
            VALUES ('2026-01-01T00:00:00.000000+00:00', 'legacy', 'legacy', '2026-01-01T00:00:00.000000+00:00');
            """
        )
        conn.commit()
        conn.close()

        db = TranscriptDB(db_path=db_path)
        try:
            cols = {row["name"] for row in db._conn.execute("PRAGMA table_info(transcripts)").fetchall()}
            assert "transcription_provider" in cols
            assert "transcription_model_id" in cols
            assert "transcription_resolved_device" in cols
            assert "transcription_compute_type" in cols
            assert "transcription_cpu_threads" in cols
            assert "transcription_prompt_text" in cols
            assert "transcription_prompt_chars" in cols
            assert "transcription_prompt_words" in cols
            assert "retranscription_count" in cols
            assert "last_retranscription_at" in cols
            assert "last_retranscription_time_ms" in cols
            assert "last_retranscription_provider" in cols
            assert "last_retranscription_model_id" in cols
            assert "last_retranscription_resolved_device" in cols
            assert "last_retranscription_compute_type" in cols
            assert "last_retranscription_cpu_threads" in cols
            assert "last_retranscription_prompt_text" in cols
            assert "last_retranscription_prompt_chars" in cols
            assert "last_retranscription_prompt_words" in cols
            assert "refinement_provider" in cols
            assert "refinement_model_id" in cols
            assert "refinement_resolved_device" in cols
            assert "refinement_compute_type" in cols
            assert "refinement_cpu_threads" in cols
            assert "refinement_gpu_layers" in cols
            assert "refinement_use_thinking" in cols
            assert "refinement_prompt_text" in cols
            assert "refinement_prompt_chars" in cols
            assert "refinement_prompt_words" in cols
            assert "refinement_prompt_tokens" in cols
            assert "refinement_completion_tokens" in cols
            assert "refinement_total_tokens" in cols

            transcript = db.get_transcript(1)
            assert transcript is not None
            assert transcript.transcription_provider == ""
            assert transcript.transcription_resolved_device == ""
            assert transcript.refinement_provider == ""
            assert transcript.retranscription_count == 0
            assert transcript.last_retranscription_provider == ""
            assert transcript.transcription_prompt_chars == 0
            assert transcript.refinement_prompt_words == 0
            assert transcript.refinement_prompt_tokens == 0
            assert transcript.refinement_use_thinking is False
        finally:
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
        assert all(c == 12 for c in results)  # 10 user transcripts + 2 protected prompt records


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
        recent_items = backup_db.recent()[0]
        assert any(t.raw_text == "verify backup" for t in recent_items)
        backup_db.close()
