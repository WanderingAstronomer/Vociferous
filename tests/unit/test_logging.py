from __future__ import annotations

import logging

from src.api import app as api_app
from src.core.log_manager import AgentFriendlyFormatter, LogManager


class _FakeEventBus:
    def on(self, event_type: str, handler: object) -> None:
        pass


class _FakeCoordinator:
    event_bus = _FakeEventBus()


def test_create_app_preserves_log_manager_handlers(monkeypatch) -> None:
    monkeypatch.setattr(api_app, "prewarm_health_cache", lambda: None)
    monkeypatch.setattr(api_app, "_wire_event_bridge", lambda coordinator, ws_manager: None)

    LogManager().configure_logging()
    api_app.create_app(_FakeCoordinator())

    handlers = logging.getLogger().handlers
    assert handlers
    assert all(isinstance(handler.formatter, AgentFriendlyFormatter) for handler in handlers)
    assert all(type(handler).__name__ != "QueueHandler" for handler in handlers)
