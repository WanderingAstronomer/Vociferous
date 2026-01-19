"""
Intent Registry.

Maps Intent types to:
1. Handler Functions
2. Guard Policies
3. Idempotence Metadata (Retriable vs Non-Retriable)
"""

from typing import Type, Callable, NamedTuple, Dict, Any, Optional
from . import InteractionIntent
from .guards import GuardPolicy


class IntentMetadata(NamedTuple):
    handler: Callable[[Any], None]
    guard: Optional[GuardPolicy]
    is_idempotent: bool


class HandbookRegistry:
    """
    Central registry for intent behavior.
    """

    _registry: Dict[Type[InteractionIntent], IntentMetadata] = {}

    @classmethod
    def register(
        cls,
        intent_type: Type[InteractionIntent],
        is_idempotent: bool = False,
        guard: Optional[GuardPolicy] = None,
    ):
        """Decorator to register a handler."""

        def decorator(handler_fn):
            cls._registry[intent_type] = IntentMetadata(
                handler_fn, guard, is_idempotent
            )
            return handler_fn

        return decorator

    @classmethod
    def get_metadata(
        cls, intent_type: Type[InteractionIntent]
    ) -> Optional[IntentMetadata]:
        return cls._registry.get(intent_type)
