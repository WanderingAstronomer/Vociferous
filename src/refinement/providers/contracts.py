"""Provider Protocol, request policy, and shared provider error type."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from src.refinement.output_parser import GenerationResult


class ProviderRequestError(RuntimeError):
    """Provider request failed with an HTTP-aware status code."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class GenerationTaskKind(StrEnum):
    """High-level task shape for provider request policy translation."""

    REFINEMENT = "refinement"
    TITLE = "title"
    ANALYTICS = "analytics"
    FREEFORM = "freeform"


class ReasoningPolicy(StrEnum):
    """Requested reasoning behavior from the product point of view.

    Disabled means Vociferous wants final output only and provider adapters
    should suppress reasoning when the backend exposes a real control. Hidden
    means the provider may reason internally but must return final output only.
    Visible is legacy/debug behavior; it may preserve provider reasoning fields
    in ``GenerationResult.reasoning`` but never changes the user-facing content.
    """

    DISABLED = "disabled"
    HIDDEN = "hidden"
    VISIBLE = "visible"


class ResponseShape(StrEnum):
    """Expected response envelope."""

    TEXT = "text"
    JSON_OBJECT = "json_object"


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """Provider-neutral generation request policy.

    ``visible_output_tokens`` is the useful-output budget. Provider adapters may
    add hidden overhead for reasoning backends, but callers should not need to
    know provider-specific hidden-budget mechanics.
    """

    task_kind: GenerationTaskKind
    visible_output_tokens: int
    reasoning_policy: ReasoningPolicy = ReasoningPolicy.DISABLED
    response_shape: ResponseShape = ResponseShape.TEXT

    @classmethod
    def for_refinement(cls, *, visible_output_tokens: int, use_thinking: bool = False) -> "GenerationRequest":
        return cls(
            task_kind=GenerationTaskKind.REFINEMENT,
            visible_output_tokens=visible_output_tokens,
            reasoning_policy=ReasoningPolicy.VISIBLE if use_thinking else ReasoningPolicy.DISABLED,
        )

    @classmethod
    def for_custom(
        cls,
        *,
        visible_output_tokens: int,
        use_thinking: bool = False,
        task_kind: GenerationTaskKind | str = GenerationTaskKind.FREEFORM,
        reasoning_policy: ReasoningPolicy | str | None = None,
        response_shape: ResponseShape | str = ResponseShape.TEXT,
    ) -> "GenerationRequest":
        resolved_reasoning = _coerce_reasoning_policy(reasoning_policy)
        if resolved_reasoning is None:
            resolved_reasoning = ReasoningPolicy.VISIBLE if use_thinking else ReasoningPolicy.DISABLED
        return cls(
            task_kind=_coerce_task_kind(task_kind),
            visible_output_tokens=visible_output_tokens,
            reasoning_policy=resolved_reasoning,
            response_shape=_coerce_response_shape(response_shape),
        )

    @property
    def use_thinking(self) -> bool:
        """Legacy compatibility: visible reasoning maps to old True."""
        return self.reasoning_policy == ReasoningPolicy.VISIBLE

    @property
    def final_output_only(self) -> bool:
        return self.reasoning_policy in {ReasoningPolicy.DISABLED, ReasoningPolicy.HIDDEN}

    def to_runtime_summary(self) -> dict[str, object]:
        return {
            "task_kind": self.task_kind.value,
            "visible_output_tokens": self.visible_output_tokens,
            "reasoning_policy": self.reasoning_policy.value,
            "response_shape": self.response_shape.value,
        }


def _coerce_task_kind(value: GenerationTaskKind | str) -> GenerationTaskKind:
    if isinstance(value, GenerationTaskKind):
        return value
    return GenerationTaskKind(str(value))


def _coerce_reasoning_policy(value: ReasoningPolicy | str | None) -> ReasoningPolicy | None:
    if value is None:
        return None
    if isinstance(value, ReasoningPolicy):
        return value
    return ReasoningPolicy(str(value))


def _coerce_response_shape(value: ResponseShape | str) -> ResponseShape:
    if isinstance(value, ResponseShape):
        return value
    return ResponseShape(str(value))


class RefinementProvider(Protocol):
    """Provider contract consumed by SLMRuntime."""

    @property
    def provider_id(self) -> str: ...

    def load(self) -> None: ...
    def unload(self) -> None: ...
    def get_runtime_summary(self) -> dict[str, object]: ...
    def refine(
        self,
        text: str,
        *,
        instructions: str = "",
        temperature: float,
        top_p: float,
        top_k: int,
        repetition_penalty: float,
        use_thinking: bool,
        allow_skip: bool = True,
        request: GenerationRequest | None = None,
    ) -> GenerationResult: ...
    def generate_custom(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 150,
        temperature: float = 0.7,
        use_thinking: bool = False,
        request: GenerationRequest | None = None,
    ) -> GenerationResult: ...
