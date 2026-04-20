"""Tests for transcription service post-processing and transcribe()."""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.core.cuda_runtime import CudaRuntimeStatus
from src.core.exceptions import EngineError
from src.core.settings import ModelSettings, get_settings
from src.services.transcription_service import (
    _merge_segment_texts,
    create_local_model,
    post_process_transcription,
    transcribe,
)


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


# ── transcribe() kwarg verification ───────────────────────────────────────
# faster-whisper (CTranslate2 backend): initial_prompt is now SAFE.
# These tests verify the faster-whisper inference path passes the right parameters.


class TestTranscribeKwargs:
    """Verify transcribe() passes the correct kwargs to the faster-whisper model."""

    @staticmethod
    def _make_fake_model(text: str = "Hello world.") -> MagicMock:
        """Return a mock faster-whisper WhisperModel that yields one segment."""
        seg = MagicMock()
        seg.text = text
        seg.start = 0.0
        seg.end = 1.0
        info = MagicMock()
        model = MagicMock()
        model.transcribe.return_value = (iter([seg]), info)
        return model

    @staticmethod
    def _make_fake_pipeline() -> MagicMock:
        """Return a mock AudioPipeline that passes audio through."""
        pipeline = MagicMock()
        # process() must return valid float32 audio, not None
        pipeline.process.side_effect = lambda audio, **kw: audio.astype(np.float32)
        return pipeline

    def test_initial_prompt_is_passed(self, fresh_settings):
        """initial_prompt IS now passed (faster-whisper has no SIGSEGV bug)."""
        model = self._make_fake_model()
        pipeline = self._make_fake_pipeline()
        audio = np.zeros(16000, dtype=np.int16)

        transcribe(audio, fresh_settings, local_model=model, audio_pipeline=pipeline)

        model.transcribe.assert_called_once()
        _, kwargs = model.transcribe.call_args
        assert "initial_prompt" in kwargs
        assert kwargs["initial_prompt"] is not None

    def test_language_always_passed(self, fresh_settings):
        """Language kwarg is always present in faster-whisper transcribe() call."""
        model = self._make_fake_model()
        pipeline = self._make_fake_pipeline()
        audio = np.zeros(16000, dtype=np.int16)

        transcribe(audio, fresh_settings, local_model=model, audio_pipeline=pipeline)

        _, kwargs = model.transcribe.call_args
        assert kwargs["language"] == fresh_settings.model.language

    def test_default_prompt_preserved_in_settings(self):
        """Default initial_prompt still defined in settings."""
        defaults = ModelSettings()
        prompt = defaults.initial_prompt
        assert len(prompt) > 20, "Prompt should be set for CTranslate2 quality"


class TestCreateLocalModelRuntimeResolution:
    """Verify device/compute resolution matches actual CUDA runtime availability."""

    @staticmethod
    def _settings_with(fresh_settings, *, device: str, compute_type: str):
        return fresh_settings.model_copy(
            update={
                "model": fresh_settings.model.model_copy(
                    update={
                        "device": device,
                        "compute_type": compute_type,
                    }
                )
            }
        )

    @staticmethod
    def _capture_whisper_ctor():
        captured: dict[str, object] = {}

        class DummyWhisperModel:
            def __init__(self, *args, **kwargs):
                captured["args"] = args
                captured["kwargs"] = kwargs

        return captured, DummyWhisperModel

    def test_auto_cpu_fallback_converts_float16_to_float32(self, fresh_settings):
        settings = self._settings_with(fresh_settings, device="auto", compute_type="float16")
        captured, dummy_model = self._capture_whisper_ctor()

        with (
            patch("src.services.transcription_service._resolve_model_path", return_value=Path("/tmp/fake-model")),
            patch(
                "src.services.transcription_service.detect_cuda_runtime",
                return_value=CudaRuntimeStatus(
                    driver_detected=True,
                    cuda_available=False,
                    detail="CTranslate2 detected 0 CUDA devices; NVIDIA driver is present but the CUDA runtime is not usable",
                ),
            ),
            patch.dict(sys.modules, {"faster_whisper": types.SimpleNamespace(WhisperModel=dummy_model)}),
        ):
            create_local_model(settings)

        assert captured["kwargs"]["device"] == "cpu"
        assert captured["kwargs"]["compute_type"] == "float32"

    def test_auto_cuda_upgrades_int8_to_float16(self, fresh_settings):
        settings = self._settings_with(fresh_settings, device="auto", compute_type="int8")
        captured, dummy_model = self._capture_whisper_ctor()

        with (
            patch("src.services.transcription_service._resolve_model_path", return_value=Path("/tmp/fake-model")),
            patch(
                "src.services.transcription_service.detect_cuda_runtime",
                return_value=CudaRuntimeStatus(
                    driver_detected=True,
                    cuda_available=True,
                    cuda_device_count=1,
                    detail="CTranslate2 detected 1 CUDA device(s)",
                ),
            ),
            patch.dict(sys.modules, {"faster_whisper": types.SimpleNamespace(WhisperModel=dummy_model)}),
        ):
            create_local_model(settings)

        assert captured["kwargs"]["device"] == "cuda"
        assert captured["kwargs"]["compute_type"] == "float16"

    def test_explicit_gpu_raises_clear_error_when_cuda_unusable(self, fresh_settings):
        settings = self._settings_with(fresh_settings, device="gpu", compute_type="float16")

        with (
            patch("src.services.transcription_service._resolve_model_path", return_value=Path("/tmp/fake-model")),
            patch(
                "src.services.transcription_service.detect_cuda_runtime",
                return_value=CudaRuntimeStatus(
                    driver_detected=True,
                    cuda_available=False,
                    detail="CTranslate2 CUDA probe failed: missing cudnn64_9.dll",
                ),
            ),
            patch.dict(sys.modules, {"faster_whisper": types.SimpleNamespace(WhisperModel=object)}),
        ):
            with pytest.raises(EngineError, match="CUDA is not usable: CTranslate2 CUDA probe failed"):
                create_local_model(settings)


class TestTranscriptionTimingLogs:
    @staticmethod
    def _make_fake_model(text: str = "Hello world.") -> MagicMock:
        seg = MagicMock()
        seg.text = text
        seg.start = 0.0
        seg.end = 1.0
        info = MagicMock()
        model = MagicMock()
        model.transcribe.return_value = (iter([seg]), info)
        model._vociferous_runtime_summary = {
            "model_id": "large-v3-turbo-int8",
            "resolved_device": "cpu",
            "compute_type_resolved": "float32",
            "cpu_threads": 4,
            "language": "en",
        }
        return model

    @staticmethod
    def _make_fake_pipeline() -> MagicMock:
        pipeline = MagicMock()
        pipeline.process.side_effect = lambda audio, **kw: audio.astype(np.float32)
        return pipeline

    def test_slow_asr_run_logs_warning_context(self, fresh_settings, caplog):
        model = self._make_fake_model()
        pipeline = self._make_fake_pipeline()
        audio = np.zeros(16_000 * 8, dtype=np.int16)

        with patch("src.services.transcription_service.time.perf_counter", side_effect=[0.0, 10.0]):
            transcribe(audio, fresh_settings, local_model=model, audio_pipeline=pipeline)

        assert "Slow ASR run detected" in caplog.text
        assert "realtime=0.80x" in caplog.text
        assert "resolved_device=cpu" in caplog.text
