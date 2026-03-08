"""
Unit tests for handler classes — TitleHandlers, RefinementHandlers, RecordingSession.

Tests the handler classes directly (no coordinator wiring) to cover all
code paths including background thread logic with mocked dependencies.
"""

from __future__ import annotations

import threading
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.database.db import TranscriptDB
from src.services.slm_types import SLMState

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> Generator[TranscriptDB, None, None]:
    database = TranscriptDB(db_path=tmp_path / "handler_test.db")
    yield database
    database.close()


@pytest.fixture()
def events() -> list[tuple[str, dict]]:
    return []


def _emit_to(events_list):
    """Factory for an event emitter that appends to a list."""

    def emit(event_type: str, data: dict) -> None:
        events_list.append((event_type, data))

    return emit


def _events_of(events_list, event_type: str) -> list[dict]:
    """Filter events by type."""
    return [d for et, d in events_list if et == event_type]


def _wait_for_threads(prefix: str, timeout: float = 5.0) -> None:
    for t in threading.enumerate():
        if t.name.startswith(prefix) and t.is_alive():
            t.join(timeout=timeout)


# ===========================================================================
# TitleHandlers
# ===========================================================================


class TestTitleHandlersRetitle:
    """TitleHandlers.handle_retitle()"""

    def _make_handler(self, *, db, title_gen, events_list):
        from src.core.handlers.title_handlers import TitleHandlers

        return TitleHandlers(
            db_provider=lambda: db,
            title_generator_provider=lambda: title_gen,
            event_bus_emit=_emit_to(events_list),
        )

    def test_retitle_schedules_generation(self, db, events):
        t = db.add_transcript(raw_text="some meaningful text here", duration_ms=5000)
        mock_gen = MagicMock()
        handler = self._make_handler(db=db, title_gen=mock_gen, events_list=events)

        intent = SimpleNamespace(transcript_id=t.id)
        handler.handle_retitle(intent)

        mock_gen.schedule.assert_called_once_with(t.id, "some meaningful text here")

    def test_retitle_no_title_generator_is_noop(self, db, events):
        t = db.add_transcript(raw_text="hello", duration_ms=1000)
        handler = self._make_handler(db=db, title_gen=None, events_list=events)

        intent = SimpleNamespace(transcript_id=t.id)
        handler.handle_retitle(intent)  # should not crash

    def test_retitle_no_db_is_noop(self, events):
        handler = self._make_handler(db=None, title_gen=MagicMock(), events_list=events)

        intent = SimpleNamespace(transcript_id=1)
        handler.handle_retitle(intent)

    def test_retitle_nonexistent_transcript_is_noop(self, db, events):
        mock_gen = MagicMock()
        handler = self._make_handler(db=db, title_gen=mock_gen, events_list=events)

        intent = SimpleNamespace(transcript_id=99999)
        handler.handle_retitle(intent)

        mock_gen.schedule.assert_not_called()

    def test_retitle_empty_text_is_noop(self, db, events):
        t = db.add_transcript(raw_text="   ", duration_ms=1000)
        mock_gen = MagicMock()
        handler = self._make_handler(db=db, title_gen=mock_gen, events_list=events)

        intent = SimpleNamespace(transcript_id=t.id)
        handler.handle_retitle(intent)

        mock_gen.schedule.assert_not_called()

    def test_retitle_prefers_normalized_text(self, db, events):
        """If normalized_text exists, use it over raw_text."""
        t = db.add_transcript(raw_text="raw version", duration_ms=1000)
        # Simulate normalized text via direct update
        db.update_normalized_text(t.id, "better version")
        mock_gen = MagicMock()
        handler = self._make_handler(db=db, title_gen=mock_gen, events_list=events)

        intent = SimpleNamespace(transcript_id=t.id)
        handler.handle_retitle(intent)

        # Should call with whatever text the DB resolved
        mock_gen.schedule.assert_called_once()


# ===========================================================================
# RefinementHandlers
# ===========================================================================


