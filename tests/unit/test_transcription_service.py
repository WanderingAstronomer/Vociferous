"""Tests for transcription service post-processing."""

import pytest

from src.core.settings import get_settings
from src.services.transcription_service import post_process_transcription


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
