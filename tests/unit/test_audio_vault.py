from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from src.database.db import TranscriptDB
from src.services.audio_vault import AudioVaultManager, AudioVaultWriter


def _configure_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VOCIFEROUS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("VOCIFEROUS_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("VOCIFEROUS_CACHE_DIR", str(tmp_path / "cache"))


def test_audio_vault_writer_persists_chunks_and_loads_audio(monkeypatch, tmp_path: Path) -> None:
    _configure_paths(monkeypatch, tmp_path)
    db = TranscriptDB(db_path=tmp_path / "test.db")
    try:
        writer = AudioVaultWriter(
            db=db,
            session_id="rec_plain",
            sample_rate=16000,
            durability_interval_seconds=1,
        )
        audio = np.arange(32000, dtype=np.int16)
        writer.write_frames(audio)
        path = writer.finalize()

        record = db.get_recording_session("rec_plain")
        assert record is not None
        assert record.status == "recorded"
        assert record.last_durable_chunk == 1
        assert path.exists()

        loaded = AudioVaultManager(db).load_audio("rec_plain")
        np.testing.assert_array_equal(loaded, audio)
    finally:
        db.close()


def test_audio_vault_recovery_truncates_torn_record(monkeypatch, tmp_path: Path) -> None:
    _configure_paths(monkeypatch, tmp_path)
    db = TranscriptDB(db_path=tmp_path / "test.db")
    try:
        writer = AudioVaultWriter(
            db=db,
            session_id="rec_torn",
            sample_rate=16000,
            durability_interval_seconds=1,
        )
        audio = np.arange(16000, dtype=np.int16)
        writer.write_frames(audio)
        writer._fh.write(b"partial")
        writer._fh.flush()
        os.fsync(writer._fh.fileno())
        writer._fh.close()
        writer._fh = None

        before_size = writer.path.stat().st_size
        recovered = AudioVaultManager(db).recover_interrupted_recordings()
        after_size = writer.path.stat().st_size

        assert len(recovered) == 1
        assert recovered[0].status == "recovered"
        assert after_size < before_size
        loaded = AudioVaultManager(db).load_audio("rec_torn")
        np.testing.assert_array_equal(loaded, audio)
    finally:
        db.close()


def test_audio_vault_recovery_truncates_malformed_complete_record(monkeypatch, tmp_path: Path) -> None:
    _configure_paths(monkeypatch, tmp_path)
    db = TranscriptDB(db_path=tmp_path / "test.db")
    try:
        writer = AudioVaultWriter(
            db=db,
            session_id="rec_malformed",
            sample_rate=16000,
            durability_interval_seconds=1,
        )
        audio = np.arange(16000, dtype=np.int16)
        writer.write_frames(audio)
        malformed_header = b'{"stored_bytes":0'
        writer._fh.write(len(malformed_header).to_bytes(4, "big"))
        writer._fh.write(malformed_header)
        writer._fh.flush()
        os.fsync(writer._fh.fileno())
        writer._fh.close()
        writer._fh = None

        before_size = writer.path.stat().st_size
        recovered = AudioVaultManager(db).recover_interrupted_recordings()
        after_size = writer.path.stat().st_size

        assert len(recovered) == 1
        assert recovered[0].status == "recovered"
        assert after_size < before_size
        loaded = AudioVaultManager(db).load_audio("rec_malformed")
        np.testing.assert_array_equal(loaded, audio)
    finally:
        db.close()


def test_audio_vault_encrypted_roundtrip(monkeypatch, tmp_path: Path) -> None:
    _configure_paths(monkeypatch, tmp_path)
    keys: dict[str, bytes] = {}

    from src.core import secret_store

    monkeypatch.setattr(secret_store, "store_audio_vault_key", lambda recording_id, key: keys.__setitem__(recording_id, key))
    monkeypatch.setattr(secret_store, "get_audio_vault_key", lambda recording_id: keys.get(recording_id))

    db = TranscriptDB(db_path=tmp_path / "test.db")
    try:
        writer = AudioVaultWriter(
            db=db,
            session_id="rec_encrypted",
            sample_rate=16000,
            durability_interval_seconds=1,
            encrypted=True,
        )
        audio = np.arange(16000, dtype=np.int16)
        writer.write_frames(audio)
        writer.finalize()

        record = db.get_recording_session("rec_encrypted")
        assert record is not None
        assert record.encrypted is True
        assert "rec_encrypted" in keys
        loaded = AudioVaultManager(db).load_audio("rec_encrypted")
        np.testing.assert_array_equal(loaded, audio)
    finally:
        db.close()