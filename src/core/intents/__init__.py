"""
Intent System Root.

Defines the core data structures for User Intent.
"""

from abc import ABC
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InteractionIntent(ABC):
    """
    Base class for all user intents.
    Must be immutable.
    Idempotence is defined in the handler registry, NOT here.
    """
