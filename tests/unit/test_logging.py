from __future__ import annotations

import json
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


def test_text_formatter_serializes_and_redacts_context() -> None:
    formatter = AgentFriendlyFormatter(structured=False)
    record = logging.LogRecord(
        name="src.core.example",
        level=logging.INFO,
        pathname=__file__,
        lineno=42,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.context = {"provider": "groq", "api_key": "gsk_secret", "nested": {"token": "abc"}}

    formatted = formatter.format(record)

    assert "core.example:42" in formatted
    assert "context=" in formatted
    assert "gsk_secret" not in formatted
    assert '"api_key": "<redacted>"' in formatted
    assert '"token": "<redacted>"' in formatted


def test_structured_formatter_redacts_context() -> None:
    formatter = AgentFriendlyFormatter(structured=True)
    record = logging.LogRecord(
        name="src.core.example",
        level=logging.INFO,
        pathname=__file__,
        lineno=42,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.context = {"authorization": "Bearer nope"}

    payload = json.loads(formatter.format(record))

    assert payload["logger"] == "core.example"
    assert payload["context"] == {"authorization": "<redacted>"}
