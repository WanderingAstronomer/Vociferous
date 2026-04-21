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
    "transcript_updated",
    "refinement_started",
    "refinement_complete",
    "refinement_error",
    "transcription_complete",
    "transcription_error",
    "config_updated",
    "engine_status",
    "tag_created",
    "tag_updated",
    "tag_deleted",
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
        assert fresh_coordinator.window._main_window is None

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

    def test_restart_lock_initialized(self, fresh_coordinator):
        """_restart_lock must be a real Lock after __init__, not lazily created."""
        # Previously created lazily with `if not hasattr(self, "_restart_lock")`.
        # Now it must exist immediately after construction — no hasattr required.
        lock = fresh_coordinator._restart_lock
        assert lock is not None
        assert hasattr(lock, "acquire")
        assert hasattr(lock, "release")


# ── Handler Registration ──────────────────────────────────────────────────


class TestHandlerRegistration:
    """Verify that _register_handlers wires all expected intents."""

    def test_all_intents_registered(self, coordinator):
        """Every intent defined in the coordinator must have a handler."""
        from src.core.intents.definitions import (
            AppendToTranscriptIntent,
            BeginRecordingIntent,
            BulkRefineTranscriptsIntent,
            CancelBulkRefinementIntent,
            CancelRecordingIntent,
            CommitEditsIntent,
            CommitRefinementIntent,
            RefineTranscriptIntent,
            RestartEngineIntent,
            RetitleTranscriptIntent,
            RevertToRawIntent,
            SetAnalyticsInclusionIntent,
            StopRecordingIntent,
            ToggleRecordingIntent,
            UpdateConfigIntent,
        )

        expected_intents = [
            BeginRecordingIntent,
            StopRecordingIntent,
            CancelRecordingIntent,
            ToggleRecordingIntent,
            CommitEditsIntent,
            RevertToRawIntent,
            AppendToTranscriptIntent,
            SetAnalyticsInclusionIntent,
            RefineTranscriptIntent,
            CommitRefinementIntent,
            BulkRefineTranscriptsIntent,
            CancelBulkRefinementIntent,
            UpdateConfigIntent,
            RestartEngineIntent,
            RetitleTranscriptIntent,
        ]

        for intent_cls in expected_intents:
            assert intent_cls in coordinator.command_bus._handlers, (
                f"{intent_cls.__name__} not registered in CommandBus"
            )

    def test_handler_count_matches_intent_count(self, coordinator):
        """No extra/ghost handlers registered beyond the expected set."""
        # 17 intents are registered in _register_handlers
        assert len(coordinator.command_bus._handlers) == 17

    def test_handlers_are_callable(self, coordinator):
        """Every registered handler must be callable."""
        for intent_cls, handler in coordinator.command_bus._handlers.items():
            assert callable(handler), f"Handler for {intent_cls.__name__} is not callable"

    def test_double_register_does_not_duplicate(self, coordinator):
        """Calling _register_handlers again overwrites, doesn't stack."""
        coordinator._register_handlers()
        assert len(coordinator.command_bus._handlers) == 17


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
        db_ref = coordinator.db
        coordinator.cleanup()
        # The underlying sqlite connection must be unusable after cleanup.
        # sqlite3 raises ProgrammingError on operations against a closed conn.
        with pytest.raises(Exception):  # noqa: BLE001 - sqlite3.ProgrammingError on closed conn
            db_ref._conn.execute("SELECT 1").fetchone()

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
        """cleanup() calls shutdown() on the SLM runtime if present."""
        mock_slm = MagicMock()
        coordinator.slm_runtime = mock_slm

        coordinator.cleanup()
        mock_slm.shutdown.assert_called_once()

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
        """cleanup() continues even if SLM shutdown() raises."""
        mock_slm = MagicMock()
        mock_slm.shutdown.side_effect = RuntimeError("SLM cleanup boom")
        coordinator.slm_runtime = mock_slm

        # Should not raise
        coordinator.cleanup()
        mock_slm.shutdown.assert_called_once()

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
        from src.core.intents.definitions import CommitEditsIntent

        t = coord.db.add_transcript(raw_text="test", duration_ms=100)
        result = coord.command_bus.dispatch(CommitEditsIntent(transcript_id=t.id, content="edited"))
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

    def test_full_pipeline_commit(self, wired):
        """Intent dispatch → handler mutates DB → EventBus emits event."""
        coord, events = wired
        t = coord.db.add_transcript(raw_text="pipeline test", duration_ms=500)

        from src.core.intents.definitions import CommitEditsIntent

        coord.command_bus.dispatch(CommitEditsIntent(transcript_id=t.id, content="updated text"))

        # DB mutation
        refreshed = coord.db.get_transcript(t.id)
        assert refreshed.normalized_text == "updated text"

        # Event emission
        updated = events.of_type("transcript_updated")
        assert len(updated) == 1
        assert updated[0]["id"] == t.id


# ── Graceful Degradation ─────────────────────────────────────────────────


