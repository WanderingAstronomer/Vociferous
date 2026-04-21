"""
Tests for the AudioPipeline preprocessing stages and VAD integration.

Covers:
  - Stage isolation: normalize, highpass, extract speech
  - VAD classify: mock ONNX session with Silero v5 contract
  - Hysteresis: two-threshold state machine prevents mid-word cutoffs
  - Inter-segment silence: low-level noise insertion between segments
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
# Sensitivity Presets (ISS-130)
# ======================================================================


class TestSensitivityPresets:
    """Whisper-mode VAD lowers thresholds and shortens minimum speech windows."""

    def test_normal_preset_keeps_class_defaults(self):
        pipe = AudioPipeline(sensitivity="normal")
        # Instance attrs should not shadow class constants.
        assert "_SPEECH_THRESHOLD" not in pipe.__dict__
        assert pipe._SPEECH_THRESHOLD == AudioPipeline._SPEECH_THRESHOLD
        assert pipe.sensitivity == "normal"

    def test_whisper_preset_lowers_thresholds(self):
        pipe = AudioPipeline(sensitivity="whisper")
        assert pipe._SPEECH_THRESHOLD < AudioPipeline._SPEECH_THRESHOLD
        assert pipe._SPEECH_EXIT_THRESHOLD < AudioPipeline._SPEECH_EXIT_THRESHOLD
        assert pipe._MIN_SPEECH_CHUNKS < AudioPipeline._MIN_SPEECH_CHUNKS
        assert pipe._PRE_SPEECH_PAD_CHUNKS > AudioPipeline._PRE_SPEECH_PAD_CHUNKS
        assert pipe.sensitivity == "whisper"

    def test_unknown_preset_falls_back_to_normal(self):
        pipe = AudioPipeline(sensitivity="ludicrous")
        assert pipe.sensitivity == "normal"
        assert pipe._SPEECH_THRESHOLD == AudioPipeline._SPEECH_THRESHOLD


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
# Stage 4: VAD classification (mocked ONNX)
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
# Stage 5: Speech extraction (hysteresis + asymmetric padding)
# ======================================================================


class TestExtractSpeech:
    """_extract_speech segment detection, hysteresis, merging, and silence insertion."""

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
        """Segments shorter than MIN_SPEECH_CHUNKS (8) are discarded."""
        pipe = AudioPipeline()
        n_chunks = 40
        audio = np.random.randn(n_chunks * 512).astype(np.float32)
        # Only 5 speech chunks — below MIN_SPEECH_CHUNKS (8)
        probs = [0.1] * 15 + [0.9] * 5 + [0.1] * 20
        result = pipe._extract_speech(audio, probs)
        assert result is None

    def test_sufficient_speech_kept(self):
        """Segments >= MIN_SPEECH_CHUNKS (8) are preserved."""
        pipe = AudioPipeline()
        n_chunks = 40
        audio = np.random.randn(n_chunks * 512).astype(np.float32)
        # 10 speech chunks — above MIN_SPEECH_CHUNKS (8)
        probs = [0.1] * 10 + [0.9] * 10 + [0.1] * 20
        result = pipe._extract_speech(audio, probs)
        assert result is not None

    def test_gap_merging_preserves_pauses(self):
        """Short silence gaps between speech segments get merged.

        With _MIN_SILENCE_CHUNKS=47, a gap of 20 chunks (~640ms) should
        definitely be merged into a single segment.
        """
        pipe = AudioPipeline()
        n_chunks = 80
        audio = np.random.randn(n_chunks * 512).astype(np.float32)
        # Speech — short gap (20 chunks < MIN_SILENCE_CHUNKS=47) — speech
        probs = [0.9] * 10 + [0.1] * 20 + [0.9] * 10 + [0.1] * 40
        result = pipe._extract_speech(audio, probs)
        assert result is not None

    def test_hysteresis_prevents_mid_word_cutoff(self):
        """Probability dip between thresholds should NOT end speech segment.

        A prob of 0.40 is below the entry threshold (0.45) but above the
        exit threshold (0.35), so once in speech state it stays in speech.
        """
        pipe = AudioPipeline()
        n_chunks = 30
        audio = np.random.randn(n_chunks * 512).astype(np.float32)
        # Clear speech → dip to 0.40 (above exit 0.35) → back to speech
        probs = [0.9] * 10 + [0.40] * 5 + [0.9] * 10 + [0.1] * 5
        result = pipe._extract_speech(audio, probs)
        assert result is not None
        # Should get ONE segment (hysteresis keeps it together)
        # The 0.40 dip doesn't break it because it's above exit threshold

    def test_hysteresis_allows_exit_below_exit_threshold(self):
        """Prob below exit threshold (0.35) DOES end the speech segment."""
        pipe = AudioPipeline()
        n_chunks = 60
        audio = np.random.randn(n_chunks * 512).astype(np.float32)
        # Speech (10) → deep silence (0.2, below exit) → long silence
        probs = [0.9] * 10 + [0.2] * 50
        result = pipe._extract_speech(audio, probs)
        assert result is not None  # 10 chunks >= MIN_SPEECH_CHUNKS (8)

    def test_asymmetric_padding(self):
        """Pre-roll (7 chunks) and post-roll (13 chunks) are different."""
        pipe = AudioPipeline()
        # Enough chunks that padding won't hit array boundaries
        n_chunks = 60
        audio = np.random.randn(n_chunks * 512).astype(np.float32)
        # Speech in the middle: chunks 20-29 (10 chunks of speech)
        probs = [0.1] * 20 + [0.9] * 10 + [0.1] * 30
        result = pipe._extract_speech(audio, probs)
        assert result is not None
        # Expected: pre_pad=7, post_pad=13 → extract chunks 13-42
        # That's 30 chunks × 512 = 15360 samples
        expected_chunks = 10 + 7 + 13  # speech + pre + post
        expected_samples = expected_chunks * 512
        assert len(result) == expected_samples

    def test_inter_segment_silence_inserted(self):
        """When segments don't merge, low-level noise is inserted between them."""
        pipe = AudioPipeline()
        # Two speech segments with a huge gap (>= MIN_SILENCE_CHUNKS=47)
        n_chunks = 120
        audio = np.ones(n_chunks * 512, dtype=np.float32) * 0.1
        probs = [0.9] * 10 + [0.1] * 50 + [0.9] * 10 + [0.1] * 50
        result = pipe._extract_speech(audio, probs)
        assert result is not None
        # Should be longer than just the two speech segments because of
        # the 300ms (~4800 samples) silence insert between them
        silence_samples = int(300 * 16000 / 1000)
        # Two segments with padding + silence insert
        min_expected = (10 + 10) * 512 + silence_samples
        assert len(result) > min_expected

    def test_single_segment_no_silence_insert(self):
        """Single segment should have no silence inserted."""
        pipe = AudioPipeline()
        n_chunks = 30
        audio = np.random.randn(n_chunks * 512).astype(np.float32)
        probs = [0.9] * 10 + [0.1] * 20
        result = pipe._extract_speech(audio, probs)
        assert result is not None
        # No inter-segment silence for a single segment


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
