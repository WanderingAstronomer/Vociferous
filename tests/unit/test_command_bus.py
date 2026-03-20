"""
Tests for the v4 CommandBus.

Verifies:
- Register + dispatch
- Unregister
- Unknown intent returns False
- Handler receives correct intent data
"""

from abc import ABCMeta
from dataclasses import dataclass

import pytest

from src.core.command_bus import CommandBus, handles
from src.core.intents import InteractionIntent


@dataclass(frozen=True, slots=True)
class _TestIntent(InteractionIntent):
    value: int = 0


@dataclass(frozen=True, slots=True)
class _AnotherIntent(InteractionIntent):
    name: str = ""


class TestCommandBus:
    def test_interaction_intent_is_plain_marker_base(self):
        assert isinstance(InteractionIntent, type)
        assert not isinstance(InteractionIntent, ABCMeta)

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


class TestHandlesDecorator:
    """Tests for @handles decorator and register_all() auto-wiring."""

    def test_handles_decorator_sets_attribute(self):
        @handles(_TestIntent)
        def handler(intent):
            pass

        assert hasattr(handler, "_handles_intent")
        assert handler._handles_intent is _TestIntent

    def test_register_all_discovers_decorated_methods(self):
        class MyHandlers:
            def __init__(self):
                self.log = []

            @handles(_TestIntent)
            def handle_test(self, intent):
                self.log.append(("test", intent.value))

            @handles(_AnotherIntent)
            def handle_another(self, intent):
                self.log.append(("another", intent.name))

        bus = CommandBus()
        obj = MyHandlers()
        bus.register_all(obj)

        bus.dispatch(_TestIntent(value=99))
        bus.dispatch(_AnotherIntent(name="hello"))

        assert obj.log == [("test", 99), ("another", "hello")]
        assert set(bus.registered_types) == {_TestIntent, _AnotherIntent}

    def test_register_all_ignores_undecorated_methods(self):
        class Mixed:
            @handles(_TestIntent)
            def handle_test(self, intent):
                pass

            def not_a_handler(self):
                pass

        bus = CommandBus()
        bus.register_all(Mixed())

        assert bus.registered_types == [_TestIntent]

    def test_register_all_skips_private_methods(self):
        class Private:
            @handles(_TestIntent)
            def _private_handler(self, intent):
                pass

        bus = CommandBus()
        bus.register_all(Private())

        # Private methods (starting with _) are skipped by register_all
        assert bus.registered_types == []
