"""
Tests for transcription module.
"""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch


class TestTranscriptionFunctions:
    """Tests for transcription utilities (not model loading)."""

    def test_post_process_adds_trailing_space(self, config_manager):
        """Post-processing should add trailing space when configured."""
        from src.services.transcription_service import post_process_transcription

        # Preserve original value
        original_value = config_manager.get_config_value(
            "output_options", "add_trailing_space"
        )

        try:
            # Ensure trailing space is enabled
            config_manager.set_config_value(
                True, "output_options", "add_trailing_space"
            )
            result = post_process_transcription("hello world")
            assert result.endswith(" ")
        finally:
            # Restore original value
            config_manager.set_config_value(
                original_value, "output_options", "add_trailing_space"
            )

    def test_post_process_strips_whitespace(self):
        """Post-processing should strip leading/trailing whitespace."""
        from src.services.transcription_service import post_process_transcription

        result = post_process_transcription("  hello world  ")
        assert result.startswith("hello")  # Leading space removed

    def test_post_process_empty_string(self):
        """Post-processing should handle empty strings."""
        from src.services.transcription_service import post_process_transcription

        result = post_process_transcription("")
        assert result == ""

    def test_post_process_none_returns_empty(self):
        """Post-processing should handle None-like input."""
        from src.services.transcription_service import post_process_transcription

        result = post_process_transcription(None)
        assert result == ""


class TestTranscribeFunction:
    """Tests for the transcribe function."""

    def test_transcribe_none_returns_empty_tuple(self):
        """Transcribing None should return empty string and zero duration."""
        from src.services.transcription_service import transcribe

        result = transcribe(None, MagicMock())
        assert result == ("", 0)

    @patch("src.services.transcription_service.create_local_model")
    def test_transcribe_silent_audio(self, mock_create_model):
        """Transcribing silence should return empty or minimal text."""
        from src.services.transcription_service import transcribe

        # Mock the model to return empty text for silence
        mock_model = MagicMock()
        # Mock transcribe result: segments iterator (empty or one segment with empty text)
        mock_segment = MagicMock()
        mock_segment.text = ""
        mock_model.transcribe.return_value = ([mock_segment], MagicMock())
        mock_create_model.return_value = mock_model

        # Create 1 second of silence (int16)
        sample_rate = 16000
        silence = np.zeros(sample_rate, dtype=np.int16)

        text, duration_ms = transcribe(silence, mock_model)

        # Silent audio should produce empty or very short result
        assert len(text.strip()) < 10


class TestModelLoading:
    """Tests for model loading."""

    @patch("faster_whisper.WhisperModel")
    def test_model_loads(self, mock_whisper_model):
        """Model should load successfully (mocked)."""
        from src.services.transcription_service import create_local_model

        model = create_local_model()
        assert model is not None
        assert mock_whisper_model.called

    @patch("faster_whisper.WhisperModel")
    def test_model_has_transcribe_method(self, mock_whisper_model):
        """Loaded model should have transcribe method."""
        from src.services.transcription_service import create_local_model

        # Ensure the mock instance has transcribe
        mock_instance = mock_whisper_model.return_value
        mock_instance.transcribe = MagicMock()

        model = create_local_model()
        assert hasattr(model, "transcribe")
        assert callable(model.transcribe)
