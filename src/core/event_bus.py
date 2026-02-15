"""
Event Bus — Lightweight pub/sub for backend → frontend event streaming.

Thread-safe. Services emit events, WebSocket handler relays them to clients.
Completely decoupled from intent/command bus (which handles UI→backend intents).
"""

import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

EventHandler = Callable[[dict[str, Any]], None]


@dataclass(frozen=True, slots=True)
class Event:
    """A typed event with arbitrary payload."""
    type: str
    data: dict[str, Any] = field(default_factory=dict)


class EventBus:
    """
    Thread-safe event bus.

    Usage:
        bus = EventBus()
        bus.on("transcription_complete", handler)
        bus.emit("transcription_complete", {"text": "hello"})
    """

    def __init__(self) -> None:
        self._handlers: dict[str, set[EventHandler]] = defaultdict(set)
        self._lock = threading.Lock()

    def on(self, event_type: str, handler: EventHandler) -> Callable[[], None]:
        """Subscribe to an event type. Returns an unsubscribe function."""
        with self._lock:
            self._handlers[event_type].add(handler)

        def unsubscribe():
            with self._lock:
                self._handlers[event_type].discard(handler)

        return unsubscribe

    def emit(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Emit an event to all handlers. Non-blocking; handler errors are logged."""
        with self._lock:
            handlers = list(self._handlers.get(event_type, []))

        for handler in handlers:
            try:
                handler(data or {})
            except Exception:
                logger.exception("Event handler error for '%s'", event_type)

    def off(self, event_type: str, handler: EventHandler) -> None:
        """Unsubscribe a specific handler."""
        with self._lock:
            self._handlers[event_type].discard(handler)

    def clear(self) -> None:
        """Remove all handlers."""
        with self._lock:
            self._handlers.clear()
