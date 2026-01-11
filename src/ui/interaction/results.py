"""
Intent outcome definitions for interaction layer.

Outcomes represent the system's response to an intent. They do not
perform actions; they describe what happened (or will happen) when
the workspace interpreted an intent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING
import time

if TYPE_CHECKING:
    from ui.interaction.intents import InteractionIntent


class IntentOutcome(Enum):
    """Result category for intent processing."""

    ACCEPTED = auto()  # Intent fulfilled immediately
    REJECTED = auto()  # Intent denied; user action required
    DEFERRED = auto()  # Intent queued for later execution
    NO_OP = auto()  # Intent valid but had no effect


@dataclass(frozen=True, slots=True)
class IntentResult:
    """
    Outcome of processing an intent.

    This is a record, not a command. It describes what the workspace
    decided when it received an intent. It does not cause side effects.

    Attributes:
        outcome: The category of result
        intent: The intent that was processed
        reason: Human-readable explanation (for REJECTED/DEFERRED)
        timestamp: When the intent was processed
    """

    outcome: IntentOutcome
    intent: "InteractionIntent"
    reason: str | None = None
    timestamp: float = field(default_factory=time.time)

    def is_success(self) -> bool:
        """True if intent was accepted or was a valid no-op."""
        return self.outcome in (IntentOutcome.ACCEPTED, IntentOutcome.NO_OP)

    def is_failure(self) -> bool:
        """True if intent was rejected."""
        return self.outcome == IntentOutcome.REJECTED

    def is_pending(self) -> bool:
        """True if intent was deferred for later."""
        return self.outcome == IntentOutcome.DEFERRED
