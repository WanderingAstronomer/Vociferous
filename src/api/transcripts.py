"""
Transcript API routes.

Handles transcript listing, detail, deletion, search, and refinement.
"""

from __future__ import annotations

import logging

from litestar import Response, delete, get, post

from src.api.deps import get_coordinator

logger = logging.getLogger(__name__)


@get("/api/transcripts")
async def list_transcripts(limit: int = 50, project_id: int | None = None) -> list[dict]:
    coordinator = get_coordinator()
    if coordinator.db is None:
        return []
    transcripts = coordinator.db.recent(limit=limit, project_id=project_id)
    return [transcript_to_dict(t) for t in transcripts]


@get("/api/transcripts/{transcript_id:int}")
async def get_transcript(transcript_id: int) -> Response:
    coordinator = get_coordinator()
    if coordinator.db is None:
        return Response(content={"error": "Database not available"}, status_code=503)
    t = coordinator.db.get_transcript(transcript_id)
    if t is None:
        return Response(content={"error": "Not found"}, status_code=404)
    return Response(content=transcript_to_dict(t, include_variants=True))


@delete("/api/transcripts/{transcript_id:int}", status_code=200)
async def delete_transcript(transcript_id: int) -> Response:
    """Delete a transcript via CommandBus intent."""
    coordinator = get_coordinator()
    from src.core.intents.definitions import DeleteTranscriptIntent

    intent = DeleteTranscriptIntent(transcript_id=transcript_id)
    success = coordinator.command_bus.dispatch(intent)
    if not success:
        return Response(content={"error": "Delete failed"}, status_code=500)
    return Response(content={"deleted": True})


@delete("/api/transcripts", status_code=200)
async def clear_all_transcripts() -> Response:
    """Delete all transcripts via CommandBus intent."""
    from src.core.intents.definitions import ClearTranscriptsIntent

    coordinator = get_coordinator()
    intent = ClearTranscriptsIntent()
    success = coordinator.command_bus.dispatch(intent)
    if not success:
        return Response(content={"error": "Clear failed"}, status_code=500)
    # Since dispatch is async in effect (handled synchronously but db is fast),
    # we can assume it worked if success is True.
    # Ideally we'd return the deleted count, but intents don't return values.
    # The frontend should listen for 'transcripts_cleared' event.
    return Response(content={"status": "cleared"})


@get("/api/transcripts/search")
async def search_transcripts(q: str, limit: int = 50) -> list[dict]:
    coordinator = get_coordinator()
    if coordinator.db is None:
        return []
    results = coordinator.db.search(q, limit=limit)
    return [transcript_to_dict(t) for t in results]


@post("/api/transcripts/{transcript_id:int}/refine")
async def refine_transcript(transcript_id: int, data: dict) -> Response:
    """Queue a refinement via CommandBus intent."""
    coordinator = get_coordinator()
    from src.core.intents.definitions import RefineTranscriptIntent

    intent = RefineTranscriptIntent(
        transcript_id=transcript_id,
        level=data.get("level", 2),
        instructions=data.get("instructions", ""),
    )
    coordinator.command_bus.dispatch(intent)
    return Response(content={"status": "queued"})


@delete("/api/transcripts/{transcript_id:int}/variants/{variant_id:int}", status_code=200)
async def delete_variant(transcript_id: int, variant_id: int) -> Response:
    """Delete a transcript variant via CommandBus intent."""
    from src.core.intents.definitions import DeleteTranscriptVariantIntent

    coordinator = get_coordinator()
    intent = DeleteTranscriptVariantIntent(
        transcript_id=transcript_id, variant_id=variant_id
    )
    success = coordinator.command_bus.dispatch(intent)
    if not success:
        return Response(content={"error": "Delete failed"}, status_code=500)
    return Response(content={"deleted": True})


def transcript_to_dict(t, include_variants: bool = False) -> dict:
    """Convert a Transcript dataclass to a JSON-serializable dict."""
    d = {
        "id": t.id,
        "timestamp": t.timestamp,
        "raw_text": t.raw_text,
        "normalized_text": t.normalized_text,
        "text": t.text,
        "display_name": t.display_name,
        "duration_ms": t.duration_ms,
        "speech_duration_ms": t.speech_duration_ms,
        "project_id": t.project_id,
        "project_name": t.project_name,
        "current_variant_id": t.current_variant_id,
        "created_at": t.created_at,
    }
    if include_variants:
        d["variants"] = [
            {
                "id": v.id,
                "kind": v.kind,
                "text": v.text,
                "model_id": v.model_id,
                "created_at": v.created_at,
            }
            for v in t.variants
        ]
    return d
