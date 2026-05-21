"""
API dependency — provides access to the ApplicationCoordinator.

Module-level reference set by create_app(). Route handlers import
get_coordinator() to access services without closures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from litestar.exceptions import HTTPException

if TYPE_CHECKING:
    from src.core.application_coordinator import ApplicationCoordinator
    from src.database.db import TranscriptDB

_coordinator: ApplicationCoordinator | None = None


def set_coordinator(coordinator: ApplicationCoordinator) -> None:
    """Called once by create_app() during server setup."""
    global _coordinator
    _coordinator = coordinator


def get_coordinator() -> "ApplicationCoordinator":
    """Return the coordinator. Raises if not initialized."""
    if _coordinator is None:
        raise RuntimeError("Coordinator not set — API not initialized.")
    return _coordinator


def require_db() -> "TranscriptDB":
    """Return the live TranscriptDB or raise a 503 HTTPException.

    Centralizes the "Database not available" guard that every DB-touching
    route handler would otherwise duplicate.
    """
    coordinator = get_coordinator()
    if coordinator.db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    return coordinator.db


def validate_pagination(limit: int, offset: int) -> None:
    """Raise 400 if pagination params are negative."""
    if limit < 0:
        raise HTTPException(status_code=400, detail="limit must be >= 0")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")
