"""
RecordingSession pipeline tests.

Tests _recording_loop and _transcribe_and_store — the core
audio→transcribe→store→emit pipeline. Called directly (no threads)
with mocked AudioService, ASR model, and AudioPipeline.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.core.handlers.recording_handlers import RecordingSession


@pytest.fixture()
def emit():
    return MagicMock()


@pytest.fixture()
def fake_db():
    db = MagicMock()
    db.add_transcript.return_value = MagicMock(id=42)
    return db


@pytest.fixture()
def fake_audio_service():
    svc = MagicMock()
    # Default: returns 1 second of 16kHz silence
    svc.record_audio.return_value = np.zeros(16000, dtype=np.float32)
    return svc


@pytest.fixture()
def session(emit, fake_db, fake_audio_service, fresh_settings):
    """RecordingSession with all providers wired to test fakes."""
    s = RecordingSession(
        audio_service_provider=lambda: fake_audio_service,
        settings_provider=lambda: fresh_settings,
        db_provider=lambda: fake_db,
        event_bus_emit=emit,
        shutdown_event=threading.Event(),
        insight_manager_provider=lambda: None,
        motd_manager_provider=lambda: None,
        title_generator_provider=lambda: None,
    )
    return s


# ── _recording_loop ───────────────────────────────────────────────────────


class TestRecordingLoop:
    """_recording_loop orchestrates record → stop → transcribe → store."""

    @patch("src.core.handlers.recording_handlers.RecordingSession._transcribe_and_store")
    def test_happy_path(self, mock_ts, session, emit, fake_audio_service):
        """Record audio → emit recording_stopped → call _transcribe_and_store."""
        session._is_recording = True

        session._recording_loop()

        fake_audio_service.record_audio.assert_called_once()
        # Should have emitted recording_stopped with cancelled=False
        emit.assert_any_call("recording_stopped", {"cancelled": False})
        # Should have called _transcribe_and_store with the audio data
        mock_ts.assert_called_once()
        assert session._is_recording is False

    def test_cancelled_during_recording(self, session, emit, fake_audio_service):
        """If _is_recording goes False during record, loop returns early."""
        session._is_recording = False  # simulate cancel

        session._recording_loop()

        # record_audio was called, but since _is_recording is False,
        # no events should be emitted
        emit.assert_not_called()

    @patch("src.core.handlers.recording_handlers.RecordingSession._transcribe_and_store")
    def test_empty_audio_emits_error(self, mock_ts, session, emit, fake_audio_service):
        """Empty/None audio → transcription_error, no transcribe call."""
        session._is_recording = True
        fake_audio_service.record_audio.return_value = np.array([], dtype=np.float32)

        session._recording_loop()

        emit.assert_any_call("recording_stopped", {"cancelled": False})
        emit.assert_any_call("transcription_error", {"message": "Recording too short or empty"})
        mock_ts.assert_not_called()

    @patch("src.core.handlers.recording_handlers.RecordingSession._transcribe_and_store")
    def test_none_audio_emits_error(self, mock_ts, session, emit, fake_audio_service):
        """None audio → transcription_error."""
        session._is_recording = True
        fake_audio_service.record_audio.return_value = None

        session._recording_loop()

        emit.assert_any_call("transcription_error", {"message": "Recording too short or empty"})
        mock_ts.assert_not_called()

    def test_exception_emits_error(self, session, emit, fake_audio_service):
        """Exception in record_audio → recording_stopped + transcription_error."""
        session._is_recording = True
        fake_audio_service.record_audio.side_effect = RuntimeError("Mic exploded")

        session._recording_loop()

        emit.assert_any_call("recording_stopped", {"cancelled": False})
        emit.assert_any_call("transcription_error", {"message": "Mic exploded"})
        assert session._is_recording is False


# ── _transcribe_and_store ─────────────────────────────────────────────────


class TestTranscribeAndStore:
    """_transcribe_and_store runs ASR → DB → events."""

    @patch("src.core.handlers.recording_handlers._copy_to_system_clipboard")
    @patch("src.services.audio_pipeline.AudioPipeline")
    @patch("src.services.transcription_service.transcribe")
    @patch("src.services.transcription_service.create_local_model")
    def test_happy_path(
        self, mock_create, mock_transcribe, mock_pipeline, mock_clip, session, emit, fake_db, fresh_settings
    ):
        """Full pipeline: ASR → store → emit transcription_complete."""
        mock_transcribe.return_value = ("Hello world", 850, 120)
        session._asr_model = MagicMock()
        session._audio_pipeline = MagicMock()

        audio = np.zeros(16000, dtype=np.float32)
        session._transcribe_and_store(audio)

        mock_transcribe.assert_called_once()
        fake_db.add_transcript.assert_called_once()
        # Verify transcription_complete event
        complete_calls = [c for c in emit.call_args_list if c[0][0] == "transcription_complete"]
        assert len(complete_calls) == 1
        payload = complete_calls[0][0][1]
        assert payload["text"] == "Hello world"
        assert payload["id"] == 42
        assert payload["speech_duration_ms"] == 850

    @patch("src.services.audio_pipeline.AudioPipeline")
    @patch("src.services.transcription_service.transcribe")
    def test_no_speech_detected(self, mock_transcribe, mock_pipeline, session, emit, fake_db):
        """Empty transcription text → transcription_error, no DB write."""
        mock_transcribe.return_value = ("   ", 0, 0)
        session._asr_model = MagicMock()
        session._audio_pipeline = MagicMock()

        session._transcribe_and_store(np.zeros(16000, dtype=np.float32))

        emit.assert_any_call("transcription_error", {"message": "No speech detected"})
        fake_db.add_transcript.assert_not_called()

    def test_shutdown_skips_transcription(self, session, emit, fake_db):
        """If shutdown_event is set, skip everything."""
        session._shutdown_event.set()

        session._transcribe_and_store(np.zeros(16000, dtype=np.float32))

        emit.assert_not_called()
        fake_db.add_transcript.assert_not_called()

    @patch("src.services.transcription_service.create_local_model")
    def test_lazy_load_failure(self, mock_create, session, emit, fake_db):
        """ASR model is None and lazy load fails → error events."""
        session._asr_model = None
        mock_create.side_effect = RuntimeError("CUDA OOM")

        session._transcribe_and_store(np.zeros(16000, dtype=np.float32))

        emit.assert_any_call("engine_status", {"asr": "unavailable"})
        error_calls = [c for c in emit.call_args_list if c[0][0] == "transcription_error"]
        assert len(error_calls) == 1
        assert "failed to load" in error_calls[0][0][1]["message"].lower()
        fake_db.add_transcript.assert_not_called()

    @patch("src.services.audio_pipeline.AudioPipeline")
    @patch("src.services.transcription_service.transcribe")
    def test_transcription_exception(self, mock_transcribe, mock_pipeline, session, emit, fake_db):
        """Exception during transcribe() → transcription_error event."""
        mock_transcribe.side_effect = RuntimeError("Whisper crashed")
        session._asr_model = MagicMock()
        session._audio_pipeline = MagicMock()

        session._transcribe_and_store(np.zeros(16000, dtype=np.float32))

        error_calls = [c for c in emit.call_args_list if c[0][0] == "transcription_error"]
        assert len(error_calls) == 1
        assert "Whisper crashed" in error_calls[0][0][1]["message"]

    @patch("src.core.handlers.recording_handlers._copy_to_system_clipboard")
    @patch("src.services.audio_pipeline.AudioPipeline")
    @patch("src.services.transcription_service.transcribe")
    def test_auto_copy_disabled(
        self, mock_transcribe, mock_pipeline, mock_clip, session, emit, fake_db, fresh_settings
    ):
        """auto_copy_to_clipboard=False → clipboard not called."""
        mock_transcribe.return_value = ("text", 500, 100)
        new_output = fresh_settings.output.model_copy(update={"auto_copy_to_clipboard": False})
        new_settings = fresh_settings.model_copy(update={"output": new_output})
        session._settings_provider = lambda: new_settings
        session._asr_model = MagicMock()
        session._audio_pipeline = MagicMock()

        session._transcribe_and_store(np.zeros(16000, dtype=np.float32))

        mock_clip.assert_not_called()

    @patch("src.core.handlers.recording_handlers._copy_to_system_clipboard")
    @patch("src.services.audio_pipeline.AudioPipeline")
    @patch("src.services.transcription_service.transcribe")
    def test_auto_copy_enabled(self, mock_transcribe, mock_pipeline, mock_clip, session, emit, fake_db, fresh_settings):
        """auto_copy_to_clipboard=True → clipboard called with text."""
        mock_transcribe.return_value = ("Copied text", 500, 100)
        # Default is True, but let's be explicit
        new_output = fresh_settings.output.model_copy(update={"auto_copy_to_clipboard": True})
        new_settings = fresh_settings.model_copy(update={"output": new_output})
        session._settings_provider = lambda: new_settings
        session._asr_model = MagicMock()
        session._audio_pipeline = MagicMock()

        session._transcribe_and_store(np.zeros(16000, dtype=np.float32))

        mock_clip.assert_called_once_with("Copied text")

    @patch("src.services.audio_pipeline.AudioPipeline")
    @patch("src.services.transcription_service.transcribe")
    def test_insight_manager_scheduled(self, mock_transcribe, mock_pipeline, session, emit, fake_db):
        """Non-None insight_manager gets maybe_schedule() called."""
        mock_transcribe.return_value = ("text", 500, 100)
        session._asr_model = MagicMock()
        session._audio_pipeline = MagicMock()
        mock_insight = MagicMock()
        session._insight_manager_provider = lambda: mock_insight

        session._transcribe_and_store(np.zeros(16000, dtype=np.float32))

        mock_insight.maybe_schedule.assert_called_once()

    @patch("src.services.audio_pipeline.AudioPipeline")
    @patch("src.services.transcription_service.transcribe")
    def test_title_generator_scheduled(self, mock_transcribe, mock_pipeline, session, emit, fake_db):
        """Non-None title_generator gets schedule() called with transcript id and text."""
        mock_transcribe.return_value = ("some text", 500, 100)
        session._asr_model = MagicMock()
        session._audio_pipeline = MagicMock()
        mock_title_gen = MagicMock()
        session._title_generator_provider = lambda: mock_title_gen

        session._transcribe_and_store(np.zeros(16000, dtype=np.float32))

        mock_title_gen.schedule.assert_called_once_with(42, "some text")

    @patch("src.services.audio_pipeline.AudioPipeline")
    @patch("src.services.transcription_service.transcribe")
    def test_no_db_still_emits_complete(self, mock_transcribe, mock_pipeline, session, emit):
        """If db_provider returns None, still emit transcription_complete with id=None."""
        mock_transcribe.return_value = ("hello", 500, 100)
        session._asr_model = MagicMock()
        session._audio_pipeline = MagicMock()
        session._db_provider = lambda: None

        session._transcribe_and_store(np.zeros(16000, dtype=np.float32))

        complete_calls = [c for c in emit.call_args_list if c[0][0] == "transcription_complete"]
        assert len(complete_calls) == 1
        assert complete_calls[0][0][1]["id"] is None

    @patch("src.services.audio_pipeline.AudioPipeline")
    @patch("src.services.transcription_service.transcribe")
    @patch("src.services.transcription_service.create_local_model")
    def test_lazy_asr_load_success(self, mock_create, mock_transcribe, mock_pipeline, session, emit, fake_db):
        """ASR model is None → lazy load succeeds → transcription proceeds."""
        mock_model = MagicMock()
        mock_create.return_value = mock_model
        mock_transcribe.return_value = ("recovered text", 500, 100)
        session._asr_model = None
        session._audio_pipeline = MagicMock()

        session._transcribe_and_store(np.zeros(16000, dtype=np.float32))

        assert session._asr_model is mock_model
        complete_calls = [c for c in emit.call_args_list if c[0][0] == "transcription_complete"]
        assert len(complete_calls) == 1
        assert complete_calls[0][0][1]["text"] == "recovered text"


# ── handle_begin guard checks ────────────────────────────────────────────


class TestHandleBeginGuards:
    """handle_begin pre-checks before entering _recording_loop."""

    def test_begin_while_recording_is_noop(self, session, emit):
        session._is_recording = True
        session.handle_begin(MagicMock())
        # No recording_started event
        assert all(c[0][0] != "recording_started" for c in emit.call_args_list)

    def test_begin_without_audio_service_is_noop(self, emit, fake_db, fresh_settings):
        """No audio service → no recording started."""
        s = RecordingSession(
            audio_service_provider=lambda: None,
            settings_provider=lambda: fresh_settings,
            db_provider=lambda: fake_db,
            event_bus_emit=emit,
            shutdown_event=threading.Event(),
            insight_manager_provider=lambda: None,
            motd_manager_provider=lambda: None,
        )
        s.handle_begin(MagicMock())
        assert s._is_recording is False
        emit.assert_not_called()

    @patch("src.core.resource_manager.ResourceManager.get_user_cache_dir")
    @patch("src.core.handlers.recording_handlers.RecordingSession._recording_loop")
    def test_begin_missing_model_file_emits_error(self, mock_loop, mock_cache_dir, session, emit, tmp_path):
        """Model directory not on disk → transcription_error, no recording."""
        mock_cache_dir.return_value = tmp_path  # empty dir, no CT2 model directories

        session.handle_begin(MagicMock())

        error_calls = [c for c in emit.call_args_list if c[0][0] == "transcription_error"]
        assert len(error_calls) == 1
        assert (
            "download" in error_calls[0][0][1]["message"].lower() or "model" in error_calls[0][0][1]["message"].lower()
        )
        assert session._is_recording is False
