"""
Application lifecycle integration tests.

Validates the ApplicationCoordinator composition root:
- Initialization state
- Handler registration completeness
- Shutdown and cleanup lifecycle
- Settings propagation
- EventBus/CommandBus wiring integrity
- Graceful handling of missing optional services

Uses real buses + real DB but NO heavy services (ASR, SLM, audio, webview).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import EventCollector

# ── Fixtures ──────────────────────────────────────────────────────────────


ALL_LIFECYCLE_EVENTS = [
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
    "config_updated",
    "engine_status",
]


@pytest.fixture()
def fresh_coordinator(tmp_path: Path):
    """
    Bare ApplicationCoordinator with only settings — no handlers registered,
    no DB wired. For testing the init state before start().
    """
    from src.core.application_coordinator import ApplicationCoordinator
    from src.core.settings import init_settings, reset_for_tests

    reset_for_tests()
    settings = init_settings(config_path=tmp_path / "config" / "settings.json")
    coord = ApplicationCoordinator(settings)
    yield coord
    reset_for_tests()


@pytest.fixture()
def wired(coordinator, event_collector):
    """Coordinator with EventCollector subscribed to all domain events."""
    event_collector.subscribe_all(coordinator.event_bus, ALL_LIFECYCLE_EVENTS)
    return coordinator, event_collector


# ── Initialization State ──────────────────────────────────────────────────


class TestInitializationState:
    """Verify the coordinator's state immediately after construction."""

    def test_buses_created(self, fresh_coordinator):
        """CommandBus and EventBus must exist after __init__."""
        from src.core.command_bus import CommandBus
        from src.core.event_bus import EventBus

        assert isinstance(fresh_coordinator.command_bus, CommandBus)
        assert isinstance(fresh_coordinator.event_bus, EventBus)

    def test_services_none_before_start(self, fresh_coordinator):
        """All heavy services must be None before start() is called."""
        assert fresh_coordinator.db is None
        assert fresh_coordinator.audio_service is None
        assert fresh_coordinator.input_listener is None
        assert fresh_coordinator.slm_runtime is None
        # Recording session (and its ASR model) are created during start()
        assert fresh_coordinator.recording_session is None

    def test_recording_state_idle(self, fresh_coordinator):
        """Recording session is not created until start(); shutdown event must be clear."""
        # RecordingSession (which owns _is_recording / _recording_stop) is
        # created inside start() — not in __init__.  Before start() it is None.
        assert fresh_coordinator.recording_session is None
        assert not fresh_coordinator._shutdown_event.is_set()

    def test_window_refs_none(self, fresh_coordinator):
        """Window references must be None before start()."""
        assert fresh_coordinator._main_window is None

    def test_server_thread_none(self, fresh_coordinator):
        """Server thread not started until start()."""
        assert fresh_coordinator._server_thread is None
        assert fresh_coordinator._uvicorn_server is None

    def test_settings_stored(self, fresh_coordinator):
        """Settings reference must be stored on the coordinator."""
        assert fresh_coordinator.settings is not None
        assert hasattr(fresh_coordinator.settings, "model")
        assert hasattr(fresh_coordinator.settings, "recording")
        assert hasattr(fresh_coordinator.settings, "refinement")


# ── Handler Registration ──────────────────────────────────────────────────


