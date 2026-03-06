"""Tests for transcription service post-processing and audio pipeline stages."""

import numpy as np
import pytest

from src.core.settings import get_settings
from src.services.audio_pipeline import AudioPipeline
from src.services.transcription_service import _merge_segment_texts, post_process_transcription


class TestAudioPipelineStages:
    """Unit tests for AudioPipeline pre-processing stages (no ONNX model needed)."""

    def test_dead_silence_returns_none(self):
        """Pipeline.process short-circuits on all-zero audio."""
        pipeline = AudioPipeline(sample_rate=16000)
        audio = np.zeros(16000, dtype=np.int16)
        result = pipeline.process(audio)
        assert result is None

    def test_empty_audio_returns_none(self):
        pipeline = AudioPipeline(sample_rate=16000)
        audio = np.array([], dtype=np.int16)
        result = pipeline.process(audio)
        assert result is None

    def test_rms_normalize_scales_quiet_audio(self):
        pipeline = AudioPipeline(sample_rate=16000)
        quiet = np.full(1000, 10, dtype=np.float32) / 32768.0  # very quiet
        normalised = pipeline._rms_normalize(quiet)
        new_rms = float(np.sqrt(np.mean(normalised**2)))
        assert new_rms > float(np.sqrt(np.mean(quiet**2)))

    def test_rms_normalize_clamps_gain(self):
        """Gain is clamped to 10× — near-silent audio doesn't explode."""
        pipeline = AudioPipeline(sample_rate=16000)
        near_zero = np.full(1000, 1e-6, dtype=np.float32)
        normalised = pipeline._rms_normalize(near_zero)
        assert np.all(np.abs(normalised) <= 1.0)

    def test_highpass_removes_dc_offset(self):
        pipeline = AudioPipeline(sample_rate=16000)
        # DC offset + a 440Hz tone
        t = np.linspace(0, 1.0, 16000, endpoint=False, dtype=np.float32)
        signal = 0.3 + 0.1 * np.sin(2 * np.pi * 440 * t)
        filtered = pipeline._highpass(signal.astype(np.float32))
        # DC component should be attenuated significantly
        assert abs(float(np.mean(filtered[1000:]))) < 0.05

    def test_noise_gate_zeros_quiet_frames(self):
        pipeline = AudioPipeline(sample_rate=16000)
        # One chunk of silence, one chunk of speech-level signal
        chunk = AudioPipeline._CHUNK_SIZE
        silence = np.full(chunk, 1e-5, dtype=np.float32)
        speech = np.full(chunk, 0.1, dtype=np.float32)
        audio = np.concatenate([silence, speech])
        gated = pipeline._noise_gate(audio)
        # First chunk should be zeroed, second should survive
        assert float(np.max(np.abs(gated[:chunk]))) == 0.0
        assert float(np.max(np.abs(gated[chunk:]))) > 0.0


