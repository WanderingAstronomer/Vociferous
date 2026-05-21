"""
Tests for ApplicationCoordinator intent handlers.

Validates the full intent→handler→DB→EventBus flow for every
CommandBus-registered intent, using a real database and real buses
but WITHOUT heavy services (ASR, SLM, audio, webview).
"""

from __future__ import annotations

import pytest

from tests.conftest import EventCollector

# ── Fixtures ──────────────────────────────────────────────────────────────

ALL_EVENTS = [
    "recording_started",
    "recording_stopped",
    "transcript_deleted",
    "transcripts_batch_deleted",
    "transcript_updated",
    "transcripts_cleared",
    "refinement_started",
    "refinement_complete",
    "refinement_error",
    "transcription_complete",
    "transcription_error",
    "config_updated",
    "tag_created",
    "tag_updated",
    "tag_deleted",
]


@pytest.fixture()
def wired(coordinator, event_collector):
    """Coordinator with EventCollector subscribed to all domain events."""
    event_collector.subscribe_all(coordinator.event_bus, ALL_EVENTS)
    return coordinator, event_collector


# ── CommitEditsIntent ─────────────────────────────────────────────────────


class TestCommitEdits:
    """Commit edits via CommandBus → normalized_text updated in DB."""

    def test_commit_updates_normalized_text(self, wired):
        coord, events = wired
        t = coord.db.add_transcript(raw_text="original text", duration_ms=500)

        from src.core.intents.definitions import CommitEditsIntent

        result = coord.command_bus.dispatch(CommitEditsIntent(transcript_id=t.id, content="edited text"))
        assert result is True

        # Reload transcript and check normalized_text was updated
        refreshed = coord.db.get_transcript(t.id)
        assert refreshed is not None
        assert refreshed.text == "edited text"
        assert refreshed.normalized_text == "edited text"

    def test_commit_preserves_raw(self, wired):
        """Raw text must remain immutable after edits."""
        coord, events = wired
        t = coord.db.add_transcript(raw_text="original", duration_ms=100)

        from src.core.intents.definitions import CommitEditsIntent

        coord.command_bus.dispatch(CommitEditsIntent(transcript_id=t.id, content="new version"))

        refreshed = coord.db.get_transcript(t.id)
        assert refreshed.raw_text == "original"
        assert refreshed.text == "new version"


# ── Delete intents ───────────────────────────────────────────────────────


class TestDeleteIntents:
    """Delete intents mutate through CommandBus and emit domain events."""

    def test_delete_transcript_removes_row_and_emits_event(self, wired):
        coord, events = wired
        t = coord.db.add_transcript(raw_text="delete me", duration_ms=100)

        from src.core.intents.definitions import DeleteTranscriptIntent

        success, result = coord.command_bus.dispatch_result(DeleteTranscriptIntent(transcript_id=t.id))

        assert success is True
        assert result == {"deleted": True}
        assert coord.db.get_transcript(t.id) is None
        assert events.of_type("transcript_deleted") == [{"id": t.id}]

    def test_delete_default_prompt_clears_config(self, wired):
        coord, events = wired
        t = coord.db.add_transcript(raw_text="prompt text", duration_ms=100)

        from src.core.intents.definitions import DeleteTranscriptIntent, UpdateConfigIntent

        coord.command_bus.dispatch(
            UpdateConfigIntent(settings={"refinement": {"default_prompt_transcript_id": t.id}}),
        )
        success, result = coord.command_bus.dispatch_result(DeleteTranscriptIntent(transcript_id=t.id))

        assert success is True
        assert result == {"deleted": True}
        assert coord.settings.refinement.default_prompt_transcript_id is None
        assert events.of_type("config_updated")[-1]["refinement"]["default_prompt_transcript_id"] is None

    def test_batch_delete_transcripts_returns_count(self, wired):
        coord, events = wired
        first = coord.db.add_transcript(raw_text="first", duration_ms=100)
        second = coord.db.add_transcript(raw_text="second", duration_ms=100)

        from src.core.intents.definitions import BatchDeleteTranscriptsIntent

        success, result = coord.command_bus.dispatch_result(
            BatchDeleteTranscriptsIntent(transcript_ids=(first.id, second.id)),
        )

        assert success is True
        assert result == {"deleted": 2}
        assert events.of_type("transcripts_batch_deleted") == [
            {"ids": [first.id, second.id], "count": 2},
        ]

    def test_delete_tag_removes_tag_and_emits_event(self, wired):
        coord, events = wired
        tag = coord.db.add_tag("Temporary", color="#ffffff")

        from src.core.intents.definitions import DeleteTagIntent

        success, result = coord.command_bus.dispatch_result(DeleteTagIntent(tag_id=tag.id))

        assert success is True
        assert result == {"deleted": True}
        assert coord.db.get_tag(tag.id) is None
        assert events.of_type("tag_deleted") == [{"id": tag.id}]


