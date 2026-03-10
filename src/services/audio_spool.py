"""
AudioSpoolWriter — incremental disk spooling for crash-resilient recording.

Writes raw PCM int16 frames to a spool file on disk as recording progresses.
If the process crashes, the spool file survives with all audio captured up to
the last flush.  After recording completes normally, the spool is either
promoted to the audio cache (WAV) or discarded.

Spool files live in ``<cache_dir>/audio_spool/`` and are named by ISO timestamp.
Format is raw int16 mono PCM (no header) — fast append-only writes, trivially
convertible to WAV after the fact.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from src.core.resource_manager import ResourceManager

logger = logging.getLogger(__name__)

# Flush to disk every ~1 second of 16 kHz mono int16 (32 KB).
_FLUSH_THRESHOLD_BYTES = 32_000


class AudioSpoolWriter:
    """Append-only raw PCM spool writer with periodic flushing."""

    def __init__(self, session_id: str, sample_rate: int = 16000) -> None:
        self._sample_rate = sample_rate
        self._spool_dir = ResourceManager.get_user_cache_dir("audio_spool")
        self._spool_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._spool_dir / f"{session_id}.pcm"
        self._fh = open(self._path, "wb")  # noqa: SIM115 — intentional manual lifecycle
        self._buffer = bytearray()
        self._total_bytes = 0
        logger.debug("Spool opened: %s", self._path)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def write_frames(self, frames: NDArray[np.int16]) -> None:
        """Buffer frames and flush to disk when threshold reached."""
        raw = frames.tobytes()
        self._buffer.extend(raw)
        if len(self._buffer) >= _FLUSH_THRESHOLD_BYTES:
            self._flush()

    def _flush(self) -> None:
        if self._fh is None or not self._buffer:
            return
        self._fh.write(self._buffer)
        self._fh.flush()
        self._total_bytes += len(self._buffer)
        self._buffer.clear()

    def finalize(self) -> Path:
        """Flush remaining data, close file, return path."""
        self._flush()
        if self._fh is not None:
            self._fh.close()
            self._fh = None
        duration_s = self._total_bytes / (self._sample_rate * 2)
        logger.info("Spool finalized: %s (%.1fs, %d bytes)", self._path.name, duration_s, self._total_bytes)
        return self._path

    def discard(self) -> None:
        """Close and delete the spool file (used on cancel)."""
        if self._fh is not None:
            self._fh.close()
            self._fh = None
        try:
            self._path.unlink(missing_ok=True)
            logger.debug("Spool discarded: %s", self._path.name)
        except OSError:
            logger.warning("Failed to delete spool file: %s", self._path, exc_info=True)

    def __del__(self) -> None:
        if self._fh is not None:
            try:
                self._flush()
                self._fh.close()
            except Exception:
                pass
            self._fh = None
