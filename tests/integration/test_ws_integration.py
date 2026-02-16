"""
WebSocket integration tests.

Verifies the full EventBus → ConnectionManager → WebSocket broadcast pipeline
and the WS command → CommandBus intent dispatch path.

These tests exercise the critical real-time communication artery:
  EventBus.emit(event) → bridge handler → broadcast_threadsafe() → WS client

Uses Litestar's sync TestClient with websocket_connect().
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from litestar import Litestar, WebSocket
from litestar.config.cors import CORSConfig
from litestar.handlers import websocket_listener
from litestar.testing import TestClient

from src.api.app import ConnectionManager, _handle_ws_message, _wire_event_bridge
from src.api.deps import set_coordinator
from tests.conftest import EventCollector

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def ws_app(coordinator, event_collector) -> Iterator[tuple]:
    """
    Litestar app with WebSocket handler, wired event bridge.

    Yields (client, coordinator, ws_manager, event_collector).
    """
    from collections.abc import AsyncGenerator
    from contextlib import asynccontextmanager
    from typing import Any

    set_coordinator(coordinator)

    ws_manager = ConnectionManager()
    _wire_event_bridge(coordinator, ws_manager)

    # Subscribe collector to key events
    ALL_EVENTS = [
        "recording_started", "recording_stopped",
        "transcript_deleted", "transcription_complete",
        "refinement_started", "refinement_complete", "refinement_error",
        "project_created", "project_deleted",
        "config_updated",
    ]
    event_collector.subscribe_all(coordinator.event_bus, ALL_EVENTS)

    @asynccontextmanager
    async def ws_lifespan(socket: WebSocket) -> AsyncGenerator[None, Any]:
        ws_manager.register(socket)
        try:
            yield
        finally:
            ws_manager.unregister(socket)

    @websocket_listener("/ws", connection_lifespan=ws_lifespan)
    async def ws_handler(data: str, socket: WebSocket) -> None:
        try:
            msg = json.loads(data)
            msg_type = msg.get("type", "")
        except (json.JSONDecodeError, AttributeError):
            return
        _handle_ws_message(coordinator, msg_type, msg.get("data", {}))

    app = Litestar(
        route_handlers=[ws_handler],
        cors_config=CORSConfig(
            allow_origins=["http://localhost:5173"],
            allow_methods=["*"],
            allow_headers=["*"],
        ),
        debug=True,
    )

    with TestClient(app=app) as client:
        yield client, coordinator, ws_manager, event_collector

    set_coordinator(None)


# ── Connection Lifecycle ──────────────────────────────────────────────────


class TestConnectionLifecycle:
    """WebSocket connect/disconnect correctly updates ConnectionManager."""

    def test_connect_registers_client(self, ws_app) -> None:
        client, _, ws_manager, _ = ws_app

        with client.websocket_connect("/ws") as ws:
            # Send a message to ensure the handler has started
            ws.send_text(json.dumps({"type": "ping"}))
            time.sleep(0.05)

            assert len(ws_manager._connections) == 1

    def test_disconnect_unregisters_client(self, ws_app) -> None:
        client, _, ws_manager, _ = ws_app

        with client.websocket_connect("/ws") as ws:
            ws.send_text(json.dumps({"type": "ping"}))
            time.sleep(0.05)
            assert len(ws_manager._connections) == 1

        # After context exits, connection should be cleaned up
        time.sleep(0.1)
        assert len(ws_manager._connections) == 0

    def test_event_loop_captured(self, ws_app) -> None:
        client, _, ws_manager, _ = ws_app

        with client.websocket_connect("/ws") as ws:
            ws.send_text(json.dumps({"type": "ping"}))
            time.sleep(0.05)
            assert ws_manager._loop is not None


# ── EventBus → WebSocket Broadcast ────────────────────────────────────────


class TestEventBroadcast:
    """Events emitted on EventBus arrive at connected WebSocket clients."""

    def test_transcript_deleted_event_broadcast(self, ws_app) -> None:
        """Fire transcript_deleted → verify it arrives at WS client."""
        client, coord, _, _ = ws_app

        with client.websocket_connect("/ws") as ws:
            # Must send a message first to ensure connection is registered
            ws.send_text(json.dumps({"type": "ping"}))
            time.sleep(0.1)

            # Emit event from EventBus (simulating a background thread event)
            coord.event_bus.emit("transcript_deleted", {"transcript_id": 42})
            time.sleep(0.1)

            msg = ws.receive_json(timeout=2)
            assert msg["type"] == "transcript_deleted"
            assert msg["data"]["transcript_id"] == 42

    def test_config_updated_event_broadcast(self, ws_app) -> None:
        client, coord, _, _ = ws_app

        with client.websocket_connect("/ws") as ws:
            ws.send_text(json.dumps({"type": "ping"}))
            time.sleep(0.1)

            coord.event_bus.emit("config_updated", {"section": "model", "model": "small-en"})
            time.sleep(0.1)

            msg = ws.receive_json(timeout=2)
            assert msg["type"] == "config_updated"
            assert msg["data"]["section"] == "model"

    def test_refinement_error_event_broadcast(self, ws_app) -> None:
        client, coord, _, _ = ws_app

        with client.websocket_connect("/ws") as ws:
            ws.send_text(json.dumps({"type": "ping"}))
            time.sleep(0.1)

            coord.event_bus.emit("refinement_error", {
                "transcript_id": 7,
                "message": "SLM not available",
            })
            time.sleep(0.1)

            msg = ws.receive_json(timeout=2)
            assert msg["type"] == "refinement_error"
            assert msg["data"]["message"] == "SLM not available"

    def test_multiple_events_arrive_in_order(self, ws_app) -> None:
        """Multiple events should arrive in emission order."""
        client, coord, _, _ = ws_app

        with client.websocket_connect("/ws") as ws:
            ws.send_text(json.dumps({"type": "ping"}))
            time.sleep(0.1)

            coord.event_bus.emit("recording_started", {"status": "recording"})
            time.sleep(0.05)
            coord.event_bus.emit("recording_stopped", {"status": "stopped"})
            time.sleep(0.1)

            msg1 = ws.receive_json(timeout=2)
            msg2 = ws.receive_json(timeout=2)

            assert msg1["type"] == "recording_started"
            assert msg2["type"] == "recording_stopped"


# ── WS Command → CommandBus Dispatch ──────────────────────────────────────


class TestWSCommandDispatch:
    """WebSocket commands are parsed and dispatched to CommandBus."""

    def test_toggle_recording_dispatches_intent(self, ws_app) -> None:
        """Sending toggle_recording via WS dispatches ToggleRecordingIntent."""
        client, coord, _, _ = ws_app

        # Track CommandBus dispatches
        dispatched = []
        original_dispatch = coord.command_bus.dispatch

        def tracking_dispatch(intent):
            dispatched.append(type(intent).__name__)
            return original_dispatch(intent)

        coord.command_bus.dispatch = tracking_dispatch

        with client.websocket_connect("/ws") as ws:
            ws.send_text(json.dumps({"type": "toggle_recording"}))
            time.sleep(0.2)

        assert "ToggleRecordingIntent" in dispatched

    def test_unknown_ws_command_no_crash(self, ws_app) -> None:
        """Unknown WS message types are logged, not crashed."""
        client, _, _, _ = ws_app

        with client.websocket_connect("/ws") as ws:
            ws.send_text(json.dumps({"type": "nonexistent_command"}))
            time.sleep(0.1)
            # No crash — connection stays open
            ws.send_text(json.dumps({"type": "ping"}))
            time.sleep(0.05)

    def test_malformed_json_no_crash(self, ws_app) -> None:
        """Invalid JSON doesn't crash the WS handler."""
        client, _, _, _ = ws_app

        with client.websocket_connect("/ws") as ws:
            ws.send_text("this is not json {{{")
            time.sleep(0.1)
            # Connection should survive
            ws.send_text(json.dumps({"type": "ping"}))
            time.sleep(0.05)


# ── ConnectionManager Unit Tests ──────────────────────────────────────────


class TestConnectionManager:
    """ConnectionManager thread-safety and broadcast behavior."""

    def test_no_connections_no_crash(self) -> None:
        """broadcast_threadsafe with no connections is a no-op."""
        mgr = ConnectionManager()
        # Should not crash
        mgr.broadcast_threadsafe("some_event", {"key": "value"})

    def test_no_loop_no_crash(self) -> None:
        """broadcast_threadsafe with no event loop is a no-op."""
        mgr = ConnectionManager()
        # Manually add a fake connection without a loop
        mgr._connections.add("fake_ws")  # type: ignore
        mgr.broadcast_threadsafe("event", {"data": 1})
        # Should silently return (no loop to schedule on)
