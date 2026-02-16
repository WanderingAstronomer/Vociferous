"""
API dependency — provides access to the ApplicationCoordinator.

Module-level reference set by create_app(). Route handlers import
get_coordinator() to access services without closures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.application_coordinator import ApplicationCoordinator

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
