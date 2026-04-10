"""
Tag API routes.

Handles tag CRUD operations and transcript-tag assignment.
"""

from __future__ import annotations

import logging

from litestar import Response, delete, get, post, put

from src.api.config import clear_default_refinement_prompt_if_matches
from src.api.deps import get_coordinator

logger = logging.getLogger(__name__)


@get("/api/tags", sync_to_thread=True)
def list_tags() -> list[dict]:
    coordinator = get_coordinator()
    if coordinator.db is None:
        return []
    tags = coordinator.db.get_tags()
    return [{"id": t.id, "name": t.name, "color": t.color, "is_system": t.is_system} for t in tags]


@post("/api/tags")
async def create_tag(data: dict) -> Response:
    """Create a tag and emit tag_created event."""
    name = data.get("name", "").strip()
    if not name:
        return Response(content={"error": "Tag name is required"}, status_code=400)

    coordinator = get_coordinator()
    if coordinator.db is None:
        return Response(content={"error": "Database not available"}, status_code=503)
    tag = coordinator.db.add_tag(name=name, color=data.get("color"))
    coordinator.event_bus.emit("tag_created", {"id": tag.id, "name": tag.name, "color": tag.color})
    return Response(content={"status": "created"})


@put("/api/tags/{tag_id:int}", sync_to_thread=True)
def update_tag(tag_id: int, data: dict) -> Response:
    """Update a tag's name or color."""
    coordinator = get_coordinator()
    if coordinator.db is None:
        return Response(content={"error": "Database not available"}, status_code=503)
    existing = coordinator.db.get_tag(tag_id)
    if existing is None:
        return Response(content={"error": "Not found"}, status_code=404)
    if existing.is_system:
        return Response(content={"error": "System tags cannot be modified"}, status_code=403)
    tag = coordinator.db.update_tag(
        tag_id, **{k: v for k, v in data.items() if k in ("name", "color") and v is not None}
    )
    if not tag:
        return Response(content={"error": "Update failed"}, status_code=500)
    coordinator.event_bus.emit("tag_updated", {"id": tag.id, "name": tag.name, "color": tag.color})
    return Response(content={"status": "updated"})


@delete("/api/tags/{tag_id:int}", status_code=200, sync_to_thread=True)
def delete_tag(tag_id: int) -> Response:
    """Delete a tag."""
    coordinator = get_coordinator()
    if coordinator.db is None:
        return Response(content={"error": "Database not available"}, status_code=503)
    existing = coordinator.db.get_tag(tag_id)
    if existing is None:
        return Response(content={"error": "Not found"}, status_code=404)
    if existing.is_system:
        return Response(content={"error": "System tags cannot be deleted"}, status_code=403)
    deleted = coordinator.db.delete_tag(tag_id)
    if not deleted:
        return Response(content={"error": "Delete failed"}, status_code=500)
    coordinator.event_bus.emit("tag_deleted", {"id": tag_id})
    return Response(content={"deleted": True})


@post("/api/transcripts/{transcript_id:int}/tags")
async def assign_tags(transcript_id: int, data: dict) -> Response:
    """Set the exact tag set for a transcript."""
    tag_ids = data.get("tag_ids", [])
    if not isinstance(tag_ids, list) or not all(isinstance(i, int) for i in tag_ids):
        return Response(content={"error": "'tag_ids' must be a list of integers"}, status_code=400)

    coordinator = get_coordinator()
    if coordinator.db is None:
        return Response(content={"error": "Database not available"}, status_code=503)
    tags = coordinator.db.assign_tags(transcript_id, list(tag_ids))
    default_prompt_id = coordinator.settings.refinement.default_prompt_transcript_id
    if default_prompt_id == transcript_id and not any(tag.name == "Prompt" for tag in tags):
        clear_default_refinement_prompt_if_matches(coordinator, transcript_id)
    coordinator.event_bus.emit(
        "transcript_updated",
        {
            "id": transcript_id,
            "tags": [{"id": t.id, "name": t.name, "color": t.color, "is_system": t.is_system} for t in tags],
        },
    )
    return Response(content={"status": "assigned"})
