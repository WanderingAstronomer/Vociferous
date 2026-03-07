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
    "transcript_updated",
    "transcripts_cleared",
    "refinement_started",
    "refinement_complete",
    "refinement_error",
    "transcription_complete",
    "transcription_error",
    "config_updated",
    "batch_retitle_progress",
    "tag_created",
    "tag_updated",
    "tag_deleted",
]


@pytest.fixture()
def wired(coordinator, event_collector):
    """Coordinator with EventCollector subscribed to all domain events."""
    event_collector.subscribe_all(coordinator.event_bus, ALL_EVENTS)
    return coordinator, event_collector


# ── DeleteTranscriptIntent ────────────────────────────────────────────────


class TestDeleteTranscript:
    """Delete transcript via CommandBus → DB row removed + event emitted."""

    def test_delete_existing(self, wired):
        coord, events = wired
        t = coord.db.add_transcript(raw_text="hello world", duration_ms=1000)
        assert coord.db.get_transcript(t.id) is not None

        from src.core.intents.definitions import DeleteTranscriptIntent

        result = coord.command_bus.dispatch(DeleteTranscriptIntent(transcript_id=t.id))

        assert result is True
        assert coord.db.get_transcript(t.id) is None
        deleted_events = events.of_type("transcript_deleted")
        assert len(deleted_events) == 1
        assert deleted_events[0]["id"] == t.id

    def test_delete_nonexistent_no_crash(self, wired):
        """Deleting a non-existent transcript should not raise or emit."""
        coord, events = wired
        from src.core.intents.definitions import DeleteTranscriptIntent

        result = coord.command_bus.dispatch(DeleteTranscriptIntent(transcript_id=99999))
        # Handler runs but db.delete_transcript returns False → no event emitted
        assert result is True
        assert len(events.of_type("transcript_deleted")) == 0

    def test_delete_without_db(self, coordinator, event_collector):
        """If db is None, handler silently returns."""
        event_collector.subscribe_all(coordinator.event_bus, ALL_EVENTS)
        coordinator.db = None

        from src.core.intents.definitions import DeleteTranscriptIntent

        result = coordinator.command_bus.dispatch(DeleteTranscriptIntent(transcript_id=1))
        assert result is True
        assert len(event_collector.of_type("transcript_deleted")) == 0


# ── CommitEditsIntent ─────────────────────────────────────────────────────


class TestCommitEdits:
    """Commit edits via CommandBus → variant created in DB."""

    def test_commit_creates_variant(self, wired):
        coord, events = wired
        t = coord.db.add_transcript(raw_text="original text", duration_ms=500)

        from src.core.intents.definitions import CommitEditsIntent

        result = coord.command_bus.dispatch(CommitEditsIntent(transcript_id=t.id, content="edited text"))
        assert result is True

        # Reload transcript and check variant
        refreshed = coord.db.get_transcript(t.id)
        assert refreshed is not None
        assert refreshed.text == "edited text"
        assert refreshed.current_variant_id is not None

    def test_commit_preserves_raw(self, wired):
        """Raw text must remain immutable after edits."""
        coord, events = wired
        t = coord.db.add_transcript(raw_text="original", duration_ms=100)

        from src.core.intents.definitions import CommitEditsIntent

        coord.command_bus.dispatch(CommitEditsIntent(transcript_id=t.id, content="new version"))

        refreshed = coord.db.get_transcript(t.id)
        assert refreshed.raw_text == "original"
        assert refreshed.text == "new version"


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


# ── ClearTranscriptsIntent ────────────────────────────────────────────────


class TestClearTranscripts:
    """Clear all transcripts via CommandBus → DB emptied + event emitted."""

    def test_clear_deletes_all(self, wired):
        coord, events = wired
        coord.db.add_transcript(raw_text="one", duration_ms=100)
        coord.db.add_transcript(raw_text="two", duration_ms=200)

        from src.core.intents.definitions import ClearTranscriptsIntent

        coord.command_bus.dispatch(ClearTranscriptsIntent())

        cleared = events.of_type("transcripts_cleared")
        assert len(cleared) == 1
        assert cleared[0]["count"] == 2

        # Verify rows are gone
        assert coord.db.get_transcript(1) is None
        assert coord.db.get_transcript(2) is None

    def test_clear_empty_db(self, wired):
        """Clearing with no transcripts emits count 0."""
        coord, events = wired

        from src.core.intents.definitions import ClearTranscriptsIntent

        coord.command_bus.dispatch(ClearTranscriptsIntent())

        cleared = events.of_type("transcripts_cleared")
        assert len(cleared) == 1
        assert cleared[0]["count"] == 0


# ── DeleteTranscriptVariantIntent ─────────────────────────────────────────


class TestDeleteTranscriptVariant:
    """Delete a specific variant via CommandBus → DB + conditional event."""

    def test_delete_variant_emits_update(self, wired):
        coord, events = wired
        t = coord.db.add_transcript(raw_text="base text", duration_ms=500)
        v = coord.db.add_variant(t.id, "user_edit", "edited", set_current=True)

        from src.core.intents.definitions import DeleteTranscriptVariantIntent

        coord.command_bus.dispatch(
            DeleteTranscriptVariantIntent(transcript_id=t.id, variant_id=v.id),
        )

        updated = events.of_type("transcript_updated")
        assert len(updated) == 1
        assert updated[0]["id"] == t.id

    def test_delete_nonexistent_variant_no_event(self, wired):
        """Deleting a variant that doesn't exist emits nothing."""
        coord, events = wired
        t = coord.db.add_transcript(raw_text="base", duration_ms=100)

        from src.core.intents.definitions import DeleteTranscriptVariantIntent

        coord.command_bus.dispatch(
            DeleteTranscriptVariantIntent(transcript_id=t.id, variant_id=99999),
        )

        assert len(events.of_type("transcript_updated")) == 0


# ── RenameTranscriptIntent ────────────────────────────────────────────────


class TestRenameTranscript:
    """Rename transcript via CommandBus → display_name set + event."""

    def test_rename_emits_update(self, wired):
        coord, events = wired
        t = coord.db.add_transcript(raw_text="hello", duration_ms=100)

        from src.core.intents.definitions import RenameTranscriptIntent

        coord.command_bus.dispatch(
            RenameTranscriptIntent(transcript_id=t.id, title="My Title"),
        )

        updated = events.of_type("transcript_updated")
        assert len(updated) == 1
        assert updated[0]["id"] == t.id

        # Verify in DB
        refreshed = coord.db.get_transcript(t.id)
        assert refreshed.display_name == "My Title"

    def test_rename_empty_title_is_noop(self, wired):
        """Empty/whitespace title should NOT rename or emit."""
        coord, events = wired
        t = coord.db.add_transcript(raw_text="hello", duration_ms=100)

        from src.core.intents.definitions import RenameTranscriptIntent

        coord.command_bus.dispatch(
            RenameTranscriptIntent(transcript_id=t.id, title="   "),
        )

        assert len(events.of_type("transcript_updated")) == 0


# ── BatchRetitleIntent ────────────────────────────────────────────────────


class TestBatchRetitle:
    """BatchRetitle with no TitleGenerator emits an error event."""

    def test_batch_retitle_without_generator(self, wired):
        """No title_generator → error event emitted."""
        coord, events = wired
        assert coord.title_generator is None

        from src.core.intents.definitions import BatchRetitleIntent

        coord.command_bus.dispatch(BatchRetitleIntent())

        errors = events.of_type("batch_retitle_progress")
        assert len(errors) == 1
        assert errors[0]["status"] == "error"


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
