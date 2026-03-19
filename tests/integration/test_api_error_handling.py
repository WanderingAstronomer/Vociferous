"""
API error handling and edge case tests.

Validates error responses for invalid requests, missing data, boundary
conditions, and failure modes across all API modules. Exercises both
HTTP error codes and the error payloads returned to the frontend.

Uses the same real-coordinator test harness as test_api_routes.py.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from litestar.testing import TestClient

from tests.conftest import EventCollector

# ── Fixtures (reuse the same pattern as test_api_routes) ──────────────────


ALL_ERROR_EVENTS = [
    "transcript_deleted",
    "refinement_started",
    "refinement_error",
    "config_updated",
    "tag_created",
    "tag_updated",
    "tag_deleted",
]


@pytest.fixture()
def api(coordinator, event_collector) -> Iterator[tuple]:
    """Litestar TestClient wired to a real coordinator."""
    from litestar import Litestar
    from litestar.config.cors import CORSConfig

    from src.api.app import ConnectionManager, _wire_event_bridge
    from src.api.deps import set_coordinator
    from src.api.config import dispatch_intent, get_config, update_config
    from src.api.models import download_model, list_models
    from src.api.system import health
    from src.api.transcripts import (
        delete_transcript,
        get_transcript,
        list_transcripts,
        refine_transcript,
        search_transcripts,
    )

    event_collector.subscribe_all(coordinator.event_bus, ALL_ERROR_EVENTS)
    set_coordinator(coordinator)
    ws_manager = ConnectionManager()
    _wire_event_bridge(coordinator, ws_manager)

    app = Litestar(
        route_handlers=[
            list_transcripts,
            get_transcript,
            delete_transcript,
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


# ── Intent Dispatch Error Paths ───────────────────────────────────────────


class TestIntentDispatchErrors:
    """Error handling for POST /api/intents."""

    def test_missing_type_field(self, api):
        """Omitting 'type' should return 400."""
        client, _, _ = api
        resp = client.post("/api/intents", json={"transcript_id": 1})
        assert resp.status_code == 400
        assert "Missing" in resp.json()["error"]

    def test_unknown_intent_type(self, api):
        """Unknown intent type string should return 400."""
        client, _, _ = api
        resp = client.post("/api/intents", json={"type": "launch_missile"})
        assert resp.status_code == 400
        assert "Unknown intent" in resp.json()["error"]

    def test_intent_with_nonsense_type_value(self, api):
        """Intent type that is an integer instead of string returns 400."""
        client, _, _ = api
        resp = client.post(
            "/api/intents",
            json={"type": 12345},
        )
        assert resp.status_code == 400

    def test_intent_with_extra_fields(self, api):
        """Extra fields on a frozen dataclass intent → TypeError → 400."""
        client, coord, _ = api
        t = coord.db.add_transcript(raw_text="extra fields test", duration_ms=100)

        resp = client.post(
            "/api/intents",
            json={
                "type": "delete_transcript",
                "transcript_id": t.id,
                "extra_nonsense": "should_be_ignored",
            },
        )
        # Dataclass intents reject unknown kwargs → TypeError → 400
        assert resp.status_code == 400

    def test_empty_json_body(self, api):
        """Empty JSON body should return 400."""
        client, _, _ = api
        resp = client.post("/api/intents", json={})
        assert resp.status_code == 400


# ── Transcript Error Paths ────────────────────────────────────────────────


class TestTranscriptErrors:
    """Error responses for transcript endpoints."""

    def test_get_nonexistent_transcript(self, api):
        """GET a transcript that doesn't exist → 404."""
        client, _, _ = api
        resp = client.get("/api/transcripts/9999999")
        assert resp.status_code == 404
        assert "Not found" in resp.json()["error"]

    def test_get_transcript_zero_id(self, api):
        """GET transcript with id=0 → 404 (no transcript at id 0)."""
        client, _, _ = api
        resp = client.get("/api/transcripts/0")
        assert resp.status_code == 404

    def test_get_transcript_negative_id(self, api):
        """GET transcript with negative id → 404."""
        client, _, _ = api
        resp = client.get("/api/transcripts/-1")
        assert resp.status_code == 404

    def test_delete_nonexistent_transcript(self, api):
        """DELETE a non-existent transcript returns 404."""
        client, coord, events = api
        resp = client.delete("/api/transcripts/99999")
        assert resp.status_code == 404
        assert "error" in resp.json()
        assert len(events.of_type("transcript_deleted")) == 0

    def test_search_empty_query(self, api):
        """Search with empty query should return results (match all)."""
        client, coord, _ = api
        coord.db.add_transcript(raw_text="data here", duration_ms=100)

        resp = client.get("/api/transcripts/search", params={"q": ""})
        assert resp.status_code == 200
        # Behavior depends on DB implementation — either all or none

    def test_search_special_characters(self, api):
        """Search with SQL-like special chars should not crash."""
        client, coord, _ = api
        coord.db.add_transcript(raw_text="safe text", duration_ms=100)

        for query in ["%", "_", "'", "'; DROP TABLE--", "😀"]:
            resp = client.get("/api/transcripts/search", params={"q": query})
            assert resp.status_code == 200  # No crash, even if no results

    def test_list_transcripts_with_zero_limit(self, api):
        """Limit=0 should return empty or handle gracefully."""
        client, coord, _ = api
        # v9 migration seeds 1 protected transcript; add_transcript adds 1 more
        baseline = len(coord.db.recent(limit=100)[0])
        coord.db.add_transcript(raw_text="limited", duration_ms=100)

        resp = client.get("/api/transcripts", params={"limit": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == baseline + 1

    def test_list_transcripts_large_limit(self, api):
        """Very large limit should not crash."""
        client, _, _ = api
        resp = client.get("/api/transcripts", params={"limit": 999999})
        assert resp.status_code == 200


# ── Config Error Paths ────────────────────────────────────────────────────


class TestConfigErrors:
    """Error responses for config endpoints."""

    def test_update_config_empty_body(self, api):
        """PUT /api/config with empty dict should succeed (no changes)."""
        client, _, _ = api
        resp = client.put("/api/config", json={})
        assert resp.status_code == 200

    def test_update_config_unknown_key(self, api):
        """PUT /api/config with unknown top-level key → 200 (silently dropped)."""
        client, _, _ = api
        resp = client.put("/api/config", json={"nonexistent_section": True})
        # Settings model uses extra="ignore" — unknown keys are silently dropped
        assert resp.status_code == 200

    def test_get_config_returns_all_sections(self, api):
        """GET /api/config must include model, recording, refinement."""
        client, _, _ = api
        resp = client.get("/api/config")
        body = resp.json()
        assert "model" in body
        assert "recording" in body
        assert "refinement" in body


# ── Model Download Error Paths ────────────────────────────────────────────


class TestModelDownloadErrors:
    """Error responses for model download endpoint."""

    def test_download_missing_model_id(self, api):
        """POST /api/models/download without model_id → 400."""
        client, _, _ = api
        resp = client.post("/api/models/download", json={"model_type": "asr"})
        assert resp.status_code == 400
        assert "Missing model_id" in resp.json()["error"]

    def test_download_unknown_model(self, api):
        """POST /api/models/download with invalid model_id → 404."""
        client, _, _ = api
        resp = client.post(
            "/api/models/download",
            json={"model_type": "asr", "model_id": "nonexistent-model-v99"},
        )
        assert resp.status_code == 404
        assert "Unknown model" in resp.json()["error"]

    def test_download_unknown_slm_model(self, api):
        """SLM model type with unknown ID → 404."""
        client, _, _ = api
        resp = client.post(
            "/api/models/download",
            json={"model_type": "slm", "model_id": "fake-slm"},
        )
        assert resp.status_code == 404


# ── Health Edge Cases ─────────────────────────────────────────────────────


class TestHealthEdgeCases:
    """Edge cases for the health endpoint."""

    def test_health_with_no_db(self, api):
        """Health with db=None should return 0 transcripts."""
        client, coord, _ = api
        coord.db = None

        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["transcripts"] == 0

    def test_health_version_present(self, api):
        """Health response must contain a version string."""
        client, _, _ = api
        resp = client.get("/api/health")
        assert "version" in resp.json()
        assert isinstance(resp.json()["version"], str)


# ── Transcript DB-Unavailable Paths ───────────────────────────────────────


class TestDatabaseUnavailable:
    """Behavior when the database is None (not yet initialized)."""

    def test_list_transcripts_database_none(self, api):
        """List returns empty when db is None."""
        client, coord, _ = api
        coord.db = None
        resp = client.get("/api/transcripts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_get_transcript_database_none(self, api):
        """Get returns 503 when db is None."""
        client, coord, _ = api
        coord.db = None
        resp = client.get("/api/transcripts/1")
        assert resp.status_code == 503

    def test_search_database_none(self, api):
        """Search returns empty envelope when db is None."""
        client, coord, _ = api
        coord.db = None
        resp = client.get("/api/transcripts/search", params={"q": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
