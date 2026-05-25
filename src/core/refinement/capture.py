"""Pure capture-builder for refinement runs.

Given a settings snapshot and a live SLM runtime, produce the dict of
provider/model/prompt/usage fields that downstream code persists with each
refinement. Has no I/O and no event emission — strictly a data shaper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.refinement.prompt_builder import PromptBuilder

if TYPE_CHECKING:
    from src.core.settings import VociferousSettings

_PROMPT_BODY_SENTINEL = "__VOCIFEROUS_TRANSCRIPT_BODY__"


def build_refinement_capture(
    settings: "VociferousSettings",
    slm_runtime: Any,
    instructions: str,
) -> dict[str, str | int | bool]:
    """Build the refinement-capture payload that gets persisted with the variant.

    Pulls runtime details (provider, model, device, thinking flag, last usage
    counts) from the SLM runtime's ``get_runtime_summary`` when available,
    falling back to settings when the runtime hasn't reported yet.
    """
    runtime: dict[str, object] = {}
    get_runtime_summary = getattr(slm_runtime, "get_runtime_summary", None)
    if callable(get_runtime_summary):
        candidate = get_runtime_summary()
        if isinstance(candidate, dict):
            runtime = candidate

    provider = str(runtime.get("provider") or settings.refinement.provider)
    model_id = str(runtime.get("model_id") or settings.refinement.model_id)
    use_thinking = bool(runtime.get("use_thinking", settings.refinement.use_thinking))
    last_usage = runtime.get("last_usage") if isinstance(runtime.get("last_usage"), dict) else {}
    if use_thinking:
        thinking_directive = ""
    elif provider == "local_ct2":
        thinking_directive = "/no_think"
    else:
        thinking_directive = "/no_think" if "qwen" in model_id.lower() else ""

    prompt_builder = PromptBuilder(
        system_prompt=settings.refinement.system_prompt,
        invariants=settings.refinement.invariants,
    )
    messages = prompt_builder.build_refinement_messages(
        _PROMPT_BODY_SENTINEL,
        instructions,
        use_thinking=use_thinking,
        thinking_directive=thinking_directive,
    )
    prompt_text = "\n\n".join(
        str(message.get("content", "")).replace(_PROMPT_BODY_SENTINEL, "").rstrip()
        for message in messages
        if isinstance(message, dict)
    ).strip()
    return {
        "refinement_provider": provider,
        "refinement_model_id": model_id,
        "refinement_resolved_device": str(runtime.get("resolved_device") or ""),
        "refinement_compute_type": str(runtime.get("compute_type") or ""),
        "refinement_cpu_threads": int(runtime.get("cpu_threads") or 0),
        "refinement_gpu_layers": int(runtime.get("gpu_layers") or 0),
        "refinement_use_thinking": use_thinking,
        "refinement_prompt_text": prompt_text,
        "refinement_prompt_chars": len(prompt_text),
        "refinement_prompt_words": len(prompt_text.split()),
        "refinement_prompt_tokens": int(last_usage.get("prompt_tokens") or 0),
        "refinement_completion_tokens": int(last_usage.get("completion_tokens") or 0),
        "refinement_total_tokens": int(last_usage.get("total_tokens") or 0),
    }


__all__ = ["build_refinement_capture"]
