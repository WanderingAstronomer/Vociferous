"""
Pytest configuration for Vociferous (v4).

Shared fixtures for unit, integration, and API tests.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Generator

import pytest

# Project root — ensures `from src.core.xxx import ...` works from tests.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Database fixture —— real SQLite in a temp directory
# ---------------------------------------------------------------------------

@pytest.fixture()
def db(tmp_path: Path):
    """Fresh TranscriptDB backed by a temporary file."""
    from src.database.db import TranscriptDB

    database = TranscriptDB(db_path=tmp_path / "test.db")
    yield database
    database.close()


# ---------------------------------------------------------------------------
# Event collector —— captures EventBus emissions for assertions
# ---------------------------------------------------------------------------

class EventCollector:
    """Subscribes to an EventBus and records every emission."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def handler(self, event_type: str):
        """Return a handler that records events of the given type."""
        def _handler(data: dict) -> None:
            self.events.append((event_type, data))
        return _handler

    def subscribe_all(self, event_bus, event_types: list[str]) -> None:
        """Subscribe to a list of event types on the given bus."""
        for et in event_types:
            event_bus.on(et, self.handler(et))

    def of_type(self, event_type: str) -> list[dict]:
        """Return data payloads for events matching the given type."""
        return [data for et, data in self.events if et == event_type]

    def clear(self) -> None:
        self.events.clear()


@pytest.fixture()
def event_collector() -> EventCollector:
    """Fresh EventCollector instance."""
    return EventCollector()


# ---------------------------------------------------------------------------
# Coordinator fixture —— real buses + real DB, mocked heavy services
# ---------------------------------------------------------------------------

@pytest.fixture()
def coordinator(tmp_path: Path):
    """
    ApplicationCoordinator wired with real CommandBus, EventBus, and DB.

    Heavy services (ASR, SLM, audio, input handler, webview, API server)
    are NOT started — only the intent handler wiring and database.
    This enables testing the full intent→handler→DB→event flow
    without hardware or model dependencies.
    """
    from src.core.application_coordinator import ApplicationCoordinator
    from src.core.settings import init_settings, reset_for_tests

    reset_for_tests()
    settings = init_settings(config_path=tmp_path / "config" / "settings.json")

    coord = ApplicationCoordinator(settings)

    # Initialize only the lightweight parts
    from src.core.handlers.recording_handlers import RecordingSession
    from src.database.db import TranscriptDB

    coord.db = TranscriptDB(db_path=tmp_path / "test.db")
    coord.recording_session = RecordingSession(
        audio_service_provider=lambda: coord.audio_service,
        settings_provider=lambda: coord.settings,
        db_provider=lambda: coord.db,
        event_bus_emit=coord.event_bus.emit,
        shutdown_event=coord._shutdown_event,
        insight_manager_provider=lambda: coord.insight_manager,
        motd_manager_provider=lambda: coord.motd_manager,
    )
    coord._register_handlers()

    yield coord

    # Cleanup
    if coord.db:
        coord.db.close()
    coord.event_bus.clear()
    reset_for_tests()


# ---------------------------------------------------------------------------
# Settings reset —— ensures isolated settings per test module
# ---------------------------------------------------------------------------

@pytest.fixture()
def fresh_settings(tmp_path: Path):
    """Provide clean, isolated settings backed by a temp directory."""
    from src.core.settings import init_settings, reset_for_tests

    reset_for_tests()
    settings = init_settings(config_path=tmp_path / "config" / "settings.json")
    yield settings
    reset_for_tests()