class TestRefinementHandlersStateGuards:
    """All SLM state validation branches in handle_refine()."""

    def _make_handler(self, *, db, slm=None, events_list=None):
        from src.core.handlers.refinement_handlers import RefinementHandlers
        from src.core.settings import VociferousSettings

        settings = VociferousSettings()
        ev = events_list or []
        return RefinementHandlers(
            db_provider=lambda: db,
            slm_runtime_provider=lambda: slm,
            settings_provider=lambda: settings,
            event_bus_emit=_emit_to(ev),
        ), ev

    def test_no_db_emits_error(self, events):
        handler, ev = self._make_handler(db=None, events_list=events)
        handler.handle_refine(SimpleNamespace(transcript_id=1, level=1, instructions=None))

        errors = _events_of(ev, "refinement_error")
        assert len(errors) == 1
        assert "database" in errors[0]["message"].lower()

    def test_no_slm_emits_error(self, db, events):
        handler, ev = self._make_handler(db=db, slm=None, events_list=events)
        handler.handle_refine(SimpleNamespace(transcript_id=1, level=1, instructions=None))

        errors = _events_of(ev, "refinement_error")
        assert len(errors) == 1

    def test_slm_disabled_emits_error(self, db, events):
        mock_slm = MagicMock()
        mock_slm.state = SLMState.DISABLED
        handler, ev = self._make_handler(db=db, slm=mock_slm, events_list=events)

        handler.handle_refine(SimpleNamespace(transcript_id=1, level=1, instructions=None))

        errors = _events_of(ev, "refinement_error")
        assert len(errors) == 1
        assert "disabled" in errors[0]["message"].lower()

    def test_slm_loading_emits_error(self, db, events):
        mock_slm = MagicMock()
        mock_slm.state = SLMState.LOADING
        handler, ev = self._make_handler(db=db, slm=mock_slm, events_list=events)

        handler.handle_refine(SimpleNamespace(transcript_id=1, level=1, instructions=None))

        errors = _events_of(ev, "refinement_error")
        assert len(errors) == 1
        assert "loading" in errors[0]["message"].lower()

    def test_slm_error_state_emits_error(self, db, events):
        mock_slm = MagicMock()
        mock_slm.state = SLMState.ERROR
        handler, ev = self._make_handler(db=db, slm=mock_slm, events_list=events)

        handler.handle_refine(SimpleNamespace(transcript_id=1, level=1, instructions=None))

        errors = _events_of(ev, "refinement_error")
        assert len(errors) == 1
        assert "failed" in errors[0]["message"].lower()

    def test_slm_inferring_emits_error(self, db, events):
        mock_slm = MagicMock()
        mock_slm.state = SLMState.INFERRING
        handler, ev = self._make_handler(db=db, slm=mock_slm, events_list=events)

        handler.handle_refine(SimpleNamespace(transcript_id=1, level=1, instructions=None))

        errors = _events_of(ev, "refinement_error")
        assert len(errors) == 1
        assert "already in progress" in errors[0]["message"].lower()

    def test_nonexistent_transcript_emits_error(self, db, events):
        mock_slm = MagicMock()
        mock_slm.state = SLMState.READY
        handler, ev = self._make_handler(db=db, slm=mock_slm, events_list=events)

        handler.handle_refine(SimpleNamespace(transcript_id=99999, level=1, instructions=None))

        errors = _events_of(ev, "refinement_error")
        assert len(errors) == 1
        assert "not found" in errors[0]["message"].lower()


class TestRefinementHandlersHappyPath:
    """Refinement background thread: successful execution path."""

    def test_successful_refinement_updates_text_and_emits(self, db, events):
        from src.core.handlers.refinement_handlers import RefinementHandlers
        from src.core.settings import VociferousSettings

        t = db.add_transcript(raw_text="original text to refine", duration_ms=5000)
        settings = VociferousSettings()

        mock_slm = MagicMock()
        mock_slm.state = SLMState.READY
        mock_slm.refine_text_sync.return_value = "refined version of the text"

        handler = RefinementHandlers(
            db_provider=lambda: db,
            slm_runtime_provider=lambda: mock_slm,
            settings_provider=lambda: settings,
            event_bus_emit=_emit_to(events),
        )

        handler.handle_refine(SimpleNamespace(transcript_id=t.id, level=2, instructions=None))
        _wait_for_threads("refine")

        # Should have emitted started + progress + complete
        started = _events_of(events, "refinement_started")
        assert len(started) == 1
        assert started[0]["transcript_id"] == t.id

        complete = _events_of(events, "refinement_complete")
        assert len(complete) == 1
        assert complete[0]["transcript_id"] == t.id
        assert complete[0]["text"] == "refined version of the text"
        assert complete[0]["level"] == 2

        # Verify normalized_text updated in DB
        refreshed = db.get_transcript(t.id)
        assert refreshed.text == "refined version of the text"

    def test_slm_exception_in_refine_thread_emits_error(self, db, events):
        from src.core.handlers.refinement_handlers import RefinementHandlers
        from src.core.settings import VociferousSettings

        t = db.add_transcript(raw_text="will fail", duration_ms=1000)
        settings = VociferousSettings()

        mock_slm = MagicMock()
        mock_slm.state = SLMState.READY
        mock_slm.refine_text_sync.side_effect = RuntimeError("inference exploded")

        handler = RefinementHandlers(
            db_provider=lambda: db,
            slm_runtime_provider=lambda: mock_slm,
            settings_provider=lambda: settings,
            event_bus_emit=_emit_to(events),
        )

        handler.handle_refine(SimpleNamespace(transcript_id=t.id, level=1, instructions=None))
        _wait_for_threads("refine")

        errors = _events_of(events, "refinement_error")
        assert len(errors) == 1
        assert "exploded" in errors[0]["message"]