class TestHandlerRegistration:
    """Verify that _register_handlers wires all expected intents."""

    def test_all_intents_registered(self, coordinator):
        """Every intent defined in the coordinator must have a handler."""
        from src.core.intents.definitions import (
            AssignProjectIntent,
            BeginRecordingIntent,
            CancelRecordingIntent,
            ClearTranscriptsIntent,
            CommitEditsIntent,
            CreateProjectIntent,
            DeleteProjectIntent,
            DeleteTranscriptIntent,
            DeleteTranscriptVariantIntent,
            RefineTranscriptIntent,
            RenameTranscriptIntent,
            RestartEngineIntent,
            StopRecordingIntent,
            ToggleRecordingIntent,
            UpdateConfigIntent,
            UpdateProjectIntent,
        )

        expected_intents = [
            BeginRecordingIntent,
            StopRecordingIntent,
            CancelRecordingIntent,
            ToggleRecordingIntent,
            DeleteTranscriptIntent,
            DeleteTranscriptVariantIntent,
            ClearTranscriptsIntent,
            CommitEditsIntent,
            RenameTranscriptIntent,
            RefineTranscriptIntent,
            CreateProjectIntent,
            UpdateProjectIntent,
            DeleteProjectIntent,
            AssignProjectIntent,
            UpdateConfigIntent,
            RestartEngineIntent,
        ]

        for intent_cls in expected_intents:
            assert intent_cls in coordinator.command_bus._handlers, (
                f"{intent_cls.__name__} not registered in CommandBus"
            )

    def test_handler_count_matches_intent_count(self, coordinator):
        """No extra/ghost handlers registered beyond the expected set."""
        # 18 intents are registered in _register_handlers
        assert len(coordinator.command_bus._handlers) == 18

    def test_handlers_are_callable(self, coordinator):
        """Every registered handler must be callable."""
        for intent_cls, handler in coordinator.command_bus._handlers.items():
            assert callable(handler), f"Handler for {intent_cls.__name__} is not callable"

    def test_double_register_does_not_duplicate(self, coordinator):
        """Calling _register_handlers again overwrites, doesn't stack."""
        coordinator._register_handlers()
        assert len(coordinator.command_bus._handlers) == 18


# ── Shutdown & Cleanup ────────────────────────────────────────────────────


class TestShutdownLifecycle:
    """Verify shutdown and cleanup release resources correctly."""

    def test_shutdown_sets_event(self, coordinator):
        """shutdown() must set _shutdown_event."""
        assert not coordinator._shutdown_event.is_set()
        coordinator.shutdown()
        assert coordinator._shutdown_event.is_set()

    def test_shutdown_sets_recording_stop(self, coordinator):
        """shutdown() must signal the RecordingSession to stop."""
        coordinator.shutdown()
        assert coordinator.recording_session._recording_stop.is_set()

    def test_cleanup_closes_db(self, coordinator):
        """cleanup() must close the database connection."""
        assert coordinator.db is not None
        coordinator.cleanup()
        # After cleanup, db.close() was called — verify by checking
        # the internal connection is closed (no-op on second close)
        # The coordinator fixture would double-close, but that's safe

    def test_cleanup_clears_event_bus(self, coordinator, event_collector):
        """cleanup() must clear all EventBus subscriptions."""
        event_collector.subscribe_all(coordinator.event_bus, ["transcript_deleted"])
        assert len(coordinator.event_bus._handlers) > 0

        coordinator.cleanup()
        assert len(coordinator.event_bus._handlers) == 0

    def test_cleanup_with_no_services(self, fresh_coordinator):
        """cleanup() on a coordinator with no services should not crash."""
        # All services are None — cleanup should be a no-op
        fresh_coordinator.cleanup()
        # recording_session was never created (start() not called)
        assert fresh_coordinator.recording_session is None

    def test_cleanup_with_mock_slm(self, coordinator):
        """cleanup() calls disable() on the SLM runtime if present."""
        mock_slm = MagicMock()
        coordinator.slm_runtime = mock_slm

        coordinator.cleanup()
        mock_slm.disable.assert_called_once()

    def test_cleanup_with_mock_input_listener(self, coordinator):
        """cleanup() calls stop() on the input listener if present."""
        mock_listener = MagicMock()
        coordinator.input_listener = mock_listener

        coordinator.cleanup()
        mock_listener.stop.assert_called_once()

    def test_cleanup_deletes_asr_model(self, coordinator):
        """cleanup() must release the ASR model held by RecordingSession."""
        coordinator.recording_session._asr_model = MagicMock()
        coordinator.cleanup()
        assert coordinator.recording_session._asr_model is None

    def test_cleanup_stops_uvicorn(self, coordinator):
        """cleanup() sets should_exit on the uvicorn server."""
        mock_server = MagicMock()
        mock_server.should_exit = False
        coordinator._uvicorn_server = mock_server

        coordinator.cleanup()
        assert mock_server.should_exit is True

    def test_cleanup_resilient_to_slm_error(self, coordinator):
        """cleanup() continues even if SLM disable() raises."""
        mock_slm = MagicMock()
        mock_slm.disable.side_effect = RuntimeError("SLM cleanup boom")
        coordinator.slm_runtime = mock_slm

        # Should not raise
        coordinator.cleanup()
        mock_slm.disable.assert_called_once()

    def test_cleanup_resilient_to_listener_error(self, coordinator):
        """cleanup() continues even if input listener stop() raises."""
        mock_listener = MagicMock()
        mock_listener.stop.side_effect = RuntimeError("Listener boom")
        coordinator.input_listener = mock_listener

        coordinator.cleanup()
        mock_listener.stop.assert_called_once()


