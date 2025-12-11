from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class RefinerConfig:
    """Configuration for transcript refinement.

    The refiner uses Canary-Qwen LLM for lightweight, local-first polishing.
    Refinement can be toggled on/off via the enabled flag.
    """

    enabled: bool = False
    params: dict[str, str] = field(default_factory=dict)


class Refiner(Protocol):
    """Interface for transcript refiners.

    Implementations should be local and lightweight. The refiner receives
    the full transcript text and returns an improved string.
    """

    def refine(self, text: str, instructions: str | None = None) -> str:  # pragma: no cover - Protocol definition
        ...


class NullRefiner:
    """No-op refiner used when refinement is disabled."""

    def refine(self, text: str, instructions: str | None = None) -> str:
        return text

