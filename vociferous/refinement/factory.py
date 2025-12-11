from __future__ import annotations

from vociferous.refinement.base import (
    NullRefiner,
    Refiner,
    RefinerConfig,
)
from vociferous.refinement.canary_refiner import CanaryRefiner


def build_refiner(config: RefinerConfig | None) -> Refiner:
    """Construct a refiner from config.
    
    Returns NullRefiner if refinement is disabled; otherwise returns
    CanaryRefiner for LLM-based text polishing.
    
    Args:
        config: Refiner configuration with enabled flag
        
    Returns:
        Refiner instance (NullRefiner or CanaryRefiner)
    """
    if config is None or not config.enabled:
        return NullRefiner()
    
    return CanaryRefiner()