# ── RefineTranscriptIntent (error paths) ──────────────────────────────────


class TestRefineTranscriptValidation:
    """Refinement validation paths (no SLM loaded in test coordinator)."""

    def test_refine_without_slm_emits_error(self, wired):
        """With no SLM runtime, refinement should emit an error event."""
        coord, events = wired
        t = coord.db.add_transcript(raw_text="refine me", duration_ms=100)

        from src.core.intents.definitions import RefineTranscriptIntent

        result = coord.command_bus.dispatch(RefineTranscriptIntent(transcript_id=t.id, level=2))
        assert result is True

        errors = events.of_type("refinement_error")
        assert len(errors) == 1
        assert "not configured" in errors[0]["message"].lower() or "not available" in errors[0]["message"].lower()

    def test_refine_nonexistent_transcript_emits_error(self, wired):
        """Refinement of a non-existent transcript should emit error."""
        coord, events = wired
        # Give it a mock SLM runtime with READY state so it passes state checks
        from unittest.mock import MagicMock

        from src.services.slm_types import SLMState

        mock_slm = MagicMock()
        mock_slm.state = SLMState.READY
        coord.slm_runtime = mock_slm

        from src.core.intents.definitions import RefineTranscriptIntent

        result = coord.command_bus.dispatch(RefineTranscriptIntent(transcript_id=99999, level=1))
        assert result is True

        errors = events.of_type("refinement_error")
        assert len(errors) == 1
        assert "not found" in errors[0]["message"].lower()


# ── Recording State Machine ──────────────────────────────────────────────


class TestRecordingStateMachine:
    """Recording intent handlers manage _is_recording state correctly."""

    def test_begin_without_audio_service_is_noop(self, wired):
        """BeginRecording with no audio_service does nothing."""
        coord, events = wired
        assert coord.audio_service is None

        from src.core.intents.definitions import BeginRecordingIntent

        coord.command_bus.dispatch(BeginRecordingIntent())

        assert coord.recording_session._is_recording is False
        assert len(events.of_type("recording_started")) == 0

    def test_cancel_when_not_recording_is_noop(self, wired):
        """CancelRecording when not recording does nothing."""
        coord, events = wired

        from src.core.intents.definitions import CancelRecordingIntent

        coord.command_bus.dispatch(CancelRecordingIntent())

        assert coord.recording_session._is_recording is False
        assert len(events.of_type("recording_stopped")) == 0

    def test_stop_when_not_recording_is_noop(self, wired):
        """StopRecording when not recording does nothing."""
        coord, events = wired

        from src.core.intents.definitions import StopRecordingIntent

        coord.command_bus.dispatch(StopRecordingIntent())

        assert coord.recording_session._is_recording is False

    def test_toggle_dispatches_begin_when_idle(self, wired):
        """ToggleRecording when idle dispatches BeginRecording (which is noop without audio)."""
        coord, events = wired

        from src.core.intents.definitions import ToggleRecordingIntent

        coord.command_bus.dispatch(ToggleRecordingIntent())

        # No audio service → begin is noop
        assert coord.recording_session._is_recording is False

    def test_toggle_dispatches_stop_when_recording(self, wired):
        """ToggleRecording when recording dispatches StopRecording."""
        coord, events = wired
        # Manually set recording state
        coord.recording_session._is_recording = True

        from src.core.intents.definitions import ToggleRecordingIntent

        coord.command_bus.dispatch(ToggleRecordingIntent())

        # StopRecording sets the stop event
        assert coord.recording_session._recording_stop.is_set()


