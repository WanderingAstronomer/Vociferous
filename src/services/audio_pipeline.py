"""
Unified audio preprocessing pipeline for Vociferous.

Stages: normalize → highpass → Silero VAD → clean speech output.

The noise gate that existed between highpass and VAD has been removed:
Whisper large-v3 was trained on raw noisy audio, and digital-zero
regions created by a gate are out-of-distribution — causing
hallucinations, soft phoneme loss (/h/, /f/, /s/), and word-boundary
truncation.  RMS normalization + 100 Hz highpass is sufficient signal
sanitization.  Silero VAD handles speech/silence discrimination.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from src.core.model_registry import SILERO_VAD
from src.core.resource_manager import ResourceManager

logger = logging.getLogger(__name__)


class AudioPipeline:
    """Unified audio preprocessor: int16 in → clean float32 speech out.

    Pipeline stages:
      1. int16 → float32 normalization
      2. RMS normalization to consistent amplitude
      3. First-order IIR highpass @ 100 Hz (DC offset, hum, rumble)
      4. Silero VAD speech/silence classification per 32 ms chunk
      5. Extract speech segments with hysteresis, asymmetric padding,
         and inter-segment silence insertion

    The noise gate that was previously Stage 4 has been removed: Whisper
    large-v3 was trained on raw noisy audio. Digital-zero regions created
    by a gate are out-of-distribution and cause hallucinations, soft
    phoneme loss (/h/, /f/, /s/), and word-boundary truncation.

    Returns None from :meth:`process` when no meaningful speech is detected
    (replaces ``_is_effective_silence`` + all trim functions).
    """

    # ── Silero VAD parameters ──
    _CHUNK_SIZE: int = 512  # 32 ms at 16 kHz — Silero's native chunk size
    _SPEECH_THRESHOLD: float = 0.45  # activation threshold (enter speech)
    _SPEECH_EXIT_THRESHOLD: float = 0.35  # deactivation threshold (hysteresis)
    _MIN_SILENCE_CHUNKS: int = 47  # ~1500 ms pause before splitting segments
    _PRE_SPEECH_PAD_CHUNKS: int = 7  # ~224 ms pre-roll (capture consonant attack)
    _POST_SPEECH_PAD_CHUNKS: int = 13  # ~416 ms post-roll (trailing silence for punctuation)
    _MIN_SPEECH_CHUNKS: int = 8  # ~256 ms minimum speech segment (filter transients)

    # ── Pre-processing parameters ──
    _HIGHPASS_CUTOFF: float = 100.0  # Hz (below fundamental speech floor ~85 Hz)
    _TARGET_RMS: float = 0.1  # normalization target
    _SILENCE_RMS_FLOOR: float = 1e-5  # fast pre-check: dead silence

    # ── Inter-segment silence ──
    _INTER_SEGMENT_SILENCE_MS: int = 300  # silence insert between split segments

    def __init__(self, sample_rate: int = 16000) -> None:
        self.sample_rate = sample_rate
        self._session: Any = None  # onnxruntime.InferenceSession (deferred import)

        # Pre-compute highpass filter coefficient
        rc = 1.0 / (2.0 * np.pi * self._HIGHPASS_CUTOFF)
        dt = 1.0 / self.sample_rate
        self._hp_alpha: float = rc / (rc + dt)

    # ------------------------------------------------------------------
    # VAD model lifecycle
    # ------------------------------------------------------------------

    def _load_vad_model(self) -> Any:
        """Load or return cached Silero VAD ONNX session."""
        if self._session is not None:
            return self._session

        import onnxruntime  # deferred import — heavy C library

        model_path = self._resolve_model_path()
        if not model_path.exists():
            self._auto_provision(model_path)

        self._session = onnxruntime.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )
        logger.info("Silero VAD model loaded from %s", model_path)
        return self._session

    @staticmethod
    def _resolve_model_path() -> Path:
        cache_dir = ResourceManager.get_user_cache_dir("models")
        return cache_dir / SILERO_VAD.filename

    @staticmethod
    def _auto_provision(model_path: Path) -> None:
        """Auto-download the VAD model if missing (~2 MB, near-instant)."""
        from src.provisioning.core import ProvisioningError, download_model_file

        logger.info("Silero VAD model not found, downloading (~2 MB)...")
        try:
            download_model_file(
                repo_id=SILERO_VAD.repo,
                filename=SILERO_VAD.filename,
                target_dir=model_path.parent,
                expected_sha256=SILERO_VAD.sha256,
            )
        except ProvisioningError:
            raise
        except Exception as e:
            raise ProvisioningError(
                f"Failed to download Silero VAD model: {e}. Run 'make provision' or ensure internet connectivity."
            ) from e

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(
        self,
        audio: NDArray[np.int16],
        sample_rate: int = 16000,
    ) -> NDArray[np.float32] | None:
        """Full pipeline: int16 input → clean float32 speech, or None.

        Returns None when no meaningful speech is detected.
        """
        if audio.size == 0:
            return None

        self.sample_rate = sample_rate

        # Stage 1: int16 -> float32 (do this once; reused by RMS pre-check)
        audio_f32: NDArray[np.float32] = audio.astype(np.float32) / 32768.0

        # Stage 0: Fast energy pre-check — skip everything on dead silence
        rms = float(np.sqrt(np.mean(audio_f32**2)))
        if rms < self._SILENCE_RMS_FLOOR:
            logger.info("Dead silence (RMS=%.6f), skipping pipeline", rms)
            return None

        # Stage 2: RMS normalization (reuse pre-computed RMS from Stage 0)
        audio_f32 = self._rms_normalize(audio_f32, current_rms=rms)

        # Stage 3: Highpass filter @ 100 Hz
        audio_f32 = self._highpass(audio_f32)

        # Stage 4: Silero VAD classification
        speech_probs = self._vad_classify(audio_f32)

        # Stage 5: Extract speech segments (hysteresis + inter-segment silence)
        result = self._extract_speech(audio_f32, speech_probs)

        if result is None or result.size == 0:
            logger.info("No speech segments after VAD processing")
            return None

        return result

    # ------------------------------------------------------------------
    # Pipeline stages
    # ------------------------------------------------------------------

    def _rms_normalize(
        self, audio: NDArray[np.float32], current_rms: float | None = None
    ) -> NDArray[np.float32]:
        """Scale audio to a consistent RMS level.

        Ensures quiet mic recordings and loud recordings enter downstream
        stages at the same level so thresholds work consistently.

        Args:
            audio: float32 audio samples.
            current_rms: Pre-computed RMS to avoid redundant calculation.
        """
        if current_rms is None:
            current_rms = float(np.sqrt(np.mean(audio**2)))
        if current_rms < 1e-8:
            return audio
        gain = min(self._TARGET_RMS / current_rms, 10.0)
        return np.clip(audio * gain, -1.0, 1.0).astype(np.float32)

    def _highpass(self, audio: NDArray[np.float32]) -> NDArray[np.float32]:
        """First-order IIR highpass filter.

        Removes DC offset, AC hum (50/60 Hz), and sub-bass rumble below
        100 Hz.  No effect on speech content — fundamental floor is ~85 Hz.

        Uses a recursive filter: ``y[n] = α·(y[n-1] + x[n] - x[n-1])``.
        For a 10 s recording at 16 kHz that's ~160 k iterations in Python.
        IIR recurrences are inherently sequential — vectorizing with pure
        NumPy is numerically unstable for long sequences, and adding
        ``scipy.signal.lfilter`` isn't worth the 40 MB dependency for a
        one-shot postprocessing step that completes in tens of milliseconds.
        """
        alpha = self._hp_alpha
        n = len(audio)
        out = np.empty(n, dtype=np.float32)
        out[0] = audio[0]
        for i in range(1, n):
            out[i] = alpha * (out[i - 1] + audio[i] - audio[i - 1])
        return out

    def _vad_classify(self, audio: NDArray[np.float32]) -> list[float]:
        """Run Silero VAD on 32 ms chunks, return speech probability per chunk."""
        session = self._load_vad_model()

        chunk_size = self._CHUNK_SIZE
        n_chunks = len(audio) // chunk_size

        # Silero VAD v5 state: single tensor [2, batch=1, 128]
        state = np.zeros((2, 1, 128), dtype=np.float32)
        sr = np.array(self.sample_rate, dtype=np.int64)

        probabilities: list[float] = []

        for i in range(n_chunks):
            start = i * chunk_size
            end = start + chunk_size
            chunk_data = audio[start:end].reshape(1, -1)

            ort_inputs = {
                "input": chunk_data,
                "state": state,
                "sr": sr,
            }

            output, state = session.run(None, ort_inputs)
            probabilities.append(float(output[0][0]))

        return probabilities

    def _extract_speech(
        self,
        audio: NDArray[np.float32],
        speech_probs: list[float],
    ) -> NDArray[np.float32] | None:
        """Extract speech segments using VAD probabilities with hysteresis.

        Uses a two-threshold state machine: activation at _SPEECH_THRESHOLD,
        deactivation at _SPEECH_EXIT_THRESHOLD (lower).  This prevents
        mid-word cutoffs during brief energy dips (fricatives, nasals).

        Segments separated by short silence (< _MIN_SILENCE_CHUNKS) are merged
        to preserve natural phrasing context for Whisper.  Segments that remain
        separate get a brief low-level noise insert between them — Whisper
        needs silence *duration* to generate punctuation, but digital zero is
        out-of-distribution, so we use Gaussian noise at ~-80 dBFS instead.
        """
        if not speech_probs:
            return None

        chunk_size = self._CHUNK_SIZE
        n_chunks = len(speech_probs)

        # Classify chunks with hysteresis (two-threshold state machine).
        # Once speech is detected (p >= SPEECH_THRESHOLD), we stay in speech
        # until p drops below SPEECH_EXIT_THRESHOLD.  This prevents the VAD
        # from cutting out during mid-word energy dips (fricatives, nasals).
        is_speech: list[bool] = []
        in_speech = False
        for p in speech_probs:
            if in_speech:
                in_speech = p >= self._SPEECH_EXIT_THRESHOLD
            else:
                in_speech = p >= self._SPEECH_THRESHOLD
            is_speech.append(in_speech)

        # Find contiguous speech runs
        segments: list[tuple[int, int]] = []  # (start_chunk, end_chunk)
        i = 0
        while i < n_chunks:
            if is_speech[i]:
                seg_start = i
                while i < n_chunks and is_speech[i]:
                    i += 1
                seg_end = i
                if (seg_end - seg_start) >= self._MIN_SPEECH_CHUNKS:
                    segments.append((seg_start, seg_end))
            else:
                i += 1

        if not segments:
            return None

        # Merge segments separated by short silence (preserve natural pauses)
        merged: list[tuple[int, int]] = [segments[0]]
        for seg_start, seg_end in segments[1:]:
            _, prev_end = merged[-1]
            gap = seg_start - prev_end
            if gap <= self._MIN_SILENCE_CHUNKS:
                merged[-1] = (merged[-1][0], seg_end)
            else:
                merged.append((seg_start, seg_end))

        # Extract audio for each segment with asymmetric padding.
        # Pre-roll captures consonant attack; post-roll captures word-final
        # decay and provides silence for Whisper's punctuation decoder.
        parts: list[NDArray[np.float32]] = []
        for seg_start, seg_end in merged:
            padded_start = max(0, seg_start - self._PRE_SPEECH_PAD_CHUNKS)
            padded_end = min(n_chunks, seg_end + self._POST_SPEECH_PAD_CHUNKS)
            sample_start = padded_start * chunk_size
            sample_end = min(padded_end * chunk_size, len(audio))
            parts.append(audio[sample_start:sample_end])

        if not parts:
            return None

        # Assemble segments with inter-segment silence.
        # Whisper uses silence duration to decide punctuation tokens.
        # Digital zero is out-of-distribution (trained on real noisy audio),
        # so we insert low-level Gaussian noise (~-80 dBFS) instead.
        if len(parts) > 1:
            silence_samples = int(self._INTER_SEGMENT_SILENCE_MS * self.sample_rate / 1000)
            rng = np.random.default_rng(42)
            assembled: list[NDArray[np.float32]] = [parts[0]]
            for part in parts[1:]:
                silence = rng.normal(0, 1e-4, silence_samples).astype(np.float32)
                assembled.append(silence)
                assembled.append(part)
            result = np.concatenate(assembled)
        else:
            result = parts[0]

        # Log diagnostics
        original_ms = len(audio) / self.sample_rate * 1000
        result_ms = len(result) / self.sample_rate * 1000
        removed_pct = (1 - len(result) / len(audio)) * 100
        n_segs = len(merged)

        if removed_pct > 1.0:
            logger.info(
                "VAD: %.0fms → %.0fms (%.1f%% silence removed, %d segment%s)",
                original_ms,
                result_ms,
                removed_pct,
                n_segs,
                "s" if n_segs != 1 else "",
            )

        return result
