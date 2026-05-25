"""Provider Protocol and shared error type for refinement providers."""

from __future__ import annotations

from typing import Protocol

from src.refinement.output_parser import GenerationResult


class ProviderRequestError(RuntimeError):
    """Provider request failed with an HTTP-aware status code."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


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
    ) -> GenerationResult: ...
    def generate_custom(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 150,
        temperature: float = 0.7,
        use_thinking: bool = False,
    ) -> GenerationResult: ...
