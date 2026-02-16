"""
Litestar API Application — Vociferous v4.0.

REST + WebSocket endpoints bridging the Svelte frontend to the Python backend.
Route handlers are defined in dedicated modules (transcripts, projects, system).
This file provides the WebSocket infrastructure and app factory.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import TYPE_CHECKING, Any

from litestar import Litestar, MediaType, WebSocket, get
from litestar.config.cors import CORSConfig
from litestar.exceptions import WebSocketDisconnect
from litestar.handlers import websocket
from litestar.response import File
from litestar.static_files import StaticFilesConfig

from src.api.deps import set_coordinator
from src.api.projects import create_project, delete_project, list_projects, update_project
from src.api.system import (
    close_window,
    dispatch_intent,
    download_model,
    get_config,
    health,
    list_models,
    maximize_window,
    minimize_window,
    restart_engine,
    toggle_mini_widget,
    update_config,
)
from src.api.transcripts import (
    delete_transcript,
    delete_variant,
    get_transcript,
    list_transcripts,
    refine_transcript,
    search_transcripts,
)
from src.core.resource_manager import ResourceManager

if TYPE_CHECKING:
    from src.core.application_coordinator import ApplicationCoordinator

logger = logging.getLogger(__name__)


def _json_default(obj: Any) -> Any:
    """Handle numpy scalars and arrays for JSON serialization."""
    import numpy as np

    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


# --- WebSocket connection manager ---


class ConnectionManager:
    """
    Thread-safe WebSocket connection manager.

    Stores connected sockets and provides broadcast from any thread.
    The event loop reference is captured on first connect so that
    sync EventBus handlers can schedule broadcasts via call_soon_threadsafe.
    """

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def register(self, ws: WebSocket) -> None:
        """Add a WebSocket (called from async context)."""
        with self._lock:
            self._connections.add(ws)
            if self._loop is None:
                try:
                    self._loop = asyncio.get_running_loop()
                except RuntimeError:
                    pass
        logger.debug("WS client connected (%d total)", len(self._connections))

    def unregister(self, ws: WebSocket) -> None:
        """Remove a WebSocket (called from async context)."""
        with self._lock:
            self._connections.discard(ws)
        logger.debug("WS client disconnected (%d total)", len(self._connections))

    def broadcast_threadsafe(self, event_type: str, data: dict) -> None:
        """
        Schedule a broadcast from any thread (sync-safe).

        Called by EventBus handlers which fire from background threads
        (recording thread, refinement thread, etc.).
        """
        with self._lock:
            loop = self._loop
            conns = set(self._connections)

        if not conns or loop is None:
            return

        message = json.dumps({"type": event_type, "data": data}, default=_json_default)

        async def _do_broadcast():
            dead = []
            for ws in conns:
                try:
                    await ws.send_data(message)
                except Exception:
                    dead.append(ws)
            if dead:
                with self._lock:
                    for ws in dead:
                        self._connections.discard(ws)

        try:
            loop.call_soon_threadsafe(asyncio.ensure_future, _do_broadcast())
        except RuntimeError:
            # Loop closed (shutdown)
            pass


def create_app(coordinator: ApplicationCoordinator) -> Litestar:
    """Create the Litestar application with all routes."""

    # Make coordinator available to route modules
    set_coordinator(coordinator)

    ws_manager = ConnectionManager()

    # Bridge EventBus → WebSocket broadcast
    _wire_event_bridge(coordinator, ws_manager)

    # --- WebSocket lifecycle ---

    @websocket("/ws")
    async def ws_handler(socket: WebSocket) -> None:
        """Handle WebSocket connections from the frontend.

        Uses a raw handler instead of @websocket_listener so we can
        catch WebSocketDisconnect cleanly during shutdown — prevents
        Litestar's exception middleware from trying to send a close
        frame on an already-closed socket (which causes RuntimeError
        noise in the terminal).
        """
        await socket.accept()
        ws_manager.register(socket)
        try:
            while True:
                try:
                    data = await socket.receive_data(mode="text")
                except WebSocketDisconnect:
                    break

                try:
                    msg = json.loads(data)
                    msg_type = msg.get("type", "")
                except (json.JSONDecodeError, AttributeError):
                    logger.warning("Invalid WS message: %s", str(data)[:100])
                    continue

                _handle_ws_message(coordinator, msg_type, msg.get("data", {}))
        except Exception:
            logger.debug("WebSocket connection error", exc_info=True)
        finally:
            ws_manager.unregister(socket)

    # --- Static files ---
    # Serve JS/CSS bundles at /assets/ and HTML entry points via explicit routes.
    # IMPORTANT: Do NOT use html_mode=True at path="/" — it creates a catch-all
    # that intercepts parameterized API routes like /api/transcripts/{id}.

    frontend_dist = ResourceManager.get_app_root() / "frontend" / "dist"
    static_configs = []
    spa_handlers = []

    if frontend_dist.is_dir():
        assets_dir = frontend_dist / "assets"
        if assets_dir.is_dir():
            static_configs.append(
                StaticFilesConfig(
                    directories=[assets_dir],
                    path="/assets/",
                )
            )

        # Serve SPA entry points as explicit routes (not catch-all)
        index_html = frontend_dist / "index.html"
        mini_html = frontend_dist / "mini.html"

        if index_html.is_file():

            @get("/", media_type=MediaType.HTML, sync_to_thread=False)
            def serve_index() -> File:
                return File(path=index_html, media_type=MediaType.HTML)

            spa_handlers.append(serve_index)

        if mini_html.is_file():

            @get("/mini.html", media_type=MediaType.HTML, sync_to_thread=False)
            def serve_mini() -> File:
                return File(path=mini_html, media_type=MediaType.HTML)

            spa_handlers.append(serve_mini)

    # --- Build app ---

    app = Litestar(
        route_handlers=[
            # WebSocket
            ws_handler,
            # Transcripts
            list_transcripts,
            get_transcript,
            delete_transcript,
            delete_variant,
            refine_transcript,
            search_transcripts,
            # Projects
            list_projects,
            create_project,
            update_project,
            delete_project,
            # System
            get_config,
            update_config,
            list_models,
            download_model,
            restart_engine,
            health,
            toggle_mini_widget,
            minimize_window,
            maximize_window,
            close_window,
            dispatch_intent,
            # SPA entry points
            *spa_handlers,
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

    EventBus handlers fire from sync Python threads (recording, refinement, etc.).
    We use broadcast_threadsafe() which schedules onto uvicorn's event loop
    via call_soon_threadsafe.
    """
    event_types = [
        "recording_started",
        "recording_stopped",
        "transcription_complete",
        "transcription_error",
        "audio_level",
        "audio_spectrum",
        "refinement_started",
        "refinement_complete",
        "refinement_error",
        "transcript_deleted",
        "config_updated",
        "engine_status",
        "download_progress",
        "project_created",
        "project_deleted",
    ]

    for event_type in event_types:

        def make_handler(et: str):
            def handler(data: dict) -> None:
                ws_manager.broadcast_threadsafe(et, data)

            return handler

        coordinator.event_bus.on(event_type, make_handler(event_type))


def _handle_ws_message(coordinator: ApplicationCoordinator, msg_type: str, data: dict) -> None:
    """
    Handle an incoming WebSocket command from the frontend.

    Maps WS message types to CommandBus intents.
    """
    from src.core.intents.definitions import (
        BeginRecordingIntent,
        CancelRecordingIntent,
        StopRecordingIntent,
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
