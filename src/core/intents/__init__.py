"""
Intent System Root.

Defines the core data structures for User Intent.
"""

from dataclasses import dataclass
from abc import ABC


@dataclass(frozen=True, slots=True)
class InteractionIntent(ABC):
    """
    Base class for all user intents.
    Must be immutable.
    Idempotence is defined in the handler registry, NOT here.
    """

    pass
