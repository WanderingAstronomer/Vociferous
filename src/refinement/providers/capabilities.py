"""Per-model capability model for OpenAI-compatible refinement providers.

The runtimes behind the OpenAI-compatible surface (LM Studio, Groq) accept
overlapping but not identical parameter sets. Different model families also
have different sensitivity to those parameters: reasoning models route output
to ``reasoning_content`` when forced into JSON schema mode, Qwen3-family
models honor a ``chat_template_kwargs.enable_thinking`` flag, Groq's
``reasoning_effort`` accepts different value sets depending on the model
family (``low``/``medium``/``high`` for gpt-oss, ``none``/``default`` for
Qwen3-32B), and Qwen3 Multi-Token-Prediction (MTP) variants like Qwopus
have a documented failure rate on structured-output tasks.

This module centralizes that knowledge so the HTTP provider can stay
focused on transport. To add support for a new model family, edit the
marker tuples here and (if needed) extend :class:`ProviderCapabilities`.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.refinement.providers.contracts import GenerationRequest, ReasoningPolicy

# ---------------------------------------------------------------------------
# Marker tuples. Matched as case-insensitive substrings against ``model_id``.
# ---------------------------------------------------------------------------

# Qwen-family models that accept the legacy ``/no_think`` directive in the
# user message. Kept as a fallback for older deployments where the chat
# template does not honor ``enable_thinking``.
_NO_THINK_MODEL_MARKERS = ("qwen", "qwq", "qwopus")

# Qwen3-family chat templates that honor ``chat_template_kwargs.enable_thinking``.
# This is the canonical mechanism for suppressing reasoning. When False, the
# template pre-fills an empty ``<think></think>`` block, structurally
# preventing the model from emitting reasoning at all.
_ENABLE_THINKING_KWARG_MODEL_MARKERS = ("qwen3", "qwq", "qwopus")

# Models that accept the ``reasoning_effort`` parameter.
_REASONING_EFFORT_MODEL_MARKERS = ("qwen3", "qwq", "qwopus", "gpt-oss")

# Qwen3-32B uses ``none``/``default`` for ``reasoning_effort`` instead of the
# ``low``/``medium``/``high`` set used by gpt-oss. Detected separately so the
# Groq path can pick the right value.
_QWEN3_REASONING_EFFORT_MODEL_MARKERS = ("qwen3", "qwq", "qwopus")

# LM Studio routes the output of these reasoning-trained models through
# ``reasoning_content`` even when JSON schema is enforced, causing
# ``content`` to come back empty. Forcing a json_schema response_format
# keeps the structured envelope intact; the HTTP provider then peels the
# text out of either ``content`` or ``reasoning_content``.
_LM_STUDIO_SCHEMA_MODEL_MARKERS = ("gpt-oss", "deepseek-r1")

# Models with built-in Multi-Token-Prediction heads.  These have ~90%
# schema-compliance failures on agentic / structured tasks because LM
# Studio’s “Harmony” parser misses intermediate state transitions during
# speculative bursts.  The HTTP provider enables a single retry when JSON
# schema extraction returns malformed output, instead of immediately raising.
_MTP_MODEL_MARKERS = ("qwopus", "qwen3-mtp")

# Models in the Qwen3.6 architecture family where LM Studio cannot suppress
# thinking via chat_template_kwargs or reasoning_effort.  LM Studio emits:
#   “No valid custom reasoning fields found … Reasoning setting ‘off’ cannot
#   be converted to any custom KVs.”
# and the model generates reasoning_content regardless of enable_thinking=False.
# Both MTP (qwen3.6-*-mtp) and plain (qwen3.6-*) variants are affected.
# The HTTP provider adds _THINKING_UNSUPPRESSABLE_OVERHEAD_TOKENS to the
# token budget when use_thinking=False so the involuntary thinking phase has
# room to complete before actual content is produced.
_THINKING_UNSUPPRESSABLE_MODEL_MARKERS = ("qwopus", "qwen3-mtp", "qwen3.6", "qwen-3.6")

# LM Studio's OpenAI-compatible REST path has been observed to ignore both
# top-level and ``extra_body`` forms of ``chat_template_kwargs`` for these
# Qwen families. Appending an assistant message containing an empty think block
# structurally skips the model's reasoning phase.
_LM_STUDIO_ASSISTANT_PREFILL_MODEL_MARKERS = (
    "qwopus",
    "qwen3-mtp",
    "qwen3.5",
    "qwen-3.5",
    "qwen3.6",
    "qwen-3.6",
)

_GROQ_GPT_OSS_MODEL_MARKERS = ("gpt-oss",)
_GROQ_REASONING_FORMAT_MODEL_MARKERS = ("qwen/qwen3", "qwen3-32b")

# Fields on a ChatCompletion ``message`` object that may carry the cognitive
# trace. ``reasoning_content`` is LM Studio's name; ``reasoning`` is what
# Groq returns when ``reasoning_format`` is ``parsed``.
REASONING_MESSAGE_FIELDS = ("reasoning_content", "reasoning")

# Minimum output budget when schema-forcing reasoning models. The JSON envelope
# itself consumes a non-trivial fraction of the budget; 128 tokens is the
# smallest value that reliably leaves room for the ``text`` payload.
LM_STUDIO_SCHEMA_MIN_OUTPUT_TOKENS = 128

# Strict JSON schema used when forcing structured output on LM Studio
# reasoning models. The single ``text`` field carries the actual response.
TEXT_RESPONSE_FORMAT: dict[str, object] = {
    "type": "json_schema",
    "json_schema": {
        "name": "vociferous_text_response",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
}


def _model_matches(model_id: str, markers: tuple[str, ...]) -> bool:
    lowered = model_id.lower()
    return any(marker in lowered for marker in markers)


@dataclass(frozen=True)
class ProviderCapabilities:
    """Resolved capability set for a (provider_id, model_id) pair."""

    provider_id: str
    model_id: str

    # ---- thinking suppression ---------------------------------------------
    accepts_no_think_directive: bool
    supports_enable_thinking_kwarg: bool
    assistant_prefill_suppresses_thinking: bool

    # ---- reasoning_effort -------------------------------------------------
    supports_reasoning_effort: bool
    reasoning_effort_enabled_value: str
    reasoning_effort_disabled_value: str
    supports_reasoning_format: bool
    supports_include_reasoning: bool

    # ---- structured output workaround ------------------------------------
    force_text_schema: bool
    schema_min_output_tokens: int

    # ---- output routing & retries ----------------------------------------
    routes_output_to_reasoning_content: bool
    is_mtp_model: bool
    # LM Studio cannot suppress thinking for this model via any API parameter.
    # The model generates reasoning_content regardless of use_thinking=False.
    thinking_unsuppressable: bool

    # ----- derivations -----------------------------------------------------

    def thinking_directive(self, *, use_thinking: bool) -> str:
        """Legacy ``/no_think`` directive to inject into the user message.

        Emitted as a belt-and-suspenders fallback whenever the model family
        accepts it. Even when ``enable_thinking`` is available, custom merges
        like Qwopus have been observed to ignore the kwarg, so we keep both
        signals in play whenever thinking is disabled.
        """
        if use_thinking:
            return ""
        return "/no_think" if self.accepts_no_think_directive else ""

    def thinking_directive_for(self, request: GenerationRequest) -> str:
        if request.reasoning_policy != ReasoningPolicy.DISABLED:
            return ""
        return "/no_think" if self.accepts_no_think_directive else ""

    def chat_template_kwargs(self, *, use_thinking: bool) -> dict[str, object] | None:
        """LM Studio ``chat_template_kwargs`` payload for thinking control."""
        if self.provider_id != "lm_studio":
            return None
        if not self.supports_enable_thinking_kwarg:
            return None
        return {"enable_thinking": bool(use_thinking)}

    def chat_template_kwargs_for(self, request: GenerationRequest) -> dict[str, object] | None:
        if self.provider_id != "lm_studio":
            return None
        if not self.supports_enable_thinking_kwarg:
            return None
        return {"enable_thinking": request.reasoning_policy != ReasoningPolicy.DISABLED}

    def reasoning_effort_value(self, *, use_thinking: bool) -> str | None:
        """Resolved ``reasoning_effort`` value, or None when not applicable."""
        if not self.supports_reasoning_effort:
            return None
        return self.reasoning_effort_enabled_value if use_thinking else self.reasoning_effort_disabled_value

    def reasoning_effort_for(self, request: GenerationRequest) -> str | None:
        if not self.supports_reasoning_effort:
            return None
        if self.provider_id == "groq" and self.supports_include_reasoning:
            return (
                "low" if request.reasoning_policy == ReasoningPolicy.DISABLED else self.reasoning_effort_enabled_value
            )
        if request.reasoning_policy == ReasoningPolicy.DISABLED:
            return self.reasoning_effort_disabled_value
        return self.reasoning_effort_enabled_value

    def groq_reasoning_params_for(self, request: GenerationRequest) -> dict[str, object]:
        """Return Groq reasoning payload fields without illegal combinations."""
        if self.provider_id != "groq":
            return {}

        params: dict[str, object] = {}
        effort = self.reasoning_effort_for(request)
        if effort is not None:
            params["reasoning_effort"] = effort

        if self.supports_include_reasoning:
            params["include_reasoning"] = request.reasoning_policy == ReasoningPolicy.VISIBLE
            return params

        if self.supports_reasoning_format and request.reasoning_policy != ReasoningPolicy.DISABLED:
            params["reasoning_format"] = "parsed" if request.reasoning_policy == ReasoningPolicy.VISIBLE else "hidden"
        return params

    def should_prefill_empty_think(self, request: GenerationRequest) -> bool:
        return (
            self.provider_id == "lm_studio"
            and self.assistant_prefill_suppresses_thinking
            and request.reasoning_policy == ReasoningPolicy.DISABLED
        )


def resolve_capabilities(provider_id: str, model_id: str) -> ProviderCapabilities:
    """Return the capability descriptor for ``(provider_id, model_id)``."""
    accepts_no_think = provider_id == "lm_studio" and _model_matches(model_id, _NO_THINK_MODEL_MARKERS)
    supports_enable_thinking = provider_id == "lm_studio" and _model_matches(
        model_id, _ENABLE_THINKING_KWARG_MODEL_MARKERS
    )
    supports_reasoning_effort = _model_matches(model_id, _REASONING_EFFORT_MODEL_MARKERS)
    supports_reasoning_format = provider_id == "groq" and _model_matches(model_id, _GROQ_REASONING_FORMAT_MODEL_MARKERS)
    supports_include_reasoning = provider_id == "groq" and _model_matches(model_id, _GROQ_GPT_OSS_MODEL_MARKERS)

    # Groq Qwen3-32B accepts only ``none``/``default``; gpt-oss accepts
    # ``low``/``medium``/``high``. LM Studio is more permissive but
    # historically accepts the gpt-oss vocabulary across the board.
    if provider_id == "groq" and _model_matches(model_id, _QWEN3_REASONING_EFFORT_MODEL_MARKERS):
        reasoning_effort_enabled = "default"
        reasoning_effort_disabled = "none"
    elif provider_id == "groq" and _model_matches(model_id, _GROQ_GPT_OSS_MODEL_MARKERS):
        reasoning_effort_enabled = "medium"
        reasoning_effort_disabled = "low"
    else:
        reasoning_effort_enabled = "medium"
        reasoning_effort_disabled = "none"

    force_schema = provider_id == "lm_studio" and _model_matches(model_id, _LM_STUDIO_SCHEMA_MODEL_MARKERS)
    routes_to_reasoning = force_schema or supports_enable_thinking
    is_mtp = _model_matches(model_id, _MTP_MODEL_MARKERS)
    thinking_unsuppressable = provider_id == "lm_studio" and _model_matches(
        model_id, _THINKING_UNSUPPRESSABLE_MODEL_MARKERS
    )
    prefill_suppresses = provider_id == "lm_studio" and _model_matches(
        model_id, _LM_STUDIO_ASSISTANT_PREFILL_MODEL_MARKERS
    )

    return ProviderCapabilities(
        provider_id=provider_id,
        model_id=model_id,
        accepts_no_think_directive=accepts_no_think,
        supports_enable_thinking_kwarg=supports_enable_thinking,
        assistant_prefill_suppresses_thinking=prefill_suppresses,
        supports_reasoning_effort=supports_reasoning_effort,
        reasoning_effort_enabled_value=reasoning_effort_enabled,
        reasoning_effort_disabled_value=reasoning_effort_disabled,
        supports_reasoning_format=supports_reasoning_format,
        supports_include_reasoning=supports_include_reasoning,
        force_text_schema=force_schema,
        schema_min_output_tokens=LM_STUDIO_SCHEMA_MIN_OUTPUT_TOKENS,
        routes_output_to_reasoning_content=routes_to_reasoning,
        is_mtp_model=is_mtp,
        thinking_unsuppressable=thinking_unsuppressable,
    )


__all__ = [
    "LM_STUDIO_SCHEMA_MIN_OUTPUT_TOKENS",
    "ProviderCapabilities",
    "REASONING_MESSAGE_FIELDS",
    "TEXT_RESPONSE_FORMAT",
    "resolve_capabilities",
]
