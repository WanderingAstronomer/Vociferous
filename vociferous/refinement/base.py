from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class RefinerConfig:
    """Configuration for transcript refinement.

    The refiner should be lightweight and local-first. The config keeps the
    chosen model name and a free-form params mapping for model-specific knobs.
    Empty/whitespace-only params are stripped by consumers.
    """

    model: str | None = None
    enabled: bool = False
    params: dict[str, str] = field(default_factory=dict)


class Refiner(Protocol):
    """Interface for transcript refiners.

    Implementations should be inexpensive and ideally fully local. The refiner
    receives the full transcript text and returns an improved string.
    """

    def refine(self, text: str, instructions: str | None = None) -> str:  # pragma: no cover - Protocol definition
        ...


class NullRefiner:
    """No-op refiner used when refinement is disabled."""

    def refine(self, text: str, instructions: str | None = None) -> str:
        return text


class RuleBasedRefiner:
    """Lightweight heuristic refiner.

    This avoids heavy models and keeps the refinement step fully local. It
    normalizes whitespace, fixes mid-word hyphen splits, and trims stray
    punctuation spacing.
    """

    def __init__(self) -> None:
        self._hyphen_gap_pattern = re.compile(r"(?<=\w)-\s+(?=\w)")

    def refine(self, text: str, instructions: str | None = None) -> str:
        cleaned = " ".join(text.split())
        cleaned = self._hyphen_gap_pattern.sub("", cleaned)
        cleaned = cleaned.replace(" ,", ",").replace(" .", ".")
        return cleaned
