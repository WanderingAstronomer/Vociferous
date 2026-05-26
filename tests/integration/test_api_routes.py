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
from unittest.mock import MagicMock, patch

import pytest
from litestar.testing import TestClient

from src.core.cuda_runtime import CudaRuntimeStatus
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
    from src.api.config import (
        clear_default_refinement_prompt,
        dispatch_intent,
        get_config,
        get_insight,
        refresh_insight,
        set_default_refinement_prompt,
        update_config,
    )
    from src.api.deps import set_coordinator
    from src.api.models import download_model, list_models
    from src.api.refinement_providers import (
        delete_refinement_provider_api_key,
        get_refinement_provider_api_key_status,
        list_refinement_provider_models,
        save_refinement_provider_api_key,
        test_refinement_provider,
    )
    from src.api.system import health, import_audio_file
    from src.api.transcription_providers import (
        delete_transcription_provider_api_key,
        get_transcription_provider_api_key_status,
        list_transcription_provider_models,
        save_transcription_provider_api_key,
        test_transcription_provider,
    )
    from src.api.transcripts import (
        batch_tag_toggle,
        delete_recovered_recording,
        get_transcript,
        list_recoverable_recordings,
        list_transcripts,
        refine_transcript,
        rename_transcript,
        search_transcripts,
        transcribe_recovered_recording,
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
        "audio_recovery_updated",
    ]
    event_collector.subscribe_all(coordinator.event_bus, ALL_EVENTS)

    set_coordinator(coordinator)
    ws_manager = ConnectionManager()
    _wire_event_bridge(coordinator, ws_manager)

    app = Litestar(
        route_handlers=[
            list_transcripts,
            get_transcript,
            refine_transcript,
            search_transcripts,
            batch_tag_toggle,
            rename_transcript,
            list_recoverable_recordings,
            transcribe_recovered_recording,
            delete_recovered_recording,
            get_config,
            get_insight,
            update_config,
            set_default_refinement_prompt,
            clear_default_refinement_prompt,
            refresh_insight,
            list_models,
            download_model,
            health,
            import_audio_file,
            dispatch_intent,
            get_refinement_provider_api_key_status,
            save_refinement_provider_api_key,
            delete_refinement_provider_api_key,
            get_transcription_provider_api_key_status,
            save_transcription_provider_api_key,
            delete_transcription_provider_api_key,
            list_refinement_provider_models,
            test_refinement_provider,
            list_transcription_provider_models,
            test_transcription_provider,
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
        assert body["transcripts"] == 0

    def test_health_reflects_transcript_count(self, api):
        client, coord, _ = api
        coord.db.add_transcript(raw_text="one", duration_ms=100)
        coord.db.add_transcript(raw_text="two", duration_ms=200)

        resp = client.get("/api/health")
        assert resp.json()["transcripts"] == 2

    def test_health_reports_driver_without_cuda_runtime(self, api):
        client, _, _ = api
        with patch(
            "src.api.system.detect_cuda_runtime",
            return_value=CudaRuntimeStatus(
                driver_detected=True,
                cuda_available=False,
                cuda_device_count=0,
                gpu_name="GeForce RTX 3080",
                detail="CTranslate2 detected 0 CUDA devices; NVIDIA driver is present but the CUDA runtime is not usable",
                vram_total_mb=10240,
                vram_used_mb=512,
                vram_free_mb=9728,
            ),
        ):
            from src.api.system import _detect_gpu_status

            _detect_gpu_status.cache_clear()
            resp = client.get("/api/health")
            body = resp.json()
            assert body["gpu"]["driver_detected"] is True
            assert body["gpu"]["cuda_available"] is False
            assert body["gpu"]["cuda_device_count"] == 0
            assert body["gpu"]["gpu_name"] == "GeForce RTX 3080"
            assert "runtime is not usable" in body["gpu"]["detail"]


# ── Transcript CRUD ──────────────────────────────────────────────────────


class TestTranscriptRoutes:
    def test_list_empty(self, api):
        """Fresh DB has no user transcript data in the default list."""
        client, _, _ = api
        resp = client.get("/api/transcripts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_prompt_tag_filter_lists_shipped_prompt_records(self, api):
        client, coord, _ = api
        prompt_tag = next(tag for tag in coord.db.get_tags() if tag.name == "Prompt")

        resp = client.get("/api/transcripts", params={"tag_ids": str(prompt_tag.id)})

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        assert {item["display_name"] for item in data["items"]} == {
            "Clean Verbatim (Fast)",
            "Clean Verbatim (Deep)",
            "Markdown Rewrite (Fast)",
            "Markdown Rewrite (Deep)",
        }
        assert all(item["created_at"] == "" for item in data["items"])
        assert all(item["include_in_analytics"] is False for item in data["items"])

    def test_list_supports_not_tag_filter_mode(self, api):
        client, coord, _ = api
        work_tag = coord.db.add_tag("Work")
        personal_tag = coord.db.add_tag("Personal")
        assert work_tag.id is not None
        assert personal_tag.id is not None
        coord.db.add_transcript(raw_text="work item", tag_ids=[work_tag.id])
        coord.db.add_transcript(raw_text="personal item", tag_ids=[personal_tag.id])
        coord.db.add_transcript(raw_text="untagged item")

        resp = client.get("/api/transcripts", params={"tag_ids": str(work_tag.id), "tag_mode": "not"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert {item["raw_text"] for item in data["items"]} == {"personal item", "untagged item"}

    def test_list_returns_transcripts(self, api):
        client, coord, _ = api
        coord.db.add_transcript(raw_text="hello world", duration_ms=1000)
        coord.db.add_transcript(raw_text="second one", duration_ms=2000)

        resp = client.get("/api/transcripts")
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 2
        assert all("id" in t and "raw_text" in t for t in data["items"])

    def test_recoverable_audio_routes(self, api, tmp_path: Path):
        client, coord, _ = api
        audio_path = tmp_path / "recovered.vocaud"
        audio_path.write_bytes(b"VOCAUD1\n")
        coord.db.create_recording_session(
            recording_id="rec_api",
            audio_path=audio_path,
            sample_rate=16000,
        )
        coord.db.mark_recording_status("rec_api", "recovered", finalized=True)

        listing = client.get("/api/audio/recoverable")
        assert listing.status_code == 200
        body = listing.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == "rec_api"

        dispatched = []
        coord.command_bus.dispatch = lambda intent: dispatched.append(intent) or True

        queued = client.post("/api/audio/recoverable/rec_api/transcribe")
        assert queued.status_code == 200
        assert queued.json()["status"] == "queued"

        deleted = client.delete("/api/audio/recoverable/rec_api")
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True
        assert [type(intent).__name__ for intent in dispatched] == [
            "TranscribeRecoveredRecordingIntent",
            "DeleteRecoveredRecordingIntent",
        ]

    def test_list_with_limit(self, api):
        client, coord, _ = api
        for i in range(5):
            coord.db.add_transcript(raw_text=f"transcript {i}", duration_ms=100)

        resp = client.get("/api/transcripts", params={"limit": 3})
        data = resp.json()
        assert len(data["items"]) == 3
        assert data["total"] == 5


class TestImportAudioRoute:
    def test_import_audio_queues_intent_with_temp_file(self, api):
        client, coord, _ = api
        dispatched = []
        coord.command_bus.dispatch = lambda intent: dispatched.append(intent) or True

        resp = client.post(
            "/api/import-audio",
            files={"data": ("sample.wav", b"RIFFfake-wave-data", "audio/wav")},
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "importing"
        assert body["dispatched"] is True
        assert len(dispatched) == 1
        intent = dispatched[0]
        assert type(intent).__name__ == "ImportAudioFileIntent"
        assert intent.cleanup_source is True
        temp_path = Path(intent.file_path)
        assert temp_path.exists()
        assert temp_path.read_bytes() == b"RIFFfake-wave-data"
        temp_path.unlink(missing_ok=True)

    def test_import_audio_rejects_oversized_uploads(self, api, monkeypatch):
        client, _, _ = api
        from src.api import system

        monkeypatch.setattr(system, "_MAX_IMPORT_AUDIO_BYTES", 8)

        resp = client.post(
            "/api/import-audio",
            files={"data": ("huge.wav", b"0123456789", "audio/wav")},
        )

        assert resp.status_code == 413
        assert "too large" in resp.json()["error"].lower()

    def test_import_audio_cleans_temp_file_when_dispatch_fails(self, api):
        client, coord, _ = api
        dispatched = []
        coord.command_bus.dispatch = lambda intent: dispatched.append(intent) or False

        resp = client.post(
            "/api/import-audio",
            files={"data": ("sample.wav", b"RIFFdispatch-failure", "audio/wav")},
        )

        assert resp.status_code == 503
        assert resp.json()["error"] == "Failed to queue audio import"
        assert len(dispatched) == 1
        assert not Path(dispatched[0].file_path).exists()

    def test_append_intent_preserves_source_but_keeps_default_list_count_stable(self, api):
        client, coord, _ = api
        root = coord.db.add_transcript(raw_text="Root text", duration_ms=1000)
        source = coord.db.add_transcript(raw_text="Source text", duration_ms=500)

        resp = client.post(
            "/api/intents",
            json={
                "type": "append_to_transcript",
                "transcript_id": root.id,
                "source_transcript_id": source.id,
            },
        )

        assert resp.status_code == 200
        assert resp.json()["dispatched"] is True

        listing = client.get("/api/transcripts").json()
        assert listing["total"] == 1
        assert source.id not in {item["id"] for item in listing["items"]}

        source_detail = client.get(f"/api/transcripts/{source.id}")
        assert source_detail.status_code == 200
        assert source_detail.json()["raw_text"] == "Source text"

        health = client.get("/api/health").json()
        assert health["transcripts"] == 1

    def test_list_rejects_invalid_tag_ids(self, api):
        client, _, _ = api

        resp = client.get("/api/transcripts", params={"tag_ids": "1,abc,3"})
        assert resp.status_code == 400
        message = resp.json().get("error") or resp.json().get("detail", "")
        assert "tag_ids" in message

    def test_list_rejects_invalid_tag_mode(self, api):
        client, _, _ = api

        resp = client.get("/api/transcripts", params={"tag_ids": "1", "tag_mode": "nor"})
        assert resp.status_code == 400
        message = resp.json().get("error") or resp.json().get("detail", "")
        assert "tag_mode" in message

    def test_list_rejects_negative_offset(self, api):
        client, _, _ = api

        resp = client.get("/api/transcripts", params={"offset": -1})
        assert resp.status_code == 400
        message = resp.json().get("error") or resp.json().get("detail", "")
        assert "offset" in message

    def test_get_transcript_by_id(self, api):
        client, coord, _ = api
        t = coord.db.add_transcript(raw_text="find me", duration_ms=500)

        resp = client.get(f"/api/transcripts/{t.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["raw_text"] == "find me"
        assert body["id"] == t.id
        assert "tags" in body  # Detail view includes tags

    def test_get_transcript_exposes_processing_provenance(self, api):
        client, coord, _ = api
        transcript = coord.db.add_transcript(
            raw_text="original text",
            duration_ms=20_000,
            transcription_time_ms=5_000,
            transcription_provider="groq",
            transcription_model_id="whisper-large-v3-turbo",
            transcription_resolved_device="external_api",
            transcription_compute_type="api",
            transcription_cpu_threads=0,
            transcription_prompt_text="Use medical terminology.",
            transcription_prompt_chars=24,
            transcription_prompt_words=3,
        )
        coord.db.update_retranscription_processing_context(
            transcript.id,
            normalized_text="retranscribed text",
            retranscription_time_ms=10_000,
            retranscription_provider="local_faster_whisper",
            retranscription_model_id="large-v3",
            retranscription_resolved_device="cuda",
            retranscription_compute_type="float16",
            retranscription_cpu_threads=6,
            retranscription_prompt_text="Prefer names.",
            retranscription_prompt_chars=13,
            retranscription_prompt_words=2,
        )
        coord.db.update_refinement_processing_context(
            transcript.id,
            refinement_time_ms=4_000,
            refinement_provider="lm_studio",
            refinement_model_id="qwen3.5-27b",
            refinement_resolved_device="cuda",
            refinement_compute_type="float16",
            refinement_cpu_threads=8,
            refinement_gpu_layers=99,
            refinement_use_thinking=False,
            refinement_prompt_text="Fix grammar.",
            refinement_prompt_chars=12,
            refinement_prompt_words=2,
            refinement_prompt_tokens=80,
            refinement_completion_tokens=40,
            refinement_total_tokens=120,
        )

        resp = client.get(f"/api/transcripts/{transcript.id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["transcription_provider"] == "groq"
        assert body["transcription_model_id"] == "whisper-large-v3-turbo"
        assert body["transcription_resolved_device"] == "external_api"
        assert body["transcription_prompt_text"] == "Use medical terminology."
        assert body["retranscription_count"] == 1
        assert body["last_retranscription_provider"] == "local_faster_whisper"
        assert body["last_retranscription_model_id"] == "large-v3"
        assert body["last_retranscription_resolved_device"] == "cuda"
        assert body["last_retranscription_prompt_text"] == "Prefer names."
        assert body["refinement_provider"] == "lm_studio"
        assert body["refinement_model_id"] == "qwen3.5-27b"
        assert body["refinement_resolved_device"] == "cuda"
        assert body["refinement_gpu_layers"] == 99
        assert body["refinement_use_thinking"] is False
        assert body["refinement_prompt_text"] == "Fix grammar."
        assert body["refinement_prompt_tokens"] == 80
        assert body["refinement_completion_tokens"] == 40
        assert body["refinement_total_tokens"] == 120

    def test_get_transcript_not_found(self, api):
        client, _, _ = api
        resp = client.get("/api/transcripts/99999")
        assert resp.status_code == 404

    def test_delete_transcript_via_intent_api(self, api):
        """POST /api/intents delete_transcript removes the row and emits transcript_deleted."""
        client, coord, events = api
        t = coord.db.add_transcript(raw_text="delete me", duration_ms=100)

        resp = client.post("/api/intents", json={"type": "delete_transcript", "transcript_id": t.id})
        assert resp.status_code == 200
        assert resp.json()["dispatched"] is True
        assert resp.json()["deleted"] is True

        # Verify DB state
        assert coord.db.get_transcript(t.id) is None

        # Verify event emitted
        deleted = events.of_type("transcript_deleted")
        assert len(deleted) == 1
        assert deleted[0]["id"] == t.id

    def test_clear_all_transcripts_via_intent_api(self, api):
        """POST /api/intents clear_all_transcripts returns deleted count."""
        client, coord, events = api
        coord.db.add_transcript(raw_text="first", duration_ms=100)
        coord.db.add_transcript(raw_text="second", duration_ms=200)

        resp = client.post("/api/intents", json={"type": "clear_all_transcripts"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["dispatched"] is True
        assert "deleted" in data
        assert data["deleted"] == 2  # only non-protected transcripts deleted
        assert coord.db.transcript_count() == 0

    def test_delete_default_prompt_transcript_clears_setting(self, api):
        client, coord, events = api
        prompt_tag = next(tag for tag in coord.db.get_tags() if tag.name == "Prompt")
        prompt = coord.db.add_transcript(raw_text="Always be concise.", duration_ms=100)
        coord.db.assign_tags(prompt.id, [prompt_tag.id])
        client.put("/api/config/refinement/default-prompt", json={"transcript_id": prompt.id})

        resp = client.post("/api/intents", json={"type": "delete_transcript", "transcript_id": prompt.id})

        assert resp.status_code == 200
        assert coord.settings.refinement.default_prompt_transcript_id is None
        updated = events.of_type("config_updated")
        assert updated[-1]["refinement"]["default_prompt_transcript_id"] is None

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

    def test_search_rejects_invalid_limit(self, api):
        client, _, _ = api

        resp = client.get("/api/transcripts/search", params={"q": "hello", "limit": -1})
        assert resp.status_code == 400
        message = resp.json().get("error") or resp.json().get("detail", "")
        assert "limit" in message

    def test_batch_tag_toggle_rejects_non_boolean_add(self, api):
        client, coord, _ = api
        t = coord.db.add_transcript(raw_text="tag me", duration_ms=100)
        tag = coord.db.add_tag("sample")

        resp = client.post(
            "/api/transcripts/batch-tag-toggle",
            json={"transcript_ids": [t.id], "tag_id": tag.id, "add": "false"},
        )
        assert resp.status_code == 400
        assert "boolean" in resp.json()["error"]

    def test_batch_tag_toggle_removing_prompt_from_default_clears_setting(self, api):
        client, coord, events = api
        prompt_tag = next(tag for tag in coord.db.get_tags() if tag.name == "Prompt")
        prompt = coord.db.add_transcript(raw_text="Preserve domain terminology.", duration_ms=100)
        coord.db.assign_tags(prompt.id, [prompt_tag.id])
        client.put("/api/config/refinement/default-prompt", json={"transcript_id": prompt.id})

        resp = client.post(
            "/api/transcripts/batch-tag-toggle",
            json={"transcript_ids": [prompt.id], "tag_id": prompt_tag.id, "add": False},
        )

        assert resp.status_code == 201
        assert coord.settings.refinement.default_prompt_transcript_id is None
        updated = events.of_type("config_updated")
        assert updated[-1]["refinement"]["default_prompt_transcript_id"] is None

    def test_rename_transcript_rejects_non_string_title(self, api):
        client, coord, _ = api
        t = coord.db.add_transcript(raw_text="rename me", duration_ms=100)

        resp = client.post(f"/api/transcripts/{t.id}/rename", json={"title": 123})
        assert resp.status_code == 400
        assert "string" in resp.json()["error"].lower()

    def test_rename_transcript_not_found(self, api):
        client, _, _ = api

        resp = client.post("/api/transcripts/99999/rename", json={"title": "New title"})
        assert resp.status_code == 404


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

    def test_typing_wpm_update_marks_insight_dirty(self, api):
        client, coord, _ = api
        coord.insight_manager = MagicMock()

        resp = client.put("/api/config", json={"user": {"typing_wpm": 95}})

        assert resp.status_code == 200
        coord.insight_manager.mark_dirty.assert_called_once_with("typing_wpm_changed")

    def test_set_default_refinement_prompt_emits_event(self, api):
        client, coord, events = api
        prompt_tag = next(tag for tag in coord.db.get_tags() if tag.name == "Prompt")
        prompt = coord.db.add_transcript(raw_text="Fix grammar only.", duration_ms=100)
        coord.db.assign_tags(prompt.id, [prompt_tag.id])

        resp = client.put("/api/config/refinement/default-prompt", json={"transcript_id": prompt.id})

        assert resp.status_code == 200
        assert coord.settings.refinement.default_prompt_transcript_id == prompt.id
        updated = events.of_type("config_updated")
        assert updated[-1]["refinement"]["default_prompt_transcript_id"] == prompt.id

    def test_clear_default_refinement_prompt_emits_event(self, api):
        client, coord, events = api
        prompt_tag = next(tag for tag in coord.db.get_tags() if tag.name == "Prompt")
        prompt = coord.db.add_transcript(raw_text="Keep the tone neutral.", duration_ms=100)
        coord.db.assign_tags(prompt.id, [prompt_tag.id])
        client.put("/api/config/refinement/default-prompt", json={"transcript_id": prompt.id})

        resp = client.delete("/api/config/refinement/default-prompt")

        assert resp.status_code == 200
        assert coord.settings.refinement.default_prompt_transcript_id is None
        updated = events.of_type("config_updated")
        assert updated[-1]["refinement"]["default_prompt_transcript_id"] is None

    def test_get_insight_returns_structured_payload(self, api):
        client, coord, _ = api
        coord.insight_manager = MagicMock()
        coord.insight_manager.cached_payload = {
            "text": "Daily.\n\nLifetime.",
            "daily_text": "Daily.",
            "lifetime_text": "Lifetime.",
            "generated_at": 123.0,
            "generated_for_date": "2026-05-24",
            "stale": False,
            "dirty_reasons": [],
        }

        resp = client.get("/api/insight")

        assert resp.status_code == 200
        assert resp.json()["daily_text"] == "Daily."
        assert resp.json()["lifetime_text"] == "Lifetime."

    def test_refresh_insight_dispatches_manual_refresh(self, api):
        client, coord, _ = api
        coord.insight_manager = MagicMock()
        coord.insight_manager.request_refresh.return_value = {
            "text": "",
            "daily_text": "",
            "lifetime_text": "",
            "generated_at": 0.0,
            "generated_for_date": "",
            "stale": True,
            "dirty_reasons": ["manual_refresh"],
        }

        resp = client.post("/api/insight/refresh")

        assert resp.status_code == 201
        assert resp.json()["dirty_reasons"] == ["manual_refresh"]
        coord.insight_manager.request_refresh.assert_called_once_with()


# ── Refinement Provider Secrets ───────────────────────────────────────────


class TestRefinementProviderSecretRoutes:
    def test_provider_model_and_connection_routes_use_current_settings(self, api, monkeypatch):
        from src.api import refinement_providers

        client, _, _ = api

        monkeypatch.setattr(
            refinement_providers,
            "list_external_provider_models",
            lambda _settings, provider_id: [{"id": f"{provider_id}-model", "object": "model"}],
        )
        monkeypatch.setattr(
            refinement_providers,
            "test_external_provider",
            lambda _settings, provider_id: {"ok": True, "provider": provider_id},
        )

        models = client.get("/api/refinement/providers/lm_studio/models")
        assert models.status_code == 200
        assert models.json() == {
            "provider": "lm_studio",
            "models": [{"id": "lm_studio-model", "object": "model"}],
        }

        result = client.post("/api/refinement/providers/lm_studio/test", json={"model_id": "draft-model"})
        assert result.status_code == 200
        assert result.json() == {"ok": True, "provider": "lm_studio"}

    def test_provider_api_key_round_trip_never_exposes_secret(self, api, monkeypatch):
        from src.api import refinement_providers

        client, _, _ = api
        stored: dict[str, str] = {}

        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.setattr(refinement_providers, "get_secret_backend", lambda: "test_secret")
        monkeypatch.setattr(refinement_providers, "get_provider_api_key", lambda provider_id: stored.get(provider_id))
        monkeypatch.setattr(
            refinement_providers,
            "store_provider_api_key",
            lambda provider_id, api_key: stored.__setitem__(provider_id, api_key),
        )
        monkeypatch.setattr(
            refinement_providers,
            "delete_provider_api_key",
            lambda provider_id: stored.pop(provider_id, None) is not None,
        )

        status = client.get("/api/refinement/providers/groq/api-key")
        assert status.status_code == 200
        assert status.json()["source"] == "none"

        saved = client.put(
            "/api/refinement/providers/groq/api-key", json={"api_key": "gsk_test_secret_123456789012345678901234567890"}
        )
        assert saved.status_code == 200
        assert saved.json() == {"provider": "groq", "stored": True, "backend": "test_secret"}
        assert "gsk_test_secret_123456789012345678901234567890" not in saved.text

        status = client.get("/api/refinement/providers/groq/api-key")
        assert status.status_code == 200
        assert status.json()["has_stored_key"] is True
        assert status.json()["has_stored_key_valid"] is True
        assert status.json()["source"] == "stored"
        assert status.json()["source_valid"] is True
        assert "gsk_test_secret_123456789012345678901234567890" not in status.text

        deleted = client.delete("/api/refinement/providers/groq/api-key")
        assert deleted.status_code == 200
        assert deleted.json() == {"provider": "groq", "deleted": True, "backend": "test_secret"}

        status = client.get("/api/refinement/providers/groq/api-key")
        assert status.status_code == 200
        assert status.json()["source"] == "none"

    def test_transcription_provider_model_and_connection_routes_use_current_settings(self, api, monkeypatch):
        from src.api import transcription_providers

        client, _, _ = api

        monkeypatch.setattr(
            transcription_providers,
            "list_external_transcription_provider_models",
            lambda _settings, provider_id: [{"id": f"{provider_id}-whisper", "object": "model"}],
        )
        monkeypatch.setattr(
            transcription_providers,
            "test_external_transcription_provider",
            lambda _settings, provider_id: {"ok": True, "provider": provider_id},
        )

        models = client.get("/api/transcription/providers/groq/models")
        assert models.status_code == 200
        assert models.json() == {
            "provider": "groq",
            "models": [{"id": "groq-whisper", "object": "model"}],
        }

        result = client.post("/api/transcription/providers/groq/test", json={"model_id": "draft-whisper"})
        assert result.status_code == 200
        assert result.json() == {"ok": True, "provider": "groq"}

    def test_transcription_provider_api_key_status_uses_transcription_env_setting(self, api, monkeypatch):
        from src.api import transcription_providers
        from src.core.settings import VociferousSettings

        client, coord, _ = api
        merged = coord.settings.model_dump()
        merged["model"]["groq"]["api_key_env"] = "ASR_GROQ_API_KEY"
        merged["refinement"]["groq"]["api_key_env"] = "REFINEMENT_GROQ_API_KEY"
        coord.settings = VociferousSettings(**merged)

        monkeypatch.setenv("ASR_GROQ_API_KEY", "gsk_test_secret_123456789012345678901234567890")
        monkeypatch.delenv("REFINEMENT_GROQ_API_KEY", raising=False)
        monkeypatch.setattr(transcription_providers, "get_secret_backend", lambda: "test_secret")
        monkeypatch.setattr(transcription_providers, "get_provider_api_key", lambda _provider_id: None)

        status = client.get("/api/transcription/providers/groq/api-key")

        assert status.status_code == 200
        assert status.json()["api_key_env"] == "ASR_GROQ_API_KEY"
        assert status.json()["source"] == "environment"
        assert status.json()["source_valid"] is True
        assert "gsk_test_secret_123456789012345678901234567890" not in status.text

    def test_transcription_provider_api_key_round_trip_never_exposes_secret(self, api, monkeypatch):
        from src.api import transcription_providers

        client, _, _ = api
        stored: dict[str, str] = {}

        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.setattr(transcription_providers, "get_secret_backend", lambda: "test_secret")
        monkeypatch.setattr(transcription_providers, "get_provider_api_key", lambda provider_id: stored.get(provider_id))
        monkeypatch.setattr(
            transcription_providers,
            "store_provider_api_key",
            lambda provider_id, api_key: stored.__setitem__(provider_id, api_key),
        )
        monkeypatch.setattr(
            transcription_providers,
            "delete_provider_api_key",
            lambda provider_id: stored.pop(provider_id, None) is not None,
        )

        saved = client.put(
            "/api/transcription/providers/groq/api-key",
            json={"api_key": "gsk_test_secret_123456789012345678901234567890"},
        )
        assert saved.status_code == 200
        assert saved.json() == {"provider": "groq", "stored": True, "backend": "test_secret"}
        assert "gsk_test_secret_123456789012345678901234567890" not in saved.text

        status = client.get("/api/transcription/providers/groq/api-key")
        assert status.status_code == 200
        assert status.json()["has_stored_key"] is True
        assert status.json()["source"] == "stored"
        assert status.json()["source_valid"] is True
        assert "gsk_test_secret_123456789012345678901234567890" not in status.text

        deleted = client.delete("/api/transcription/providers/groq/api-key")
        assert deleted.status_code == 200
        assert deleted.json() == {"provider": "groq", "deleted": True, "backend": "test_secret"}

    def test_lm_studio_is_not_a_transcription_provider(self, api):
        client, _, _ = api

        models = client.get("/api/transcription/providers/lm_studio/models")
        assert models.status_code == 400

        result = client.post("/api/transcription/providers/lm_studio/test", json={"model_id": "draft-whisper"})
        assert result.status_code == 400


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
