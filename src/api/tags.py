"""
Tag API routes.

Handles tag CRUD operations and transcript-tag assignment.
"""

from __future__ import annotations

import logging

from litestar import Response, delete, get, post, put

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
    """Create a tag via CommandBus intent."""
    from src.core.intents.definitions import CreateTagIntent

    name = data.get("name", "").strip()
    if not name:
        return Response(content={"error": "Tag name is required"}, status_code=400)

    coordinator = get_coordinator()
    intent = CreateTagIntent(name=name, color=data.get("color"))
    success = coordinator.command_bus.dispatch(intent)
    if not success:
        return Response(content={"error": "Create failed"}, status_code=500)
    return Response(content={"status": "created"})


@put("/api/tags/{tag_id:int}")
async def update_tag(tag_id: int, data: dict) -> Response:
    """Update a tag's name or color via CommandBus intent."""
    from src.core.intents.definitions import UpdateTagIntent

    coordinator = get_coordinator()
    if coordinator.db is not None:
        tag = coordinator.db.get_tag(tag_id)
        if tag is not None and tag.is_system:
            return Response(content={"error": "System tags cannot be modified"}, status_code=403)
    intent = UpdateTagIntent(
        tag_id=tag_id,
        name=data.get("name"),
        color=data.get("color"),
    )
    success = coordinator.command_bus.dispatch(intent)
    if not success:
        return Response(content={"error": "Update failed"}, status_code=500)
    return Response(content={"status": "updated"})


@delete("/api/tags/{tag_id:int}", status_code=200)
async def delete_tag(tag_id: int) -> Response:
    """Delete a tag via CommandBus intent."""
    from src.core.intents.definitions import DeleteTagIntent

    coordinator = get_coordinator()
    if coordinator.db is not None:
        tag = coordinator.db.get_tag(tag_id)
        if tag is not None and tag.is_system:
            return Response(content={"error": "System tags cannot be deleted"}, status_code=403)
    intent = DeleteTagIntent(tag_id=tag_id)
    success = coordinator.command_bus.dispatch(intent)
    if not success:
        return Response(content={"error": "Delete failed"}, status_code=500)
    return Response(content={"deleted": True})


@post("/api/transcripts/{transcript_id:int}/tags")
async def assign_tags(transcript_id: int, data: dict) -> Response:
    """Set the exact tag set for a transcript via CommandBus intent."""
    from src.core.intents.definitions import AssignTagsIntent

    tag_ids = data.get("tag_ids", [])
    if not isinstance(tag_ids, list) or not all(isinstance(i, int) for i in tag_ids):
        return Response(content={"error": "'tag_ids' must be a list of integers"}, status_code=400)

    coordinator = get_coordinator()
    intent = AssignTagsIntent(transcript_id=transcript_id, tag_ids=tuple(tag_ids))
    success = coordinator.command_bus.dispatch(intent)
    if not success:
        return Response(content={"error": "Assign failed"}, status_code=500)
    return Response(content={"status": "assigned"})
