"""
Litestar API Application — Vociferous v4.0.

REST + WebSocket endpoints bridging the Svelte frontend to the Python backend.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from litestar import Litestar, get, post, put, delete, WebSocket
from litestar.config.cors import CORSConfig
from litestar.handlers import websocket_listener
from litestar.response import Response
from litestar.static_files import StaticFilesConfig

from src.core.resource_manager import ResourceManager

if TYPE_CHECKING:
    from src.core.application_coordinator import ApplicationCoordinator

logger = logging.getLogger(__name__)


# --- WebSocket connection manager ---

class ConnectionManager:
    """Manages active WebSocket connections and broadcasts events."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.add(ws)
        logger.debug("WS client connected (%d total)", len(self._connections))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)
        logger.debug("WS client disconnected (%d total)", len(self._connections))

    async def broadcast(self, event_type: str, data: dict) -> None:
        """Send an event to all connected WebSocket clients."""
        message = json.dumps({"type": event_type, "data": data})
        async with self._lock:
            dead = []
            for ws in self._connections:
                try:
                    await ws.send_data(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._connections.discard(ws)


def create_app(coordinator: ApplicationCoordinator) -> Litestar:
    """Create the Litestar application with all routes."""

    ws_manager = ConnectionManager()

    # Bridge EventBus → WebSocket broadcast
    _wire_event_bridge(coordinator, ws_manager)

    # --- WebSocket handler ---

    @websocket_listener("/ws")
    async def ws_handler(data: str, socket: WebSocket) -> None:
        """
        Handle incoming WebSocket messages from the frontend.

        Expected format: {"type": "start_recording", ...}
        Responses are sent via EventBus → broadcast bridge, not direct replies.
        """
        try:
            msg = json.loads(data)
            msg_type = msg.get("type", "")
        except (json.JSONDecodeError, AttributeError):
            logger.warning("Invalid WS message: %s", data[:100])
            return

        _handle_ws_message(coordinator, msg_type, msg.get("data", {}))

    # --- Transcript endpoints ---

    @get("/api/transcripts")
    async def list_transcripts(limit: int = 50, project_id: int | None = None) -> list[dict]:
        if coordinator.db is None:
            return []
        transcripts = coordinator.db.recent(limit=limit, project_id=project_id)
        return [_transcript_to_dict(t) for t in transcripts]

    @get("/api/transcripts/{transcript_id:int}")
    async def get_transcript(transcript_id: int) -> Response:
        if coordinator.db is None:
            return Response(content={"error": "Database not available"}, status_code=503)
        t = coordinator.db.get_transcript(transcript_id)
        if t is None:
            return Response(content={"error": "Not found"}, status_code=404)
        return Response(content=_transcript_to_dict(t, include_variants=True))

    @delete("/api/transcripts/{transcript_id:int}")
    async def delete_transcript(transcript_id: int) -> Response:
        if coordinator.db is None:
            return Response(content={"error": "Database not available"}, status_code=503)
        deleted = coordinator.db.delete_transcript(transcript_id)
        if not deleted:
            return Response(content={"error": "Not found"}, status_code=404)
        coordinator.event_bus.emit("transcript_deleted", {"id": transcript_id})
        return Response(content={"deleted": True})

    @post("/api/transcripts/{transcript_id:int}/refine")
    async def refine_transcript(transcript_id: int, data: dict) -> Response:
        from src.core.intents.definitions import RefineTranscriptIntent
        intent = RefineTranscriptIntent(
            transcript_id=transcript_id,
            level=data.get("level", 2),
            instructions=data.get("instructions", ""),
        )
        coordinator.command_bus.dispatch(intent)
        return Response(content={"status": "queued"})

    @get("/api/transcripts/search")
    async def search_transcripts(q: str, limit: int = 50) -> list[dict]:
        if coordinator.db is None:
            return []
        results = coordinator.db.search(q, limit=limit)
        return [_transcript_to_dict(t) for t in results]

    # --- Project endpoints ---

    @get("/api/projects")
    async def list_projects() -> list[dict]:
        if coordinator.db is None:
            return []
        projects = coordinator.db.get_projects()
        return [
            {"id": p.id, "name": p.name, "color": p.color, "parent_id": p.parent_id}
            for p in projects
        ]

    @post("/api/projects")
    async def create_project(data: dict) -> dict:
        if coordinator.db is None:
            return {"error": "Database not available"}
        p = coordinator.db.add_project(
            name=data["name"],
            color=data.get("color"),
            parent_id=data.get("parent_id"),
        )
        return {"id": p.id, "name": p.name, "color": p.color}

    @delete("/api/projects/{project_id:int}")
    async def delete_project(project_id: int) -> Response:
        if coordinator.db is None:
            return Response(content={"error": "Database not available"}, status_code=503)
        deleted = coordinator.db.delete_project(project_id)
        if not deleted:
            return Response(content={"error": "Not found"}, status_code=404)
        return Response(content={"deleted": True})

    # --- Config endpoints ---

    @get("/api/config")
    async def get_config() -> dict:
        return coordinator.settings.model_dump()

    @put("/api/config")
    async def update_config(data: dict) -> dict:
        from src.core.settings import update_settings
        new_settings = update_settings(**data)
        coordinator.settings = new_settings
        coordinator.event_bus.emit("config_updated", new_settings.model_dump())
        return new_settings.model_dump()

    # --- Model endpoints ---

    @get("/api/models")
    async def list_models() -> dict:
        from src.core.model_registry import get_model_catalog
        return get_model_catalog()

    # --- Health ---

    @get("/api/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "version": "4.0.0-dev",
            "transcripts": coordinator.db.transcript_count() if coordinator.db else 0,
        }

    # --- Intent dispatch via POST ---

    @post("/api/intents")
    async def dispatch_intent(data: dict) -> Response:
        """
        Generic intent dispatch from frontend.

        Expects: {"type": "begin_recording", ...fields}
        """
        from src.core.intents import definitions as defs
        intent_type_name = data.pop("type", None)
        if not intent_type_name:
            return Response(content={"error": "Missing 'type'"}, status_code=400)

        intent_map = {
            "begin_recording": defs.BeginRecordingIntent,
            "stop_recording": defs.StopRecordingIntent,
            "cancel_recording": defs.CancelRecordingIntent,
            "toggle_recording": defs.ToggleRecordingIntent,
            "navigate": defs.NavigateIntent,
            "delete_transcript": defs.DeleteTranscriptIntent,
            "commit_edits": defs.CommitEditsIntent,
            "refine_transcript": defs.RefineTranscriptIntent,
        }

        intent_cls = intent_map.get(intent_type_name)
        if intent_cls is None:
            return Response(content={"error": f"Unknown intent: {intent_type_name}"}, status_code=400)

        try:
            intent = intent_cls(**data)
        except Exception as e:
            return Response(content={"error": str(e)}, status_code=400)

        success = coordinator.command_bus.dispatch(intent)
        return Response(content={"dispatched": success})

    # --- Build the app ---

    frontend_dist = ResourceManager.get_app_root() / "frontend" / "dist"
    static_configs = []
    if frontend_dist.is_dir():
        static_configs.append(
            StaticFilesConfig(
                directories=[frontend_dist],
                path="/",
                html_mode=True,
            )
        )

    app = Litestar(
        route_handlers=[
            ws_handler,
            list_transcripts, get_transcript, delete_transcript,
            refine_transcript, search_transcripts,
            list_projects, create_project, delete_project,
            get_config, update_config,
            list_models,
            health,
            dispatch_intent,
        ],
        cors_config=CORSConfig(
            allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
            allow_methods=["*"],
            allow_headers=["*"],
        ),
        static_files_config=static_configs if static_configs else None,
        debug=False,
    )

    return app


def _wire_event_bridge(coordinator: ApplicationCoordinator, ws_manager: ConnectionManager) -> None:
    """
    Bridge EventBus events to WebSocket broadcast.

    The EventBus emits from sync Python threads. We need to schedule
    the async broadcast onto the running asyncio event loop.
    """
    event_types = [
        "recording_started",
        "recording_stopped",
        "transcription_complete",
        "transcription_error",
        "audio_level",
        "refinement_started",
        "refinement_complete",
        "refinement_error",
        "transcript_deleted",
        "config_updated",
        "engine_status",
    ]

    for event_type in event_types:

        def make_handler(et: str):
            def handler(data: dict) -> None:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(ws_manager.broadcast(et, data))
                except RuntimeError:
                    # No running loop — we're in a sync thread.
                    # Schedule on uvicorn's loop if available.
                    try:
                        import uvicorn
                        loop = asyncio.new_event_loop()
                        loop.run_until_complete(ws_manager.broadcast(et, data))
                        loop.close()
                    except Exception:
                        logger.debug("No event loop for WS broadcast of '%s'", et)
            return handler

        coordinator.event_bus.on(event_type, make_handler(event_type))


def _handle_ws_message(coordinator: ApplicationCoordinator, msg_type: str, data: dict) -> None:
    """
    Handle an incoming WebSocket command from the frontend.

    Maps WS message types to CommandBus intents.
    """
    from src.core.intents.definitions import (
        BeginRecordingIntent,
        StopRecordingIntent,
        CancelRecordingIntent,
        ToggleRecordingIntent,
    )

    handlers = {
        "start_recording": lambda: coordinator.command_bus.dispatch(BeginRecordingIntent()),
        "stop_recording": lambda: coordinator.command_bus.dispatch(StopRecordingIntent()),
        "cancel_recording": lambda: coordinator.command_bus.dispatch(CancelRecordingIntent()),
        "toggle_recording": lambda: coordinator.command_bus.dispatch(ToggleRecordingIntent()),
    }

    handler = handlers.get(msg_type)
    if handler:
        handler()
    else:
        logger.warning("Unknown WS message type: %s", msg_type)


def _transcript_to_dict(t, include_variants: bool = False) -> dict:
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
