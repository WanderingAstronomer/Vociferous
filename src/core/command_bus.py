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

# Sentinel attribute name set by the @handles decorator.
_HANDLES_ATTR = "_handles_intent"


def handles(intent_type: type[InteractionIntent]) -> Callable:
    """Mark a handler method so CommandBus.register_all() can auto-wire it."""

    def decorator(fn: Callable) -> Callable:
        setattr(fn, _HANDLES_ATTR, intent_type)
        return fn

    return decorator


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

    def register_all(self, handler_obj: object) -> None:
        """Auto-register every @handles-decorated method on *handler_obj*."""
        for name in dir(handler_obj):
            if name.startswith("_"):
                continue
            method = getattr(handler_obj, name, None)
            intent_type = getattr(method, _HANDLES_ATTR, None)
            if intent_type is not None:
                self._handlers[intent_type] = method

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

        logger.info("Dispatching intent: %s", intent_type.__name__)
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
