"""Provider-neutral generation output cleanup."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class GenerationResult:
    """Holds separated content and optional model reasoning."""

    content: str
    reasoning: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


def parse_generation_output(text: str) -> GenerationResult:
    """Separate reasoning blocks and strip common prompt/template leaks."""
    if not text:
        return GenerationResult(content="")

    reasoning = None
    content = text

    matches = list(re.finditer(r"<think>(.*?)</think>", text, flags=re.DOTALL))
    if matches:
        reasoning_parts = [match.group(1).strip() for match in matches if match.group(1).strip()]
        reasoning = "\n\n".join(reasoning_parts) if reasoning_parts else None
        content = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    elif "<think>" in text:
        parts = text.split("<think>", 1)
        content = parts[0]
        reasoning = parts[1].strip() + " [REASONING TRUNCATED]"

    content = content.replace("<<<BEGIN TRANSCRIPT>>>", "").replace("<<<END TRANSCRIPT>>>", "")

    for marker in [
        "<|im_end|>",
        "<|eot_id|>",
        "<|endoftext|>",
        "</s>",
        "<|im_start|>",
    ]:
        if marker in content:
            content = content.split(marker)[0]

    content = re.sub(r"^(system|user|assistant)\s*\n", "", content, count=1)
    content = re.sub(r"^/no_think\s*", "", content)

    return GenerationResult(content=content.strip(), reasoning=reasoning)
