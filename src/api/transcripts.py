"""
Transcript API routes.

Handles transcript listing, detail, deletion, search, and refinement.
"""

from __future__ import annotations

import logging

from litestar import Response, delete, get, post

from src.api.deps import get_coordinator

logger = logging.getLogger(__name__)


@get("/api/transcripts", sync_to_thread=True)
def list_transcripts(
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    tag_ids: str | None = None,
    tag_mode: str = "any",
) -> dict:
    coordinator = get_coordinator()
    if coordinator.db is None:
        return {"items": [], "total": 0}
    parsed_tag_ids = [int(t) for t in tag_ids.split(",") if t.strip()] if tag_ids else None
    transcripts, total = coordinator.db.recent(
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_dir=sort_dir,
        tag_ids=parsed_tag_ids,
        tag_mode=tag_mode,
    )
    return {"items": [transcript_to_dict(t) for t in transcripts], "total": total}


@get("/api/transcripts/{transcript_id:int}")
async def get_transcript(transcript_id: int) -> Response:
    import asyncio

    coordinator = get_coordinator()
    if coordinator.db is None:
        return Response(content={"error": "Database not available"}, status_code=503)
    t = await asyncio.to_thread(coordinator.db.get_transcript, transcript_id)
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


@post("/api/transcripts/batch-delete", status_code=200)
async def batch_delete_transcripts(data: dict) -> Response:
    """Delete multiple transcripts in one shot via CommandBus intent."""
    ids = data.get("ids", [])
    if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
        return Response(content={"error": "'ids' must be a list of integers"}, status_code=400)
    if not ids:
        return Response(content={"deleted": 0})

    from src.core.intents.definitions import BatchDeleteTranscriptsIntent

    coordinator = get_coordinator()
    intent = BatchDeleteTranscriptsIntent(transcript_ids=tuple(ids))
    coordinator.command_bus.dispatch(intent)
    return Response(content={"deleted": len(ids)})


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


@get("/api/transcripts/search", sync_to_thread=True)
def search_transcripts(q: str, limit: int = 50, offset: int = 0) -> dict:
    coordinator = get_coordinator()
    if coordinator.db is None:
        return {"items": [], "total": 0, "offset": offset, "limit": limit}
    results = coordinator.db.search(q, limit=limit, offset=offset)
    total = coordinator.db.search_count(q)
    return {
        "items": [transcript_to_dict(t) for t in results],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@post("/api/transcripts/{transcript_id:int}/refine")
async def refine_transcript(transcript_id: int, data: dict) -> Response:
    """Queue a refinement via CommandBus intent."""
    level = data.get("level", 2)
    if not isinstance(level, int) or not (1 <= level <= 5):
        return Response(content={"error": "level must be an integer between 1 and 5"}, status_code=400)

    coordinator = get_coordinator()
    from src.core.intents.definitions import RefineTranscriptIntent

    intent = RefineTranscriptIntent(
        transcript_id=transcript_id,
        level=level,
        instructions=data.get("instructions", ""),
    )
    coordinator.command_bus.dispatch(intent)
    return Response(content={"status": "queued"})


@delete("/api/transcripts/{transcript_id:int}/variants/{variant_id:int}", status_code=200)
async def delete_variant(transcript_id: int, variant_id: int) -> Response:
    """Delete a transcript variant via CommandBus intent."""
    from src.core.intents.definitions import DeleteTranscriptVariantIntent

    coordinator = get_coordinator()
    intent = DeleteTranscriptVariantIntent(transcript_id=transcript_id, variant_id=variant_id)
    success = coordinator.command_bus.dispatch(intent)
    if not success:
        return Response(content={"error": "Delete failed"}, status_code=500)
    return Response(content={"deleted": True})


@post("/api/transcripts/{transcript_id:int}/retitle")
async def retitle_transcript(transcript_id: int) -> Response:
    """Re-generate the SLM title for a single transcript."""
    from src.core.intents.definitions import RetitleTranscriptIntent

    coordinator = get_coordinator()
    intent = RetitleTranscriptIntent(transcript_id=transcript_id)
    coordinator.command_bus.dispatch(intent)
    return Response(content={"status": "queued"})


@post("/api/transcripts/{transcript_id:int}/rename")
async def rename_transcript(transcript_id: int, data: dict) -> Response:
    """Rename a transcript (set display_name) via CommandBus intent."""
    from src.core.intents.definitions import RenameTranscriptIntent

    title = data.get("title", "").strip()
    if not title:
        return Response(content={"error": "Title is required"}, status_code=400)

    coordinator = get_coordinator()
    intent = RenameTranscriptIntent(transcript_id=transcript_id, title=title)
    success = coordinator.command_bus.dispatch(intent)
    if not success:
        return Response(content={"error": "Rename failed"}, status_code=500)
    return Response(content={"status": "renamed", "title": title})


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
        "project_id": t.project_id,  # vestigial — kept for data compat
        "project_name": t.project_name,  # vestigial — kept for data compat
        "current_variant_id": t.current_variant_id,
        "created_at": t.created_at,
        "tags": [{"id": tag.id, "name": tag.name, "color": tag.color} for tag in t.tags],
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
