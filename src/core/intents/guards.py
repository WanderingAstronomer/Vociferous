"""
Replay Guard System.

Ensures execution safety when replaying macros or voice commands
without user confirmation (Headless Safety).
"""

from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Optional, Set

from . import InteractionIntent


@dataclass(frozen=True)
class ReplayContext:
    """
    Context snapshot for guard evaluation.

    Uses CAUSAL/CAPABILITY fields, not class names.
    """

    active_view_id: str
    focused_capability: str  # e.g. "text_editable", "recordable", "navigable"
    can_edit: bool
    mode_flags: Set[str] = field(default_factory=set)


@dataclass(frozen=True)
class GuardResult:
    """Outcome of a policy evaluation."""

    allowed: bool
    resolver_intent: Optional["InteractionIntent"] = None
    reason: str = ""


class GuardPolicy(ABC):
    """Abstract base for safety policies."""

    @abstractmethod
    def evaluate(
        self, context: ReplayContext, intent: "InteractionIntent"
    ) -> GuardResult:
        pass


class ContextMatchGuard(GuardPolicy):
    """
    Ensures the intent is only executed if the context matches required capabilities.
    """

    def __init__(self, required_capability: str):
        self.required_capability = required_capability

    def evaluate(
        self, context: ReplayContext, intent: "InteractionIntent"
    ) -> GuardResult:
        if context.focused_capability != self.required_capability:
            return GuardResult(
                False,
                reason=f"Context mismatch. Required: {self.required_capability}, Found: {context.focused_capability}",
            )
        return GuardResult(True)