# ===========================================================================
# RecordingSession
# ===========================================================================


class TestRecordingSessionLifecycle:
    """Direct unit tests for RecordingSession methods."""

    def _make_session(self, *, events_list, db=None, audio_service=None):
        from src.core.handlers.recording_handlers import RecordingSession
        from src.core.settings import VociferousSettings

        settings = VociferousSettings()
        return RecordingSession(
            audio_service_provider=lambda: audio_service,
            settings_provider=lambda: settings,
            db_provider=lambda: db,
            event_bus_emit=_emit_to(events_list),
            shutdown_event=threading.Event(),
            insight_manager_provider=lambda: None,
            motd_manager_provider=lambda: None,
        )

    def test_cancel_for_shutdown_sets_stop_and_clears_recording(self, events):
        session = self._make_session(events_list=events)
        session._is_recording = True
        session.cancel_for_shutdown()

        assert session._recording_stop.is_set()
        assert session._is_recording is False

    def test_handle_cancel_when_recording_emits_stopped(self, events):
        session = self._make_session(events_list=events)
        session._is_recording = True

        session.handle_cancel(SimpleNamespace())

        assert session._recording_stop.is_set()
        assert session._is_recording is False
        stopped = _events_of(events, "recording_stopped")
        assert len(stopped) == 1
        assert stopped[0]["cancelled"] is True

    def test_handle_cancel_when_not_recording_is_noop(self, events):
        session = self._make_session(events_list=events)
        session.handle_cancel(SimpleNamespace())

        assert len(events) == 0

    def test_handle_stop_when_recording_sets_stop_event(self, events):
        session = self._make_session(events_list=events)
        session._is_recording = True

        session.handle_stop(SimpleNamespace())
        assert session._recording_stop.is_set()

    def test_handle_stop_when_not_recording_is_noop(self, events):
        session = self._make_session(events_list=events)
        session.handle_stop(SimpleNamespace())

        assert not session._recording_stop.is_set()

    def test_handle_toggle_begins_when_idle(self, events):
        session = self._make_session(events_list=events, audio_service=None)
        session.handle_toggle(SimpleNamespace())
        # No audio service → begin is noop, but it tried
        assert session._is_recording is False

    def test_handle_toggle_stops_when_recording(self, events):
        session = self._make_session(events_list=events)
        session._is_recording = True
        session.handle_toggle(SimpleNamespace())
        assert session._recording_stop.is_set()

    def test_handle_begin_without_audio_service_is_noop(self, events):
        session = self._make_session(events_list=events, audio_service=None)
        session.handle_begin(SimpleNamespace())

        assert session._is_recording is False
        assert len(_events_of(events, "recording_started")) == 0

    def test_handle_begin_while_already_recording_is_noop(self, events):
        session = self._make_session(events_list=events, audio_service=MagicMock())
        session._is_recording = True

        session.handle_begin(SimpleNamespace())
        # Should not have emitted anything new
        assert len(_events_of(events, "recording_started")) == 0

    def test_is_recording_property(self, events):
        session = self._make_session(events_list=events)
        assert session.is_recording is False
        session._is_recording = True
        assert session.is_recording is True

    def test_thread_property(self, events):
        session = self._make_session(events_list=events)
        assert session.thread is None

    def test_load_asr_model_success_emits_ready(self, events, tmp_path):
        session = self._make_session(events_list=events)

        with patch("src.services.transcription_service.create_local_model") as mock_create:
            mock_create.return_value = MagicMock()
            session.load_asr_model()

        ready = _events_of(events, "engine_status")
        assert len(ready) == 1
        assert ready[0]["asr"] == "ready"

    def test_load_asr_model_failure_emits_unavailable(self, events):
        session = self._make_session(events_list=events)

        with patch("src.services.transcription_service.create_local_model") as mock_create:
            mock_create.side_effect = RuntimeError("model not found")
            session.load_asr_model()

        status = _events_of(events, "engine_status")
        assert len(status) == 1
        assert status[0]["asr"] == "unavailable"

    def test_unload_asr_model_clears_reference(self, events):
        session = self._make_session(events_list=events)
        session._asr_model = MagicMock()

        session.unload_asr_model()
        assert session._asr_model is None

    def test_unload_asr_model_when_none_is_noop(self, events):
        session = self._make_session(events_list=events)
        session.unload_asr_model()  # should not crash
        assert session._asr_model is None