class TestPostProcessTranscription:
    """Tests for post_process_transcription()."""

    # --- Null / empty input ---

    def test_none_returns_empty(self, fresh_settings):
        assert post_process_transcription(None, get_settings()) == ""

    def test_empty_string_returns_empty(self, fresh_settings):
        assert post_process_transcription("", get_settings()) == ""

    # --- Sentence spacing (BUG-012) ---

    def test_missing_space_after_period(self, fresh_settings):
        result = post_process_transcription("Hello world.This is a test", get_settings())
        assert "world. This" in result

    def test_missing_space_after_exclamation(self, fresh_settings):
        result = post_process_transcription("Great!Now let's go", get_settings())
        assert "Great! Now" in result

    def test_missing_space_after_question(self, fresh_settings):
        result = post_process_transcription("Really?Yes indeed", get_settings())
        assert "Really? Yes" in result

    def test_ellipsis_gets_space(self, fresh_settings):
        result = post_process_transcription("Wait...Something happened", get_settings())
        assert "... Something" in result

    def test_existing_space_not_doubled(self, fresh_settings):
        result = post_process_transcription("Hello. World", get_settings())
        assert "Hello. World" in result
        assert "Hello.  World" not in result

    def test_decimal_numbers_unaffected(self, fresh_settings):
        result = post_process_transcription("The value is 3.14 exactly", get_settings())
        assert "3.14" in result

    # --- Comma / semicolon / colon spacing ---

    def test_missing_space_after_comma(self, fresh_settings):
        result = post_process_transcription("Hello,world", get_settings())
        assert "Hello, world" in result

    def test_comma_in_number_unaffected(self, fresh_settings):
        result = post_process_transcription("The count is 1,000 exactly", get_settings())
        assert "1,000" in result

    def test_missing_space_after_semicolon(self, fresh_settings):
        result = post_process_transcription("Done;now move on", get_settings())
        assert "Done; now" in result

    def test_missing_space_after_colon(self, fresh_settings):
        result = post_process_transcription("Note:this is important", get_settings())
        assert "Note: this" in result

    def test_existing_comma_space_not_doubled(self, fresh_settings):
        result = post_process_transcription("Hello, world", get_settings())
        assert "Hello, world" in result
        assert "Hello,  world" not in result

    # --- Trailing space ---

    def test_trailing_space_added_by_default(self, fresh_settings):
        result = post_process_transcription("Hello world", get_settings())
        assert result.endswith(" ")

    def test_trailing_space_disabled(self, tmp_path):
        from src.core.settings import init_settings, reset_for_tests

        reset_for_tests()
        config_file = tmp_path / "config" / "settings.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text('{"output": {"add_trailing_space": false}}')
        init_settings(config_path=config_file)

        result = post_process_transcription("Hello world", get_settings())
        assert not result.endswith(" ")
        reset_for_tests()

    # --- Whitespace normalisation ---

    def test_leading_trailing_whitespace_stripped(self, tmp_path):
        from src.core.settings import init_settings, reset_for_tests

        reset_for_tests()
        config_file = tmp_path / "config" / "settings.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text('{"output": {"add_trailing_space": false}}')
        init_settings(config_path=config_file)

        result = post_process_transcription("  Hello world  ", get_settings())
        assert result == "Hello world"
        reset_for_tests()

    # --- Segment boundary merge ---

    def test_segment_boundary_inserts_missing_space(self, fresh_settings):
        merged = _merge_segment_texts(["hello", "world"])
        assert merged == "hello world"

    def test_segment_boundary_preserves_existing_space(self, fresh_settings):
        merged = _merge_segment_texts(["hello", " world"])
        assert merged == "hello world"

    def test_segment_boundary_inserts_space_after_sentence_punctuation(self, fresh_settings):
        merged = _merge_segment_texts(["hello.", "world"])
        assert merged == "hello. world"

    # --- Deterministic punctuation/casing ---

    def test_punctuation_spacing_is_restored_deterministically(self, fresh_settings):
        result = post_process_transcription("hello ,world!how are you ?i am fine", get_settings())
        assert result == "Hello, world! How are you? I am fine "

    def test_sentence_start_casing_is_normalized(self, fresh_settings):
        result = post_process_transcription("hello world. this is a test! do you copy? yes", get_settings())
        assert result == "Hello world. This is a test! Do you copy? Yes "

    def test_mixed_edge_case_boundary_punctuation_and_casing(self, fresh_settings):
        merged = _merge_segment_texts(["hello", "world.this", "is", "a test!are", "you", "ready?yes"])
        result = post_process_transcription(merged, get_settings())
        assert result == "Hello world. This is a test! Are you ready? Yes "

    def test_post_process_is_stable_across_repeated_runs(self, fresh_settings):
        raw = "hello ,world!how are you ?i am fine"
        once = post_process_transcription(raw, get_settings())
        twice = post_process_transcription(once, get_settings())
        assert once == twice
