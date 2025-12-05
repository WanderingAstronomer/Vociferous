from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from chatterbug.polish.base import Polisher


@dataclass(frozen=True)
class LlamaPolisherOptions:
    model_path: Path
    max_tokens: int = 128
    temperature: float = 0.2
    gpu_layers: int = 0
    context_length: int = 2048
    system_prompt: str = (
        "Fix grammar, spacing, and punctuation in the following text. "
        "Return ONLY the corrected text with no explanations, summaries, or additional commentary."
    )


class LlamaCppPolisher(Polisher):
    """Polisher backed by llama-cpp using a small quantized model."""

    def __init__(self, options: LlamaPolisherOptions, llama_loader: Callable[..., Any] | None = None) -> None:
        if llama_loader is None:
            try:
                import os
                os.environ.setdefault("LLAMA_CPP_LOG_LEVEL", "ERROR")
                from llama_cpp import Llama  # type: ignore

                llama_loader = Llama
            except ImportError as exc:  # pragma: no cover - dependency guard
                raise RuntimeError("llama-cpp-python is required; pip install .[polish]") from exc

        assert llama_loader is not None
        self._options = options
        self._llama: Any = llama_loader(
            model_path=str(options.model_path),
            n_ctx=options.context_length,
            n_gpu_layers=options.gpu_layers,
            logits_all=False,
            verbose=False,
        )

    def polish(self, text: str) -> str:
        options = self._options
        prompt = self._build_prompt(text)
        result = self._llama(
            prompt,
            max_tokens=options.max_tokens,
            temperature=options.temperature,
            stop=None,
        )
        if not isinstance(result, dict) or "choices" not in result:
            return text
        choices = result.get("choices")
        if not choices:
            return text
        message = choices[0].get("text")
        return message.strip() if isinstance(message, str) else text

    def _build_prompt(self, text: str) -> str:
        trimmed = text[-2000:]
        return (
            f"System: {self._options.system_prompt}\n"
            f"User: {trimmed}\n"
            "Assistant:"
        )
