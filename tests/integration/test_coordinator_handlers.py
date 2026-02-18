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
    "project_created",
    "project_deleted",
    "refinement_started",
    "refinement_complete",
    "refinement_error",
    "transcription_complete",
    "transcription_error",
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
        """Deleting a non-existent transcript should not raise."""
        coord, events = wired
        from src.core.intents.definitions import DeleteTranscriptIntent

        result = coord.command_bus.dispatch(DeleteTranscriptIntent(transcript_id=99999))
        # Handler still runs (db.delete_transcript returns False silently)
        assert result is True
        # Event is still emitted (current behavior — handler doesn't check return)
        assert len(events.of_type("transcript_deleted")) == 1

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


# ── CreateProjectIntent ───────────────────────────────────────────────────


class TestCreateProject:
    """Create project via CommandBus → DB row + event emitted."""

    def test_create_project(self, wired):
        coord, events = wired

        from src.core.intents.definitions import CreateProjectIntent

        result = coord.command_bus.dispatch(CreateProjectIntent(name="Test Project", color="#ff0000"))
        assert result is True

        created = events.of_type("project_created")
        assert len(created) == 1
        assert created[0]["name"] == "Test Project"
        assert created[0]["color"] == "#ff0000"
        assert created[0]["id"] is not None

        # Verify in DB
        projects = coord.db.get_projects()
        assert any(p.name == "Test Project" for p in projects)

    def test_create_project_without_db(self, coordinator, event_collector):
        """If db is None, handler silently returns with no event."""
        event_collector.subscribe_all(coordinator.event_bus, ALL_EVENTS)
        coordinator.db = None

        from src.core.intents.definitions import CreateProjectIntent

        result = coordinator.command_bus.dispatch(CreateProjectIntent(name="Ghost"))
        assert result is True
        assert len(event_collector.of_type("project_created")) == 0


# ── DeleteProjectIntent ───────────────────────────────────────────────────


class TestDeleteProject:
    """Delete project via CommandBus → DB row removed + event emitted."""

    def test_delete_existing_project(self, wired):
        coord, events = wired
        p = coord.db.add_project(name="Doomed Project")

        from src.core.intents.definitions import DeleteProjectIntent

        result = coord.command_bus.dispatch(DeleteProjectIntent(project_id=p.id))
        assert result is True

        deleted = events.of_type("project_deleted")
        assert len(deleted) == 1
        assert deleted[0]["id"] == p.id

        # Verify removed from DB
        projects = coord.db.get_projects()
        assert not any(proj.id == p.id for proj in projects)

    def test_delete_nonexistent_project_no_event(self, wired):
        """Deleting a non-existent project should NOT emit an event."""
        coord, events = wired

        from src.core.intents.definitions import DeleteProjectIntent

        result = coord.command_bus.dispatch(DeleteProjectIntent(project_id=99999))
        assert result is True
        # Handler checks return value and only emits on success
        assert len(events.of_type("project_deleted")) == 0


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
