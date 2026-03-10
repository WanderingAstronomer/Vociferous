"""
AudioCacheManager — WAV cache for recorded audio with LRU pruning.

After a recording is successfully transcribed, its raw PCM spool file is
converted to a standard WAV and cached under ``<cache_dir>/audio_cache/``.
Cache size is bounded by a user-configurable duration limit (minutes);
the oldest WAV files are evicted first.

WAV format: 16 kHz, mono, int16 — ~1.9 MB per minute.  No compression needed.

On startup, ``cleanup_stale_spools()`` scans the spool directory for orphaned
``.pcm`` files left by crashes and logs warnings so the user knows they exist.
"""

from __future__ import annotations

import logging
import wave
from pathlib import Path

from src.core.resource_manager import ResourceManager

logger = logging.getLogger(__name__)


class AudioCacheManager:
    """Manages a bounded WAV cache of recorded audio."""

    def __init__(self, sample_rate: int = 16000) -> None:
        self._sample_rate = sample_rate
        self._cache_dir = ResourceManager.get_user_cache_dir("audio_cache")
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._spool_dir = ResourceManager.get_user_cache_dir("audio_spool")

    @property
    def cache_dir(self) -> Path:
        return self._cache_dir

    # ------------------------------------------------------------------
    # Store & convert
    # ------------------------------------------------------------------

    def store(self, transcript_id: int, pcm_path: Path, max_cache_minutes: float) -> Path | None:
        """Convert raw PCM spool to WAV and cache it.  Prune if over limit.

        Returns the WAV path on success, None if caching is disabled (max=0)
        or the spool file is missing.
        """
        if max_cache_minutes <= 0:
            self._delete_file(pcm_path)
            return None

        if not pcm_path.exists():
            logger.warning("Spool file missing, cannot cache: %s", pcm_path)
            return None

        wav_path = self._cache_dir / f"{transcript_id}.wav"
        try:
            self._pcm_to_wav(pcm_path, wav_path)
            self._delete_file(pcm_path)
            logger.info("Audio cached: %s (%.1fs)", wav_path.name, self._wav_duration_s(wav_path))
        except Exception:
            logger.exception("Failed to convert spool to WAV: %s", pcm_path)
            return None

        self.prune(max_cache_minutes)
        return wav_path

    def get_path(self, transcript_id: int) -> Path | None:
        """Return the cached WAV path if it exists, else None."""
        p = self._cache_dir / f"{transcript_id}.wav"
        return p if p.exists() else None

    # ------------------------------------------------------------------
    # Pruning
    # ------------------------------------------------------------------

    def prune(self, max_minutes: float) -> None:
        """Delete oldest WAV files until total cached duration <= max_minutes."""
        if max_minutes <= 0:
            return

        wav_files = sorted(self._cache_dir.glob("*.wav"), key=lambda p: p.stat().st_mtime)
        total_s = sum(self._file_duration_s(f) for f in wav_files)
        max_s = max_minutes * 60.0

        while total_s > max_s and wav_files:
            oldest = wav_files.pop(0)
            dur = self._file_duration_s(oldest)
            self._delete_file(oldest)
            total_s -= dur
            logger.info("Pruned cached audio: %s (%.1fs, cache now %.1fs / %.1fs)", oldest.name, dur, total_s, max_s)

    # ------------------------------------------------------------------
    # Startup: orphan spool detection
    # ------------------------------------------------------------------

    def cleanup_stale_spools(self) -> list[Path]:
        """Scan spool dir for orphaned .pcm files from crashed sessions.

        Returns list of orphan paths.  Files are NOT deleted — they may
        contain recoverable audio.
        """
        if not self._spool_dir.exists():
            return []

        orphans: list[Path] = []
        for pcm in self._spool_dir.glob("*.pcm"):
            size = pcm.stat().st_size
            dur_s = size / (self._sample_rate * 2) if size > 0 else 0
            logger.warning(
                "Orphaned audio spool from crashed session: %s (%.1fs, %d bytes). "
                "File preserved in %s for manual recovery.",
                pcm.name,
                dur_s,
                size,
                self._spool_dir,
            )
            orphans.append(pcm)
        return orphans

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _pcm_to_wav(self, pcm_path: Path, wav_path: Path) -> None:
        """Convert raw int16 mono PCM to a standard WAV file."""
        pcm_data = pcm_path.read_bytes()
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # int16
            wf.setframerate(self._sample_rate)
            wf.writeframes(pcm_data)

    def _wav_duration_s(self, wav_path: Path) -> float:
        """Read WAV header to get accurate duration."""
        try:
            with wave.open(str(wav_path), "rb") as wf:
                return wf.getnframes() / wf.getframerate()
        except Exception:
            return self._file_duration_s(wav_path)

    def _file_duration_s(self, path: Path) -> float:
        """Estimate duration from file size (int16 mono, known sample rate)."""
        try:
            size = path.stat().st_size
            # WAV header is 44 bytes; for raw PCM it's 0.  Close enough.
            data_bytes = max(0, size - 44)
            return data_bytes / (self._sample_rate * 2)
        except OSError:
            return 0.0

    @staticmethod
    def _delete_file(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to delete: %s", path, exc_info=True)
