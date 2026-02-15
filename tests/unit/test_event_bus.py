"""
Tests for the v4 EventBus.

Verifies:
- Subscribe + emit
- Unsubscribe
- Multiple handlers
- Thread safety
"""

import threading

import pytest

from src.core.event_bus import EventBus


class TestEventBus:
    def test_subscribe_and_emit(self):
        bus = EventBus()
        received = []

        bus.on("test", lambda data: received.append(data))
        bus.emit("test", {"value": 42})

        assert len(received) == 1
        assert received[0]["value"] == 42

    def test_unsubscribe(self):
        bus = EventBus()
        received = []

        unsub = bus.on("test", lambda data: received.append(data))
        bus.emit("test", {"a": 1})
        unsub()
        bus.emit("test", {"a": 2})

        assert len(received) == 1

    def test_multiple_handlers(self):
        bus = EventBus()
        a, b = [], []

        bus.on("test", lambda d: a.append(d))
        bus.on("test", lambda d: b.append(d))
        bus.emit("test", {"x": 1})

        assert len(a) == 1
        assert len(b) == 1

    def test_emit_unknown_event_no_error(self):
        bus = EventBus()
        bus.emit("nonexistent", {})  # Should not raise

    def test_clear(self):
        bus = EventBus()
        received = []
        bus.on("test", lambda d: received.append(d))
        bus.clear()
        bus.emit("test", {"x": 1})
        assert len(received) == 0

    def test_thread_safety(self):
        """Emit from multiple threads should not crash."""
        bus = EventBus()
        results = []
        lock = threading.Lock()

        def handler(data):
            with lock:
                results.append(data)

        bus.on("concurrent", handler)

        threads = [
            threading.Thread(target=lambda i=i: bus.emit("concurrent", {"i": i}))
            for i in range(50)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(results) == 50

    def test_handler_exception_does_not_break_others(self):
        bus = EventBus()
        results = []

        bus.on("test", lambda d: (_ for _ in ()).throw(ValueError("boom")))
        bus.on("test", lambda d: results.append(d))
        bus.emit("test", {"v": 1})

        # Second handler should still fire
        assert len(results) == 1
