"""
Command Bus — Dict-based intent dispatch.

Central hub for intent dispatch. No QObject, no signals, no registry.
~25 lines of actual logic.
"""

import logging
from typing import Any, Callable

from src.core.intents import InteractionIntent

logger = logging.getLogger(__name__)

# Type alias for intent handlers
IntentHandler = Callable[[InteractionIntent], Any]


class CommandBus:
    """
    Dispatches intents to registered handlers.

    Simple dict lookup: intent type → handler callable.
    """

    def __init__(self) -> None:
        self._handlers: dict[type[InteractionIntent], IntentHandler] = {}

    def register(self, intent_type: type[InteractionIntent], handler: IntentHandler) -> None:
        """Register a handler for an intent type."""
        self._handlers[intent_type] = handler

    def unregister(self, intent_type: type[InteractionIntent]) -> None:
        """Remove a handler registration."""
        self._handlers.pop(intent_type, None)

    def dispatch(self, intent: InteractionIntent) -> bool:
        """
        Dispatch an intent to its registered handler.

        Returns True if a handler was found and executed successfully.
        """
        intent_type = type(intent)
        handler = self._handlers.get(intent_type)

        if handler is None:
            logger.warning("No handler registered for %s", intent_type.__name__)
            return False

        try:
            handler(intent)
            return True
        except Exception:
            logger.exception("Handler failed for %s", intent_type.__name__)
            return False

    @property
    def registered_types(self) -> list[type[InteractionIntent]]:
        """List all registered intent types."""
        return list(self._handlers.keys())