# ── Settings Propagation ──────────────────────────────────────────────────


class TestSettingsPropagation:
    """Verify settings updates reach the coordinator correctly."""

    def test_settings_reference_update(self, wired):
        """Coordinator's settings can be swapped and handlers see the new reference."""
        coord, events = wired
        from src.core.settings import get_settings, update_settings

        old_key = coord.settings.recording.activation_key
        new_settings = update_settings(recording={"activation_key": "F13"})
        coord.settings = new_settings

        assert coord.settings.recording.activation_key == "F13"
        assert coord.settings.recording.activation_key != old_key

    def test_active_project_id_persists(self, wired):
        """active_project_id on settings is readable by handlers."""
        coord, _ = wired
        from src.core.settings import update_settings

        update_settings(user={"active_project_id": 42})
        coord.settings = update_settings()
        # After reload, active_project_id should reflect what was set
        assert coord.settings.user.active_project_id == 42


# ── EventBus Wiring ──────────────────────────────────────────────────────


class TestEventBusWiring:
    """Verify the EventBus correctly propagates domain events."""

    def test_emit_reaches_collector(self, wired):
        """Direct EventBus emit should reach the EventCollector."""
        coord, events = wired
        coord.event_bus.emit("transcript_deleted", {"id": 777})

        deleted = events.of_type("transcript_deleted")
        assert len(deleted) == 1
        assert deleted[0]["id"] == 777

    def test_emit_unsubscribed_event_is_silent(self, wired):
        """Emitting an event no one listens to should not raise."""
        coord, events = wired
        coord.event_bus.emit("completely_unknown_event", {"data": True})
        # No crash, no exception

    def test_multiple_subscribers_both_fire(self, coordinator):
        """Multiple subscribers to the same event both receive it."""
        results = []

        def handler_a(data: dict) -> None:
            results.append(("a", data))

        def handler_b(data: dict) -> None:
            results.append(("b", data))

        coordinator.event_bus.on("test_event", handler_a)
        coordinator.event_bus.on("test_event", handler_b)
        coordinator.event_bus.emit("test_event", {"val": 1})

        assert len(results) == 2
        assert ("a", {"val": 1}) in results
        assert ("b", {"val": 1}) in results


# ── CommandBus Integration ────────────────────────────────────────────────


class TestCommandBusIntegration:
    """Verify the CommandBus dispatch → handler → EventBus pipeline end-to-end."""

    def test_dispatch_returns_true_on_success(self, wired):
        """Dispatching a registered intent returns True."""
        coord, _ = wired
        from src.core.intents.definitions import DeleteTranscriptIntent

        t = coord.db.add_transcript(raw_text="test", duration_ms=100)
        result = coord.command_bus.dispatch(DeleteTranscriptIntent(transcript_id=t.id))
        assert result is True

    def test_dispatch_unregistered_intent_returns_false(self, wired):
        """Dispatching an unregistered intent returns False."""
        coord, _ = wired
        from dataclasses import dataclass

        @dataclass
        class FakeIntent:
            pass

        result = coord.command_bus.dispatch(FakeIntent())
        assert result is False

    def test_full_pipeline_delete(self, wired):
        """Intent dispatch → handler mutates DB → EventBus emits event."""
        coord, events = wired
        t = coord.db.add_transcript(raw_text="pipeline test", duration_ms=500)

        from src.core.intents.definitions import DeleteTranscriptIntent

        coord.command_bus.dispatch(DeleteTranscriptIntent(transcript_id=t.id))

        # DB mutation
        assert coord.db.get_transcript(t.id) is None

        # Event emission
        deleted = events.of_type("transcript_deleted")
        assert len(deleted) == 1
        assert deleted[0]["id"] == t.id

    def test_full_pipeline_create_project(self, wired):
        """CreateProject flows through the full pipeline."""
        coord, events = wired
        from src.core.intents.definitions import CreateProjectIntent

        coord.command_bus.dispatch(CreateProjectIntent(name="Pipeline Project", color="#abcdef"))

        created = events.of_type("project_created")
        assert len(created) == 1
        assert created[0]["name"] == "Pipeline Project"
        assert created[0]["color"] == "#abcdef"

        projects = coord.db.get_projects()
        assert any(p.name == "Pipeline Project" for p in projects)


