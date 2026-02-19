"""
Project API routes.

Handles project CRUD operations.
"""

from __future__ import annotations

import logging

from litestar import Response, delete, get, post, put

from src.api.deps import get_coordinator

logger = logging.getLogger(__name__)


@get("/api/projects")
async def list_projects() -> list[dict]:
    coordinator = get_coordinator()
    if coordinator.db is None:
        return []
    projects = coordinator.db.get_projects()
    return [{"id": p.id, "name": p.name, "color": p.color, "parent_id": p.parent_id} for p in projects]


@post("/api/projects")
async def create_project(data: dict) -> Response:
    """Create a project via CommandBus intent."""
    from src.core.intents.definitions import CreateProjectIntent

    coordinator = get_coordinator()
    intent = CreateProjectIntent(
        name=data["name"],
        color=data.get("color"),
        parent_id=data.get("parent_id"),
    )
    success = coordinator.command_bus.dispatch(intent)
    if not success:
        return Response(content={"error": "Create failed"}, status_code=500)
    return Response(content={"status": "created"})


@delete("/api/projects/{project_id:int}", status_code=200)
async def delete_project(project_id: int, data: dict | None = None) -> Response:
    """Delete a project via CommandBus intent."""
    from src.core.intents.definitions import DeleteProjectIntent

    coordinator = get_coordinator()
    opts = data or {}
    intent = DeleteProjectIntent(
        project_id=project_id,
        delete_transcripts=bool(opts.get("delete_transcripts", False)),
        promote_subprojects=bool(opts.get("promote_subprojects", True)),
        delete_subproject_transcripts=bool(opts.get("delete_subproject_transcripts", False)),
    )
    success = coordinator.command_bus.dispatch(intent)
    if not success:
        return Response(content={"error": "Delete failed"}, status_code=500)
    return Response(content={"deleted": True})


@put("/api/projects/{project_id:int}")
async def update_project(project_id: int, data: dict) -> Response:
    """Update a project's name, color, or parent via CommandBus intent."""
    from src.core.intents.definitions import UpdateProjectIntent

    coordinator = get_coordinator()
    intent = UpdateProjectIntent(
        project_id=project_id,
        name=data.get("name"),
        color=data.get("color"),
        parent_id=data.get("parent_id"),
    )
    success = coordinator.command_bus.dispatch(intent)
    if not success:
        return Response(content={"error": "Update failed"}, status_code=500)
    return Response(content={"status": "updated"})
