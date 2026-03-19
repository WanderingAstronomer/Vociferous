"""
Window control and native dialog API routes.
"""

from __future__ import annotations

import logging
from pathlib import Path

from litestar import Response, post

from src.api.deps import get_coordinator

logger = logging.getLogger(__name__)


@post("/api/window/minimize", sync_to_thread=True)
def minimize_window() -> dict:
    """Minimize the main window."""
    coordinator = get_coordinator()
    coordinator.minimize_window()
    return {"status": "ok"}


@post("/api/window/maximize", sync_to_thread=True)
def maximize_window() -> dict:
    """Toggle maximize/restore on the main window."""
    coordinator = get_coordinator()
    coordinator.maximize_window()
    return {"status": "ok", "maximized": coordinator.is_window_maximized()}


@post("/api/window/close", sync_to_thread=True)
def close_window() -> dict:
    """Close the main window and shut down."""
    coordinator = get_coordinator()
    coordinator.close_window()
    return {"status": "ok"}


@post("/api/export")
async def export_file(data: dict) -> Response:
    """
    Write exported content to a user-chosen path via the native save dialog.

    Expects: { "content": str, "filename": str }
    Returns: { "path": str } on success, or error.
    """
    import asyncio

    content: str = data.get("content", "")
    filename: str = Path(data.get("filename", "export.txt")).name

    coordinator = get_coordinator()

    # create_file_dialog must run on the main (GTK/UI) thread — use run_in_executor
    # so we don't block the async API event loop.
    loop = asyncio.get_running_loop()
    save_path: str | None = await loop.run_in_executor(None, coordinator.show_save_dialog, filename)

    if save_path is None:
        return Response(content={"error": "cancelled"}, status_code=400)

    try:
        Path(save_path).write_text(content, encoding="utf-8")
    except OSError as e:
        logger.error("Export write failed: %s", e)
        return Response(content={"error": str(e)}, status_code=500)

    return Response(content={"path": save_path})
