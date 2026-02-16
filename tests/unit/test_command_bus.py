"""
Tests for the v4 CommandBus.

Verifies:
- Register + dispatch
- Unregister
- Unknown intent returns False
- Handler receives correct intent data
"""

from dataclasses import dataclass

import pytest

from src.core.command_bus import CommandBus
from src.core.intents import InteractionIntent


@dataclass(frozen=True, slots=True)
class _TestIntent(InteractionIntent):
    value: int = 0


@dataclass(frozen=True, slots=True)
class _AnotherIntent(InteractionIntent):
    name: str = ""


class TestCommandBus:
    def test_register_and_dispatch(self):
        bus = CommandBus()
        received = []

        bus.register(_TestIntent, lambda intent: received.append(intent))
        result = bus.dispatch(_TestIntent(value=42))

        assert result is True
        assert len(received) == 1
        assert received[0].value == 42

    def test_dispatch_unknown_returns_false(self):
        bus = CommandBus()
        assert bus.dispatch(_TestIntent(value=1)) is False

    def test_unregister(self):
        bus = CommandBus()
        bus.register(_TestIntent, lambda i: None)
        bus.unregister(_TestIntent)
        assert bus.dispatch(_TestIntent()) is False

    def test_multiple_intent_types(self):
        bus = CommandBus()
        test_received = []
        another_received = []

        bus.register(_TestIntent, lambda i: test_received.append(i))
        bus.register(_AnotherIntent, lambda i: another_received.append(i))

        bus.dispatch(_TestIntent(value=1))
        bus.dispatch(_AnotherIntent(name="hello"))

        assert len(test_received) == 1
        assert len(another_received) == 1
        assert another_received[0].name == "hello"

    def test_handler_exception_does_not_propagate(self):
        bus = CommandBus()

        def _exploding_handler(intent: _TestIntent) -> None:
            raise ValueError("boom")

        bus.register(_TestIntent, _exploding_handler)
        # Should not raise — but returns False because handler failed
        result = bus.dispatch(_TestIntent())
        assert result is False
