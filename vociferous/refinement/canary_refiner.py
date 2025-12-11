"""CanaryRefiner - Text refinement using Canary-Qwen LLM.

Uses the Canary-Qwen engine's dual-mode refinement capability to polish
transcripts with grammar, punctuation, and fluency fixes.
"""

from __future__ import annotations

from vociferous.domain.exceptions import DependencyError
from vociferous.domain.model import EngineConfig
from vociferous.refinement.base import Refiner


class CanaryRefiner(Refiner):
    """Refiner backed by Canary-Qwen LLM refinement mode.
    
    Delegates to the Canary-Qwen engine's refine_text() method for
    lightweight, local LLM-based text polishing.
    """

    def __init__(self) -> None:
        """Initialize Canary-Qwen refiner (lazy-loads engine)."""
        self._engine = None

    def refine(self, text: str, instructions: str | None = None) -> str:
        """Refine text using Canary-Qwen.
        
        Args:
            text: Raw transcript to refine
            instructions: Optional custom refinement instructions (unused; Canary has built-in prompt)
            
        Returns:
            Polished transcript with grammar/punctuation fixes
        """
        if self._engine is None:
            self._engine = self._lazy_load_engine()
        
        return self._engine.refine_text(text)

    def _lazy_load_engine(self):
        """Lazy-load Canary-Qwen engine on first refinement call."""
        try:
            from vociferous.engines.canary_qwen import CanaryQwenEngine
        except ImportError as exc:
            raise DependencyError(
                "Canary-Qwen engine not available; ensure transformers and torch are installed."
            ) from exc

        config = EngineConfig(model_name="nvidia/canary-qwen-2.5b")
        return CanaryQwenEngine(config)
