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
    parsed_tag_ids = [int(tag_id) for tag_id in tag_ids.split(",") if tag_id.strip()] if tag_ids else None
    transcripts, total = coordinator.db.recent(
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_dir=sort_dir,
        tag_ids=parsed_tag_ids,
        tag_mode=tag_mode,
    )
    return {"items": [transcript_to_dict(transcript) for transcript in transcripts], "total": total}


@get("/api/transcripts/{transcript_id:int}")
async def get_transcript(transcript_id: int) -> Response:
    import asyncio

    coordinator = get_coordinator()
    if coordinator.db is None:
        return Response(content={"error": "Database not available"}, status_code=503)
    transcript = await asyncio.to_thread(coordinator.db.get_transcript, transcript_id)
    if transcript is None:
        return Response(content={"error": "Not found"}, status_code=404)
    return Response(content=transcript_to_dict(transcript))


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
    return Response(content={"status": "cleared"})


@get("/api/transcripts/search", sync_to_thread=True)
def search_transcripts(q: str, limit: int = 50, offset: int = 0) -> dict:
    coordinator = get_coordinator()
    if coordinator.db is None:
        return {"items": [], "total": 0, "offset": offset, "limit": limit}
    results = coordinator.db.search(q, limit=limit, offset=offset)
    total = coordinator.db.search_count(q)
    return {
        "items": [transcript_to_dict(transcript) for transcript in results],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@post("/api/transcripts/batch-tag-toggle")
async def batch_tag_toggle(data: dict) -> Response:
    """Add or remove a single tag from multiple transcripts in one DB transaction."""
    transcript_ids = data.get("transcript_ids", [])
    tag_id = data.get("tag_id")
    add = data.get("add", True)

    if not isinstance(transcript_ids, list) or not all(isinstance(i, int) for i in transcript_ids):
        return Response(content={"error": "'transcript_ids' must be a list of integers"}, status_code=400)
    if not isinstance(tag_id, int):
        return Response(content={"error": "'tag_id' must be an integer"}, status_code=400)
    if not transcript_ids:
        return Response(content={"toggled": 0})

    from src.core.intents.definitions import BatchToggleTagIntent

    coordinator = get_coordinator()
    intent = BatchToggleTagIntent(transcript_ids=tuple(transcript_ids), tag_id=tag_id, add=bool(add))
    coordinator.command_bus.dispatch(intent)
    return Response(content={"toggled": len(transcript_ids)})


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


@post("/api/transcripts/{transcript_id:int}/refine/commit")
async def commit_refinement(transcript_id: int, data: dict) -> Response:
    """Persist accepted refinement text to normalized_text via CommandBus intent."""
    text = data.get("text", "")
    if not isinstance(text, str) or not text.strip():
        return Response(content={"error": "text is required"}, status_code=400)

    coordinator = get_coordinator()
    from src.core.intents.definitions import CommitRefinementIntent

    intent = CommitRefinementIntent(transcript_id=transcript_id, text=text)
    coordinator.command_bus.dispatch(intent)
    return Response(content={"status": "committed"})


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


def transcript_to_dict(transcript) -> dict:
    """Convert a Transcript dataclass to a JSON-serializable dict."""
    return {
        "id": transcript.id,
        "timestamp": transcript.timestamp,
        "raw_text": transcript.raw_text,
        "normalized_text": transcript.normalized_text,
        "text": transcript.text,
        "display_name": transcript.display_name,
        "duration_ms": transcript.duration_ms,
        "speech_duration_ms": transcript.speech_duration_ms,
        "created_at": transcript.created_at,
        "tags": [
            {"id": tag.id, "name": tag.name, "color": tag.color, "is_system": tag.is_system} for tag in transcript.tags
        ],
    }