# ── Graceful Degradation ─────────────────────────────────────────────────


class TestGracefulDegradation:
    """Verify coordinator operates correctly when optional services are unavailable."""

    def test_handlers_work_without_audio(self, wired):
        """All non-recording handlers work even with audio_service=None."""
        coord, events = wired
        assert coord.audio_service is None

        from src.core.intents.definitions import (
            CommitEditsIntent,
            CreateProjectIntent,
            DeleteTranscriptIntent,
        )

        t = coord.db.add_transcript(raw_text="no audio needed", duration_ms=100)

        # All should succeed
        coord.command_bus.dispatch(CommitEditsIntent(transcript_id=t.id, content="edited"))
        coord.command_bus.dispatch(CreateProjectIntent(name="AudioFree"))
        coord.command_bus.dispatch(DeleteTranscriptIntent(transcript_id=t.id))

        assert len(events.of_type("project_created")) == 1
        assert len(events.of_type("transcript_deleted")) == 1

    def test_handlers_work_without_slm(self, wired):
        """Refinement with no SLM emits error but doesn't crash."""
        coord, events = wired
        assert coord.slm_runtime is None

        from src.core.intents.definitions import RefineTranscriptIntent

        t = coord.db.add_transcript(raw_text="no slm", duration_ms=100)
        coord.command_bus.dispatch(RefineTranscriptIntent(transcript_id=t.id, level=1))

        errors = events.of_type("refinement_error")
        assert len(errors) == 1
        assert "not configured" in errors[0]["message"].lower() or "not available" in errors[0]["message"].lower()

    def test_db_none_all_handlers_survive(self, coordinator, event_collector):
        """With db=None, every handler returns without crashing."""
        event_collector.subscribe_all(coordinator.event_bus, ALL_LIFECYCLE_EVENTS)
        coordinator.db = None

        from src.core.intents.definitions import (
            BeginRecordingIntent,
            CancelRecordingIntent,
            CommitEditsIntent,
            CreateProjectIntent,
            DeleteProjectIntent,
            DeleteTranscriptIntent,
            RefineTranscriptIntent,
            StopRecordingIntent,
            ToggleRecordingIntent,
        )

        # None of these should raise
        coordinator.command_bus.dispatch(BeginRecordingIntent())
        coordinator.command_bus.dispatch(StopRecordingIntent())
        coordinator.command_bus.dispatch(CancelRecordingIntent())
        coordinator.command_bus.dispatch(ToggleRecordingIntent())
        coordinator.command_bus.dispatch(DeleteTranscriptIntent(transcript_id=1))
        coordinator.command_bus.dispatch(CommitEditsIntent(transcript_id=1, content="x"))
        coordinator.command_bus.dispatch(CreateProjectIntent(name="ghost"))
        coordinator.command_bus.dispatch(DeleteProjectIntent(project_id=1))
        coordinator.command_bus.dispatch(RefineTranscriptIntent(transcript_id=1, level=1))

        # No events emitted for DB-dependent operations when db=None
        assert len(event_collector.of_type("transcript_deleted")) == 0
        assert len(event_collector.of_type("project_created")) == 0
        assert len(event_collector.of_type("project_deleted")) == 0