class TestGracefulDegradation:
    """Verify coordinator operates correctly when optional services are unavailable."""

    def test_handlers_work_without_audio(self, wired):
        """All non-recording handlers work even with audio_service=None."""
        coord, events = wired
        assert coord.audio_service is None

        from src.core.intents.definitions import CommitEditsIntent

        t = coord.db.add_transcript(raw_text="no audio needed", duration_ms=100)
        coord.command_bus.dispatch(CommitEditsIntent(transcript_id=t.id, content="edited"))

        assert len(events.of_type("transcript_updated")) == 1

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
            RefineTranscriptIntent,
            StopRecordingIntent,
            ToggleRecordingIntent,
        )

        # None of these should raise
        coordinator.command_bus.dispatch(BeginRecordingIntent())
        coordinator.command_bus.dispatch(StopRecordingIntent())
        coordinator.command_bus.dispatch(CancelRecordingIntent())
        coordinator.command_bus.dispatch(ToggleRecordingIntent())
        coordinator.command_bus.dispatch(CommitEditsIntent(transcript_id=1, content="x"))
        coordinator.command_bus.dispatch(RefineTranscriptIntent(transcript_id=1, level=1))

        # No events emitted for DB-dependent operations when db=None
        assert len(event_collector.of_type("transcript_updated")) == 0


# ── Coordinator Query Accessors ───────────────────────────────────────────


class TestCoordinatorAccessors:
    """Verify coordinator query accessor methods that shield the API layer from internals."""

    def test_get_transcript_count_with_db(self, coordinator):
        """get_transcript_count() returns correct count from the database."""
        baseline = coordinator.get_transcript_count()
        coordinator.db.add_transcript(raw_text="hello", duration_ms=100)
        assert coordinator.get_transcript_count() == baseline + 1

    def test_get_transcript_count_no_db(self, fresh_coordinator):
        """get_transcript_count() returns 0 when db is None (safe default)."""
        assert fresh_coordinator.db is None
        assert fresh_coordinator.get_transcript_count() == 0

    def test_is_recording_active_idle(self, coordinator):
        """is_recording_active() returns False when the session is not recording."""
        assert coordinator.is_recording_active() is False

    def test_is_recording_active_no_session(self, fresh_coordinator):
        """is_recording_active() returns False when recording_session is None."""
        assert fresh_coordinator.recording_session is None
        assert fresh_coordinator.is_recording_active() is False

    def test_get_insight_text_no_manager(self, coordinator):
        """get_insight_text() returns empty string when insight_manager is None."""
        assert coordinator.insight_manager is None
        assert coordinator.get_insight_text() == ""

    def test_get_insight_text_with_manager(self, coordinator):
        """get_insight_text() delegates to insight_manager.cached_text."""
        from unittest.mock import MagicMock

        mock_manager = MagicMock()
        mock_manager.cached_text = "Some insight text"
        coordinator.insight_manager = mock_manager
        assert coordinator.get_insight_text() == "Some insight text"

    def test_get_motd_text_aliases_insight(self, coordinator):
        """get_motd_text() returns the same cached text as get_insight_text()."""
        from unittest.mock import MagicMock

        mock_manager = MagicMock()
        mock_manager.cached_text = "Unified insight"
        coordinator.insight_manager = mock_manager
        assert coordinator.get_motd_text() == "Unified insight"


# ── Engine Restarted Event ────────────────────────────────────────────────


class TestEngineRestartedEvent:
    """engine_restarted event is emitted after restart, not a direct API import."""

    def test_engine_restarted_event_emitted(self, coordinator, event_collector):
        """restart_engine() emits 'engine_restarted' on the event bus when done."""
        import threading

        event_received = threading.Event()
        coordinator.event_bus.on("engine_restarted", lambda _data: event_received.set())

        # Use patches so the actual heavy model reload is skipped
        from unittest.mock import patch

        with (
            patch.object(coordinator, "_init_slm_runtime"),
            patch("src.core.settings.get_settings", return_value=coordinator.settings),
        ):
            coordinator.restart_engine()
            # Wait until the background thread signals completion, or time out
            assert event_received.wait(timeout=5.0), "engine_restarted event not emitted within 5 s"


# ── Server Ready Probe ────────────────────────────────────────────────────


class TestWaitForServer:
    """_wait_for_server exits only when the port is accepting connections."""

    def test_returns_immediately_when_server_is_up(self, fresh_coordinator):
        """If the port is already listening, _wait_for_server returns within a few ms."""
        import socket

        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(("127.0.0.1", 0))
        server_sock.listen(1)
        _, port = server_sock.getsockname()

        try:
            fresh_coordinator._wait_for_server(host="127.0.0.1", port=port, timeout=5.0)
        finally:
            server_sock.close()

    def test_waits_until_server_comes_up(self, fresh_coordinator):
        """_wait_for_server blocks until the port opens, then returns."""
        import socket
        import threading
        import time

        # Grab a free port by binding briefly, then release it.
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()

        # Run _wait_for_server concurrently — it will poll and block.
        probe_done = threading.Event()
        probe_start = time.monotonic()

        def run_probe() -> None:
            fresh_coordinator._wait_for_server(host="127.0.0.1", port=port, timeout=5.0)
            probe_done.set()

        probe_thread = threading.Thread(target=run_probe, daemon=True)
        probe_thread.start()

        # Open the socket after a deliberate delay.
        time.sleep(0.3)
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", port))
        srv.listen(1)

        assert probe_done.wait(timeout=3.0), "_wait_for_server never returned"
        elapsed = time.monotonic() - probe_start
        srv.close()
        probe_thread.join(timeout=1.0)

        assert elapsed >= 0.2, f"returned too fast ({elapsed:.3f}s) — likely a false positive"

    def test_times_out_gracefully_when_server_never_starts(self, fresh_coordinator):
        """_wait_for_server logs a warning and returns (does not raise) after timeout."""
        import socket

        # Grab a free port and immediately close it — nothing is listening there.
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()

        # Must return without raising even though the port is deaf.
        fresh_coordinator._wait_for_server(host="127.0.0.1", port=port, timeout=0.3)
