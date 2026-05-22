"""Durable audio vault for crash-recoverable recordings."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from numpy.typing import NDArray

from src.core.resource_manager import ResourceManager

if TYPE_CHECKING:
    from src.database.db import RecordingSessionRecord, TranscriptDB

logger = logging.getLogger(__name__)

MAGIC = b"VOCAUD1\n"
VERSION = 1


class AudioVaultError(RuntimeError):
    """Raised when durable audio cannot be written or read safely."""


class AudioVaultWriter:
    """Append-only durable writer for active recordings."""

    def __init__(
        self,
        *,
        db: TranscriptDB,
        session_id: str,
        sample_rate: int = 16000,
        durability_interval_seconds: float = 5.0,
        encrypted: bool = False,
    ) -> None:
        self._db = db
        self._session_id = session_id
        self._sample_rate = int(sample_rate)
        self._chunk_frames = max(1, int(self._sample_rate * max(0.25, durability_interval_seconds)))
        self._vault_dir = ResourceManager.get_user_data_dir() / "audio_vault"
        self._vault_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._vault_dir / f"{session_id}.vocaud"
        self._fh = open(self._path, "xb")  # noqa: SIM115 - explicit lifecycle keeps finalize/discard predictable
        self._pending: list[NDArray[np.int16]] = []
        self._pending_frames = 0
        self._next_chunk = 0
        self._frame_cursor = 0
        self._encrypted = encrypted
        self._aesgcm: Any = None
        self._encryption_key_id: str | None = None

        if encrypted:
            self._enable_encryption()

        self._write_file_header()
        self._db.create_recording_session(
            recording_id=session_id,
            audio_path=self._path,
            sample_rate=self._sample_rate,
            channels=1,
            sample_width_bytes=2,
            encrypted=encrypted,
            encryption_key_id=self._encryption_key_id,
        )
        logger.info("Audio vault opened: %s", self._path.name)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def encrypted(self) -> bool:
        return self._encrypted

    def write_frames(self, frames: NDArray[np.int16]) -> None:
        if self._fh is None or frames.size == 0:
            return
        copied = np.asarray(frames, dtype=np.int16).copy()
        self._pending.append(copied)
        self._pending_frames += int(copied.size)
        while self._pending_frames >= self._chunk_frames:
            self._commit_pending_chunk(self._chunk_frames)

    def finalize(self) -> Path:
        if self._fh is None:
            return self._path
        if self._pending_frames:
            self._commit_pending_chunk(self._pending_frames)
        self._fh.flush()
        os.fsync(self._fh.fileno())
        self._fh.close()
        self._fh = None
        self._db.mark_recording_status(self._session_id, "recorded", finalized=True)
        logger.info("Audio vault finalized: %s (%d chunks)", self._path.name, self._next_chunk)
        return self._path

    def discard(self) -> None:
        if self._fh is not None:
            try:
                self._fh.close()
            finally:
                self._fh = None
        self._path.unlink(missing_ok=True)
        self._db.mark_recording_status(self._session_id, "cancelled", finalized=True)

    def _enable_encryption(self) -> None:
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except Exception as exc:  # pragma: no cover - depends on optional packaging state
            raise AudioVaultError("Encrypted audio vault requires the cryptography package.") from exc

        from src.core.secret_store import store_audio_vault_key

        key = os.urandom(32)
        store_audio_vault_key(self._session_id, key)
        self._aesgcm = AESGCM(key)
        self._encryption_key_id = self._session_id

    def _write_file_header(self) -> None:
        header = {
            "version": VERSION,
            "session_id": self._session_id,
            "sample_rate": self._sample_rate,
            "channels": 1,
            "sample_width_bytes": 2,
            "encrypted": self._encrypted,
            "algorithm": "AES-256-GCM" if self._encrypted else "none",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        payload = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self._fh.write(MAGIC)
        self._fh.write(len(payload).to_bytes(4, "big"))
        self._fh.write(payload)
        self._fh.flush()
        os.fsync(self._fh.fileno())

    def _commit_pending_chunk(self, frame_count: int) -> None:
        frames = self._take_pending_frames(frame_count)
        plaintext = frames.tobytes()
        chunk_header: dict[str, Any] = {
            "chunk_index": self._next_chunk,
            "start_frame": self._frame_cursor,
            "frame_count": int(frames.size),
        }
        payload = plaintext
        if self._encrypted:
            nonce = os.urandom(12)
            aad = f"{self._session_id}:{self._next_chunk}:{self._frame_cursor}:{frames.size}".encode("utf-8")
            payload = self._aesgcm.encrypt(nonce, plaintext, aad)
            chunk_header["nonce"] = nonce.hex()
        chunk_header["stored_bytes"] = len(payload)

        header_payload = json.dumps(chunk_header, sort_keys=True, separators=(",", ":")).encode("utf-8")
        record = len(header_payload).to_bytes(4, "big") + header_payload + payload
        byte_offset = self._fh.tell()
        digest = hashlib.sha256(record).hexdigest()
        self._fh.write(record)
        self._fh.flush()
        os.fsync(self._fh.fileno())
        self._db.add_recording_chunk(
            recording_id=self._session_id,
            chunk_index=self._next_chunk,
            start_frame=self._frame_cursor,
            frame_count=int(frames.size),
            byte_offset=byte_offset,
            byte_count=len(record),
            sha256=digest,
        )
        self._frame_cursor += int(frames.size)
        self._next_chunk += 1

    def _take_pending_frames(self, frame_count: int) -> NDArray[np.int16]:
        chunks: list[NDArray[np.int16]] = []
        remaining = frame_count
        while remaining > 0 and self._pending:
            head = self._pending.pop(0)
            if head.size <= remaining:
                chunks.append(head)
                remaining -= int(head.size)
                self._pending_frames -= int(head.size)
                continue
            chunks.append(head[:remaining].copy())
            self._pending.insert(0, head[remaining:].copy())
            self._pending_frames -= remaining
            remaining = 0
        if not chunks:
            return np.array([], dtype=np.int16)
        return np.concatenate(chunks).astype(np.int16, copy=False)


class AudioVaultManager:
    """Recovery and read access for durable audio vault files."""

    def __init__(self, db: TranscriptDB) -> None:
        self._db = db

    def recover_interrupted_recordings(self) -> list[RecordingSessionRecord]:
        recovered: list[RecordingSessionRecord] = []
        for record in self._db.list_recoverable_recordings():
            path = Path(record.audio_path)
            if record.status in {"recovered", "failed", "recorded"}:
                if path.exists():
                    recovered.append(record)
                continue
            if not path.exists():
                self._db.mark_recording_status(
                    record.id,
                    "failed",
                    failure_reason="Recording metadata survived, but the audio file is missing.",
                    finalized=True,
                )
                updated = self._db.get_recording_session(record.id)
                if updated is not None:
                    recovered.append(updated)
                continue
            self.validate_and_repair(record)
            self._db.mark_recording_status(record.id, "recovered", finalized=True)
            updated = self._db.get_recording_session(record.id)
            if updated is not None:
                recovered.append(updated)
        return recovered

    def load_audio(self, recording_id: str) -> NDArray[np.int16]:
        record = self._db.get_recording_session(recording_id)
        if record is None:
            raise AudioVaultError("Recording not found.")
        chunks = self._read_chunks(record, repair=False)
        if not chunks:
            return np.array([], dtype=np.int16)
        return np.concatenate(chunks).astype(np.int16, copy=False)

    def validate_and_repair(self, record: RecordingSessionRecord) -> None:
        self._read_chunks(record, repair=True)

    def _read_chunks(self, record: RecordingSessionRecord, *, repair: bool) -> list[NDArray[np.int16]]:
        path = Path(record.audio_path)
        if not path.exists():
            raise AudioVaultError(f"Audio vault file missing: {path.name}")
        chunks: list[NDArray[np.int16]] = []
        valid_end = 0
        with open(path, "r+b" if repair else "rb") as handle:
            header = self._read_file_header(handle)
            encrypted = bool(header.get("encrypted"))
            aesgcm = self._load_aesgcm(record.id) if encrypted else None
            while True:
                record_start = handle.tell()
                header_len_raw = handle.read(4)
                if not header_len_raw:
                    valid_end = record_start
                    break
                if len(header_len_raw) != 4:
                    valid_end = record_start
                    break
                header_len = int.from_bytes(header_len_raw, "big")
                header_payload = handle.read(header_len)
                if len(header_payload) != header_len:
                    valid_end = record_start
                    break
                chunk_header = json.loads(header_payload.decode("utf-8"))
                stored_bytes = int(chunk_header["stored_bytes"])
                payload = handle.read(stored_bytes)
                if len(payload) != stored_bytes:
                    valid_end = record_start
                    break
                record_bytes = header_len_raw + header_payload + payload
                digest = hashlib.sha256(record_bytes).hexdigest()
                if encrypted:
                    nonce = bytes.fromhex(chunk_header["nonce"])
                    aad = (
                        f"{record.id}:{chunk_header['chunk_index']}:{chunk_header['start_frame']}:{chunk_header['frame_count']}"
                    ).encode("utf-8")
                    payload = aesgcm.decrypt(nonce, payload, aad)
                frames = np.frombuffer(payload, dtype=np.int16).copy()
                chunks.append(frames)
                self._db.add_recording_chunk(
                    recording_id=record.id,
                    chunk_index=int(chunk_header["chunk_index"]),
                    start_frame=int(chunk_header["start_frame"]),
                    frame_count=int(chunk_header["frame_count"]),
                    byte_offset=record_start,
                    byte_count=len(record_bytes),
                    sha256=digest,
                )
                valid_end = handle.tell()
            if repair:
                handle.truncate(valid_end)
        return chunks

    @staticmethod
    def _read_file_header(handle) -> dict[str, Any]:
        magic = handle.read(len(MAGIC))
        if magic != MAGIC:
            raise AudioVaultError("Invalid audio vault file header.")
        header_len_raw = handle.read(4)
        if len(header_len_raw) != 4:
            raise AudioVaultError("Incomplete audio vault file header.")
        header_len = int.from_bytes(header_len_raw, "big")
        header_payload = handle.read(header_len)
        if len(header_payload) != header_len:
            raise AudioVaultError("Incomplete audio vault metadata.")
        return json.loads(header_payload.decode("utf-8"))

    @staticmethod
    def _load_aesgcm(recording_id: str):
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except Exception as exc:  # pragma: no cover - depends on optional packaging state
            raise AudioVaultError("Encrypted audio vault requires the cryptography package.") from exc

        from src.core.secret_store import get_audio_vault_key

        key = get_audio_vault_key(recording_id)
        if key is None:
            raise AudioVaultError("Encrypted audio key is missing from the local secret store.")
        return AESGCM(key)