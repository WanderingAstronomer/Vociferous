"""
Tests for the AudioPipeline preprocessing stages and VAD integration.

Covers:
  - Stage isolation: normalize, highpass, noise gate, extract speech
  - VAD classify: mock ONNX session with Silero v5 contract
  - Full pipeline: end-to-end with mocked VAD
  - Edge cases: empty, silence, single-chunk

No real ONNX model is loaded — onnxruntime.InferenceSession is mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.services.audio_pipeline import AudioPipeline

# ======================================================================
# Helpers
# ======================================================================


def _make_tone(
    freq: float = 440.0,
    duration_s: float = 0.5,
    sample_rate: int = 16000,
    amplitude: float = 0.5,
) -> np.ndarray:
    """Generate a pure sine tone as int16."""
    t = np.arange(int(duration_s * sample_rate)) / sample_rate
    return (amplitude * 32767 * np.sin(2 * np.pi * freq * t)).astype(np.int16)


def _make_silence(duration_s: float = 0.5, sample_rate: int = 16000) -> np.ndarray:
    return np.zeros(int(duration_s * sample_rate), dtype=np.int16)


def _build_mock_session(speech_prob: float = 0.9) -> MagicMock:
    """Build a mock ONNX InferenceSession that mimics Silero VAD v5.

    Returns (output, stateN) matching the v5 contract:
      - output: shape [1, 1], dtype float32
      - stateN: shape [2, 1, 128], dtype float32
    """
    session = MagicMock()

    def run_side_effect(_output_names, inputs):
        state = inputs["state"]
        output = np.array([[speech_prob]], dtype=np.float32)
        state_n = np.zeros_like(state)
        return [output, state_n]

    session.run.side_effect = run_side_effect
    return session


# ======================================================================
# Stage 1+2: Normalization
# ======================================================================


class TestRMSNormalize:
    """_rms_normalize produces consistent output amplitude."""

    def test_loud_input_scaled_down(self):
        pipe = AudioPipeline()
        loud = np.full(1600, 0.8, dtype=np.float32)
        result = pipe._rms_normalize(loud)
        rms = float(np.sqrt(np.mean(result**2)))
        assert abs(rms - pipe._TARGET_RMS) < 0.01

    def test_quiet_input_scaled_up(self):
        pipe = AudioPipeline()
        quiet = np.full(1600, 0.001, dtype=np.float32)
        result = pipe._rms_normalize(quiet)
        rms = float(np.sqrt(np.mean(result**2)))
        assert rms > 0.001  # should be amplified

    def test_dead_silence_unchanged(self):
        pipe = AudioPipeline()
        silence = np.zeros(1600, dtype=np.float32)
        result = pipe._rms_normalize(silence)
        assert np.allclose(result, silence)


# ======================================================================
# Stage 3: Highpass filter
# ======================================================================


class TestHighpass:
    """First-order IIR highpass removes low frequencies."""

    def test_dc_offset_removed(self):
        pipe = AudioPipeline()
        # Signal with large DC offset
        dc = np.full(16000, 0.5, dtype=np.float32)
        result = pipe._highpass(dc)
        # After settling, output should be near zero (DC removed)
        assert abs(np.mean(result[-1000:])) < 0.01

    def test_speech_band_preserved(self):
        pipe = AudioPipeline()
        # 300 Hz tone — should pass through mostly intact
        t = np.arange(16000) / 16000.0
        tone = (0.3 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
        result = pipe._highpass(tone)
        # RMS should still be substantial (not attenuated to nothing)
        rms_in = float(np.sqrt(np.mean(tone**2)))
        rms_out = float(np.sqrt(np.mean(result[-8000:] ** 2)))
        assert rms_out > 0.5 * rms_in


# ======================================================================
# Stage 4: Noise gate
# ======================================================================


class TestNoiseGate:
    """Fine gate zeros frames below threshold while preserving speech."""

    def test_very_quiet_frames_zeroed(self):
        pipe = AudioPipeline()
        # Signal well below gate threshold (-52 dBFS ≈ 0.0025 linear)
        quiet = np.full(512, 0.0001, dtype=np.float32)
        result = pipe._noise_gate(quiet)
        assert np.allclose(result[:512], 0.0)

    def test_loud_frames_preserved(self):
        pipe = AudioPipeline()
        loud = np.full(512, 0.1, dtype=np.float32)
        result = pipe._noise_gate(loud)
        assert np.array_equal(result[:512], loud[:512])


# ======================================================================
# Stage 5: VAD classification (mocked ONNX)
# ======================================================================


class TestVADClassify:
    """_vad_classify with mock ONNX session using Silero v5 contract."""

    def test_returns_probabilities_per_chunk(self):
        pipe = AudioPipeline(sample_rate=16000)
        mock_session = _build_mock_session(speech_prob=0.8)
        pipe._session = mock_session

        # 10 chunks × 512 samples = 5120 samples
        audio = np.random.randn(5120).astype(np.float32) * 0.1
        probs = pipe._vad_classify(audio)

        assert len(probs) == 10
        assert all(abs(p - 0.8) < 0.01 for p in probs)

    def test_silero_v5_input_contract(self):
        """Verify the exact input tensor names and shapes for Silero VAD v5."""
        pipe = AudioPipeline(sample_rate=16000)
        mock_session = _build_mock_session()
        pipe._session = mock_session

        audio = np.random.randn(512).astype(np.float32) * 0.1
        pipe._vad_classify(audio)

        # Verify the session was called with correct Silero v5 keys
        call_args = mock_session.run.call_args
        inputs = call_args[0][1]  # second positional arg to run()
        assert "input" in inputs
        assert "state" in inputs  # v5: single 'state', NOT 'h' and 'c'
        assert "sr" in inputs
        assert "h" not in inputs  # v4 API — must NOT be present
        assert "c" not in inputs  # v4 API — must NOT be present

        # Verify state shape: [2, 1, 128]
        assert inputs["state"].shape == (2, 1, 128)

    def test_empty_audio_returns_empty(self):
        pipe = AudioPipeline()
        pipe._session = _build_mock_session()
        probs = pipe._vad_classify(np.array([], dtype=np.float32))
        assert probs == []

    def test_state_propagates_between_chunks(self):
        """State output from one chunk feeds into the next chunk."""
        pipe = AudioPipeline(sample_rate=16000)
        call_count = 0
        states_seen: list[np.ndarray] = []

        def tracked_run(_output_names, inputs):
            nonlocal call_count
            states_seen.append(inputs["state"].copy())
            call_count += 1
            output = np.array([[0.5]], dtype=np.float32)
            # Return a distinctive state so we can verify propagation
            state_n = np.full_like(inputs["state"], call_count * 0.1)
            return [output, state_n]

        session = MagicMock()
        session.run.side_effect = tracked_run
        pipe._session = session

        audio = np.random.randn(1024).astype(np.float32) * 0.1  # 2 chunks
        pipe._vad_classify(audio)

        assert call_count == 2
        # First call should get zeros; second should get the modified state
        assert np.allclose(states_seen[0], 0.0)
        assert np.allclose(states_seen[1], 0.1)  # propagated from chunk 1


# ======================================================================
# Stage 6: Speech extraction
# ======================================================================


class TestExtractSpeech:
    """_extract_speech segment detection and merging."""

    def test_all_speech_returns_full_audio(self):
        pipe = AudioPipeline()
        audio = np.random.randn(5120).astype(np.float32)
        probs = [0.9] * 10  # all speech
        result = pipe._extract_speech(audio, probs)
        assert result is not None
        # With padding, should return essentially everything
        assert len(result) >= len(audio) * 0.5

    def test_all_silence_returns_none(self):
        pipe = AudioPipeline()
        audio = np.random.randn(5120).astype(np.float32)
        probs = [0.1] * 10  # all silence
        result = pipe._extract_speech(audio, probs)
        assert result is None

    def test_empty_probs_returns_none(self):
        pipe = AudioPipeline()
        result = pipe._extract_speech(np.zeros(512, dtype=np.float32), [])
        assert result is None

    def test_short_speech_filtered_out(self):
        """Segments shorter than MIN_SPEECH_CHUNKS are discarded."""
        pipe = AudioPipeline()
        n_chunks = 20
        audio = np.random.randn(n_chunks * 512).astype(np.float32)
        # Only 1 speech chunk — below MIN_SPEECH_CHUNKS (3)
        probs = [0.1] * 9 + [0.9] + [0.1] * 10
        result = pipe._extract_speech(audio, probs)
        assert result is None

    def test_gap_merging_preserves_pauses(self):
        """Short silence gaps between speech segments get merged."""
        pipe = AudioPipeline()
        n_chunks = 30
        audio = np.random.randn(n_chunks * 512).astype(np.float32)
        # Speech — short gap (< MIN_SILENCE_CHUNKS=12) — speech
        probs = [0.9] * 5 + [0.1] * 5 + [0.9] * 5 + [0.1] * 15
        result = pipe._extract_speech(audio, probs)
        assert result is not None


# ======================================================================
# Full pipeline (mocked VAD)
# ======================================================================


class TestFullPipeline:
    """End-to-end process() with mocked ONNX session."""

    @patch("src.services.audio_pipeline.AudioPipeline._load_vad_model")
    def test_speech_audio_returns_float32(self, mock_load: MagicMock):
        mock_load.return_value = _build_mock_session(speech_prob=0.95)
        pipe = AudioPipeline()
        tone = _make_tone(freq=300, duration_s=1.0, amplitude=0.5)
        result = pipe.process(tone)
        assert result is not None
        assert result.dtype == np.float32
        assert len(result) > 0

    @patch("src.services.audio_pipeline.AudioPipeline._load_vad_model")
    def test_silence_returns_none(self, mock_load: MagicMock):
        mock_load.return_value = _build_mock_session(speech_prob=0.1)
        pipe = AudioPipeline()
        silence = _make_silence(duration_s=1.0)
        result = pipe.process(silence)
        assert result is None

    def test_empty_array_returns_none(self):
        pipe = AudioPipeline()
        result = pipe.process(np.array([], dtype=np.int16))
        assert result is None

    @patch("src.services.audio_pipeline.AudioPipeline._load_vad_model")
    def test_dead_silence_skips_vad(self, mock_load: MagicMock):
        """Absolute zero audio should be caught by pre-check before VAD runs."""
        pipe = AudioPipeline()
        result = pipe.process(np.zeros(16000, dtype=np.int16))
        assert result is None
        mock_load.assert_not_called()  # VAD model never loaded
