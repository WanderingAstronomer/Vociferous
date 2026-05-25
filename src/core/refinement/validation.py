"""SLM-readiness validation used by refinement intent handlers.

Returns either a ready runtime or a user-facing error message so callers
don't have to know the SLMState enum themselves.
"""

from __future__ import annotations

from typing import Any


def validate_slm_ready(slm_runtime: Any) -> tuple[Any, str | None]:
    """Check SLM is ready; return ``(runtime, error_message_or_None)``."""
    if not slm_runtime:
        return None, "Refinement is not configured. Enable it in Settings."

    from src.services.slm_types import SLMState

    state = slm_runtime.state
    if state == SLMState.DISABLED:
        return None, "Refinement is disabled. Enable it in Settings and ensure a model is downloaded."
    if state == SLMState.LOADING:
        return None, "The refinement model is still loading. Please wait a moment and try again."
    if state == SLMState.ERROR:
        return None, "The refinement model failed to load. Check Settings to verify a model is downloaded."
    if state == SLMState.INFERRING:
        return None, "A refinement is already in progress. Please wait for it to finish."
    if state != SLMState.READY:
        return None, f"Refinement model not ready (state: {state.value})"
    return slm_runtime, None


__all__ = ["validate_slm_ready"]