# ── RetitleTranscriptIntent ───────────────────────────────────────────────


class TestRetitleTranscript:
    """RetitleTranscript with no TitleGenerator is a safe noop."""

    def test_retitle_without_generator_is_noop(self, wired):
        """No title_generator → silently returns."""
        coord, events = wired
        assert coord.title_generator is None
        t = coord.db.add_transcript(raw_text="some text", duration_ms=100)

        from src.core.intents.definitions import RetitleTranscriptIntent

        coord.command_bus.dispatch(RetitleTranscriptIntent(transcript_id=t.id))

        # No crash, no events — just a silent noop
        assert len(events.events) == 0


# ── UpdateConfigIntent ────────────────────────────────────────────────────


class TestUpdateConfig:
    """UpdateConfig via CommandBus → settings updated + event emitted."""

    def test_update_config_emits_event(self, wired):
        coord, events = wired

        from src.core.intents.definitions import UpdateConfigIntent

        coord.command_bus.dispatch(
            UpdateConfigIntent(settings={"output": {"auto_copy_to_clipboard": False}}),
        )

        cfg_events = events.of_type("config_updated")
        assert len(cfg_events) == 1
        # config_updated payload is the full settings model_dump()
        assert cfg_events[0]["output"]["auto_copy_to_clipboard"] is False

    def test_update_config_applies_to_coordinator(self, wired):
        """Settings object on coordinator should reflect the new value."""
        coord, events = wired

        from src.core.intents.definitions import UpdateConfigIntent

        coord.command_bus.dispatch(
            UpdateConfigIntent(settings={"output": {"auto_copy_to_clipboard": False}}),
        )

        assert coord.settings.output.auto_copy_to_clipboard is False

    def test_update_config_supports_delete_confirmation_setting(self, wired):
        coord, events = wired

        from src.core.intents.definitions import UpdateConfigIntent

        coord.command_bus.dispatch(
            UpdateConfigIntent(settings={"safety": {"confirm_delete": False}}),
        )

        cfg_events = events.of_type("config_updated")
        assert cfg_events[-1]["safety"]["confirm_delete"] is False
        assert coord.settings.safety.confirm_delete is False


# ── RestartEngineIntent ───────────────────────────────────────────────────


class TestRestartEngine:
    """RestartEngine dispatches the coordinator's restart_engine method."""

    def test_restart_engine_calls_method(self, wired):
        """Validate the intent dispatches to restart_engine."""
        from unittest.mock import MagicMock

        coord, events = wired
        coord.restart_engine = MagicMock()

        # SystemHandlers holds a reference to the restart_engine callable
        # captured at __init__ time, so we need to re-register to pick up mock
        from src.core.handlers.system_handlers import SystemHandlers
        from src.core.intents.definitions import RestartEngineIntent

        system = SystemHandlers(
            event_bus_emit=coord.event_bus.emit,
            input_listener_provider=lambda: coord.input_listener,
            on_settings_updated=lambda s: setattr(coord, "settings", s),
            restart_engine=coord.restart_engine,
        )
        coord.command_bus.register(RestartEngineIntent, system.handle_restart_engine)

        coord.command_bus.dispatch(RestartEngineIntent())

        coord.restart_engine.assert_called_once()
