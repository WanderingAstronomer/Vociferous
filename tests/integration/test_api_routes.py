"""
API route integration tests.

Uses Litestar's TestClient with a real ApplicationCoordinator (real DB,
real buses) but no heavy services. Tests the full HTTP request→response
cycle including H-Pattern intent dispatch.

Marked as 'integration' since they exercise multiple layers together.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from litestar.testing import TestClient

from tests.conftest import EventCollector

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def api(coordinator, event_collector) -> Iterator[tuple]:
    """
    Litestar TestClient wired to a real coordinator.

    Builds the app without static files to avoid catch-all route conflicts.
    Yields (client, coordinator, event_collector).
    """
    from litestar import Litestar
    from litestar.config.cors import CORSConfig

    from src.api.app import ConnectionManager, _handle_ws_message, _wire_event_bridge
    from src.api.deps import set_coordinator
    from src.api.config import dispatch_intent, get_config, update_config
    from src.api.models import download_model, list_models
    from src.api.system import health
    from src.api.transcripts import (
        clear_all_transcripts,
        delete_transcript,
        get_transcript,
        list_transcripts,
        refine_transcript,
        search_transcripts,
    )

    ALL_EVENTS = [
        "recording_started",
        "recording_stopped",
        "transcript_deleted",
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
    event_collector.subscribe_all(coordinator.event_bus, ALL_EVENTS)

    set_coordinator(coordinator)
    ws_manager = ConnectionManager()
    _wire_event_bridge(coordinator, ws_manager)

    app = Litestar(
        route_handlers=[
            list_transcripts,
            get_transcript,
            delete_transcript,
            clear_all_transcripts,
            refine_transcript,
            search_transcripts,
            get_config,
            update_config,
            list_models,
            download_model,
            health,
            dispatch_intent,
        ],
        cors_config=CORSConfig(
            allow_origins=["http://localhost:5173"],
            allow_methods=["*"],
            allow_headers=["*"],
        ),
        debug=True,
    )

    with TestClient(app=app) as client:
        yield client, coordinator, event_collector

    set_coordinator(None)


# ── Health ────────────────────────────────────────────────────────────────


class TestHealthEndpoint:
    def test_health_returns_ok(self, api):
        client, coord, _ = api
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "version" in body
        assert body["transcripts"] == 1  # v9 seeds 1 protected prompt transcript

    def test_health_reflects_transcript_count(self, api):
        client, coord, _ = api
        coord.db.add_transcript(raw_text="one", duration_ms=100)
        coord.db.add_transcript(raw_text="two", duration_ms=200)

        resp = client.get("/api/health")
        assert resp.json()["transcripts"] == 3  # 2 added + 1 seeded


# ── Transcript CRUD ──────────────────────────────────────────────────────


class TestTranscriptRoutes:
    def test_list_empty(self, api):
        """Fresh DB has only the seeded system prompt transcript."""
        client, _, _ = api
        resp = client.get("/api/transcripts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1  # v9 seeds 1 protected prompt transcript
        assert len(data["items"]) == 1

    def test_list_returns_transcripts(self, api):
        client, coord, _ = api
        coord.db.add_transcript(raw_text="hello world", duration_ms=1000)
        coord.db.add_transcript(raw_text="second one", duration_ms=2000)

        resp = client.get("/api/transcripts")
        data = resp.json()
        assert len(data["items"]) == 3  # 2 added + 1 seeded
        assert data["total"] == 3
        assert all("id" in t and "raw_text" in t for t in data["items"])

    def test_list_with_limit(self, api):
        client, coord, _ = api
        for i in range(5):
            coord.db.add_transcript(raw_text=f"transcript {i}", duration_ms=100)

        resp = client.get("/api/transcripts", params={"limit": 3})
        data = resp.json()
        assert len(data["items"]) == 3
        assert data["total"] == 6  # 5 added + 1 seeded

    def test_get_transcript_by_id(self, api):
        client, coord, _ = api
        t = coord.db.add_transcript(raw_text="find me", duration_ms=500)

        resp = client.get(f"/api/transcripts/{t.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["raw_text"] == "find me"
        assert body["id"] == t.id
        assert "tags" in body  # Detail view includes tags

    def test_get_transcript_not_found(self, api):
        client, _, _ = api
        resp = client.get("/api/transcripts/99999")
        assert resp.status_code == 404

    def test_delete_transcript_via_api(self, api):
        """DELETE /api/transcripts/:id removes the row and emits transcript_deleted."""
        client, coord, events = api
        t = coord.db.add_transcript(raw_text="delete me", duration_ms=100)

        resp = client.delete(f"/api/transcripts/{t.id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        # Verify DB state
        assert coord.db.get_transcript(t.id) is None

        # Verify event emitted
        deleted = events.of_type("transcript_deleted")
        assert len(deleted) == 1
        assert deleted[0]["id"] == t.id

    def test_clear_all_transcripts(self, api):
        """DELETE /api/transcripts returns deleted count and clears non-protected records."""
        client, coord, events = api
        coord.db.add_transcript(raw_text="first", duration_ms=100)
        coord.db.add_transcript(raw_text="second", duration_ms=200)

        resp = client.delete("/api/transcripts")
        assert resp.status_code == 200
        data = resp.json()
        assert "deleted" in data
        assert data["deleted"] == 2  # only non-protected transcripts deleted
        assert coord.db.transcript_count() == 1  # protected prompt transcript survives

    def test_search_transcripts(self, api):
        client, coord, _ = api
        coord.db.add_transcript(raw_text="the quick brown fox", duration_ms=100)
        coord.db.add_transcript(raw_text="lazy dog sleeps", duration_ms=200)

        resp = client.get("/api/transcripts/search", params={"q": "fox"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert "fox" in data["items"][0]["raw_text"]

    def test_search_no_results(self, api):
        client, coord, _ = api
        coord.db.add_transcript(raw_text="something", duration_ms=100)

        resp = client.get("/api/transcripts/search", params={"q": "nonexistent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0


# ── Generic Intent Dispatch ──────────────────────────────────────────────


class TestIntentDispatch:
    def test_dispatch_unknown_intent(self, api):
        client, _, _ = api
        resp = client.post("/api/intents", json={"type": "nonexistent_intent"})
        assert resp.status_code == 400
        assert "Unknown intent" in resp.json()["error"]

    def test_dispatch_missing_type(self, api):
        client, _, _ = api
        resp = client.post("/api/intents", json={"foo": "bar"})
        assert resp.status_code == 400
        assert "Missing" in resp.json()["error"]


# ── Config ────────────────────────────────────────────────────────────────


class TestConfigRoutes:
    def test_get_config(self, api):
        client, _, _ = api
        resp = client.get("/api/config")
        assert resp.status_code == 200
        body = resp.json()
        # Should have top-level sections
        assert "model" in body
        assert "recording" in body
        assert "refinement" in body

    def test_update_config_emits_event(self, api):
        """PUT /api/config updates settings and emits config_updated."""
        client, coord, events = api

        resp = client.put(
            "/api/config",
            json={"recording": {"activation_key": "ctrl_left"}},
        )
        assert resp.status_code == 200

        # Verify event emitted
        updated = events.of_type("config_updated")
        assert len(updated) == 1
        assert updated[0]["recording"]["activation_key"] == "ctrl_left"

        # Verify coordinator's settings reference updated
        assert coord.settings.recording.activation_key == "ctrl_left"


# ── Refinement via API ────────────────────────────────────────────────────


class TestRefinementRoute:
    def test_refine_without_slm_returns_queued_then_error_event(self, api):
        """POST /api/transcripts/:id/refine dispatches intent, SLM error emitted."""
        client, coord, events = api
        t = coord.db.add_transcript(raw_text="refine me", duration_ms=100)

        resp = client.post(
            f"/api/transcripts/{t.id}/refine",
            json={"level": 2},
        )
        # API returns "queued" immediately (async pattern)
        assert resp.status_code == 201
        assert resp.json()["status"] == "queued"

        # But the handler emits an error because no SLM is loaded
        errors = events.of_type("refinement_error")
        assert len(errors) == 1
        assert "not configured" in errors[0]["message"].lower() or "not available" in errors[0]["message"].lower()
