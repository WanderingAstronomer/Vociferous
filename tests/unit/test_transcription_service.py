"""Tests for transcription service post-processing."""

import numpy as np
import pytest

from src.core.settings import get_settings
from src.services.transcription_service import _is_effective_silence, _merge_segment_texts, post_process_transcription


class TestSilenceDetection:
    """Regression tests for raw silence detection guard."""

    def test_detects_all_zero_audio_as_silence(self):
        audio = np.zeros(16000, dtype=np.int16)
        assert _is_effective_silence(audio) is True

    def test_detects_tone_audio_as_non_silence(self):
        sample_rate = 16000
        t = np.linspace(0, 1.0, sample_rate, endpoint=False)
        # 440Hz tone, intentionally strong enough to pass both gates.
        tone = (0.15 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
        assert _is_effective_silence(tone) is False


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
