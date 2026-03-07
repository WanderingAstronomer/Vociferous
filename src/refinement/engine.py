"""
Refinement Engine using CTranslate2 Generator.

Wraps a CTranslate2-format model to provide a simple refine() interface for
text cleanup. Uses instruction-following (ChatML) prompting with layered
enforcement. Tokenization is handled by the HuggingFace `tokenizers` library.
"""

import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.refinement.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class GenerationResult:
    """Holds the separated content and reasoning from a model generation."""

    content: str
    reasoning: str | None = None


class RefinementEngine:
    """
    Refinement Engine using CTranslate2 Generator.

    Loads a CT2-format model and provides refine/generate_custom interfaces.
    Tokenization uses the HuggingFace `tokenizers` library (Rust-based, no PyTorch).
    """

    # Constants for dynamic scaling
    HARD_MAX_OUTPUT_TOKENS = 16384
    MIN_PADDING_TOKENS = 150
    SCALING_FACTOR = 0.5
    # Fixed thinking budget: reserved exclusively for <think> reasoning overhead.
    THINKING_BUDGET_TOKENS = 2048

    def __init__(
        self,
        model_path: Path | str,
        system_prompt: str = "",
        invariants: list[str] | None = None,
        levels: dict[int | str, dict[str, Any]] | None = None,
        n_gpu_layers: int = -1,
        n_ctx: int = 8192,
    ):
        """
        Initialize the Refinement engine.

        Args:
            model_path: Path to the CT2 model directory.
            system_prompt: Fallback system identity.
            invariants: Global rules prepended to every prompt.
            levels: Layered definitions for refinement levels (0-4).
            n_gpu_layers: GPU layers to offload (-1 = all/cuda, 0 = CPU only).
            n_ctx: Context window size (preserved for API compat; CT2 uses model config).
        """
        import ctranslate2
        from tokenizers import Tokenizer

        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"Model directory not found: {model_path}")

        self.system_prompt = system_prompt
        self.invariants = invariants or []
        self.levels = levels or {}
        self.prompt_builder = PromptBuilder(
            system_prompt=system_prompt,
            invariants=self.invariants,
        )

        # Map n_gpu_layers to CT2 device
        if n_gpu_layers == 0:
            ct2_device = "cpu"
        else:
            try:
                ct2_device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
            except Exception:
                ct2_device = "cpu"

        logger.info("Loading CT2 Generator model from %s (device=%s)...", model_path, ct2_device)
        start_time = time.perf_counter()

        self.generator = ctranslate2.Generator(
            str(model_path),
            device=ct2_device,
        )

        # Load tokenizer from the model directory
        tokenizer_path = model_path / "tokenizer.json"
        if not tokenizer_path.exists():
            raise FileNotFoundError(
                f"tokenizer.json not found in {model_path}. CT2 model directories must include the tokenizer."
            )
        self.tokenizer = Tokenizer.from_file(str(tokenizer_path))

        # Pre-resolve special token IDs for stop conditions
        self._im_end_id = self.tokenizer.token_to_id("<|im_end|>")
        self._eos_id = self.tokenizer.token_to_id("<|endoftext|>")
        self._end_tokens = [tid for tid in [self._im_end_id, self._eos_id] if tid is not None]

        load_time = time.perf_counter() - start_time
        logger.info("Refinement Engine loaded in %.2fs", load_time)

    def _calculate_dynamic_max_tokens(self, input_token_count: int, use_thinking: bool = False) -> int:
        """Calculate max new tokens, keeping thinking budget separate from output budget.

        CTranslate2's max_length applies to ALL generated tokens — thinking
        blocks AND the final answer.  To prevent the model's reasoning from
        cannibalizing the output, we allocate budgets independently:

            output_budget  = input_tokens + padding  (scales with text length)
            thinking_budget = THINKING_BUDGET_TOKENS  (fixed, thinking mode only)
            total           = output_budget + thinking_budget
        """
        base_count = max(1, input_token_count)
        output_budget = base_count + max(self.MIN_PADDING_TOKENS, int(base_count * self.SCALING_FACTOR))
        thinking_budget = self.THINKING_BUDGET_TOKENS if use_thinking else 0
        return min(self.HARD_MAX_OUTPUT_TOKENS, output_budget + thinking_budget)

    def _parse_output(self, text: str) -> GenerationResult:
        """Separate <think>...</think> blocks and strip prompt artifacts from model output."""
        if not text:
            return GenerationResult(content="")

        reasoning = None
        content = text

        # Extract complete think blocks
        match = re.search(r"<think>(.*?)</think>", text, flags=re.DOTALL)
        if match:
            reasoning = match.group(1).strip()
            content = text.replace(match.group(0), "")
        elif "<think>" in text:
            parts = text.split("<think>", 1)
            content = parts[0]
            reasoning = parts[1].strip() + " [REASONING TRUNCATED]"

        # Strip transcript markers
        content = content.replace("<<<BEGIN TRANSCRIPT>>>", "").replace("<<<END TRANSCRIPT>>>", "")

        # Truncate at leaked end tokens
        for marker in [
            "<|im_end|>",
            "<|eot_id|>",
            "<|endoftext|>",
            "</s>",
            "<|im_start|>",
        ]:
            if marker in content:
                content = content.split(marker)[0]

        # Strip leaked ChatML role markers (e.g. "system\n..." or "assistant\n...")
        # that survive after the <|im_start|> token itself was already removed.
        content = re.sub(r"^(system|user|assistant)\s*\n", "", content, count=1)

        # Strip /no_think directive if model echoed it back
        content = re.sub(r"^/no_think\s*", "", content)

        return GenerationResult(content=content.strip(), reasoning=reasoning)

    def _get_few_shot_examples(self, level_idx: int, has_instructions: bool = False) -> str:
        """Delegate to PromptBuilder."""
        return PromptBuilder.get_few_shot_examples(level_idx, has_instructions)

    def _format_prompt(
        self,
        user_text: str,
        user_instructions: str = "",
        use_thinking: bool = False,
    ) -> list[dict[str, str]]:
        """Delegate to PromptBuilder."""
        return self.prompt_builder.build_refinement_messages(user_text, user_instructions, use_thinking)

    def _messages_to_chatml(self, messages: list[dict[str, str]]) -> str:
        """Delegate to PromptBuilder."""
        return PromptBuilder.messages_to_chatml(messages)

    def refine(
        self,
        text: str,
        user_instructions: str = "",
        temperature: float = 0.05,
        top_p: float = 0.8,
        top_k: int = 20,
        use_thinking: bool = False,
    ) -> GenerationResult:
        """
        Refine the input text using the loaded model.

        Args:
            text: Raw input text.
            user_instructions: Optional specific instructions from the user.
            temperature: Sampling temperature (low for high-fidelity minimal edits).
            top_p: Nucleus sampling threshold (conservative to reduce drift).
            top_k: Top-k sampling (Qwen3 baseline: 20).
            use_thinking: Allow model to reason in <think> blocks before output.

        Returns:
            GenerationResult containing refined text and optional reasoning.
        """
        if not text or not text.strip():
            return GenerationResult(content=text)

        messages = self._format_prompt(text, user_instructions, use_thinking=use_thinking)

        # Tokenize the ChatML-formatted prompt
        chatml_string = self._messages_to_chatml(messages)
        encoded = self.tokenizer.encode(chatml_string)
        prompt_tokens = encoded.tokens  # CT2 generate_batch() expects List[str], not int IDs

        # Calculate dynamic max tokens based on input size
        max_new_tokens = self._calculate_dynamic_max_tokens(len(prompt_tokens), use_thinking=use_thinking)

        logger.debug(
            "Refining %d prompt tokens (thinking=%s) with limit of %d new tokens.",
            len(prompt_tokens),
            use_thinking,
            max_new_tokens,
        )

        # CT2 needs temperature > 0 for sampling
        effective_temp = max(temperature, 0.01)

        results = self.generator.generate_batch(
            [prompt_tokens],
            max_length=max_new_tokens,
            sampling_temperature=effective_temp,
            sampling_topp=top_p,
            sampling_topk=top_k,
            repetition_penalty=1.0,
            end_token=self._end_tokens,
            include_prompt_in_result=False,
        )

        output_ids = results[0].sequences_ids[0]
        output_text = self.tokenizer.decode(output_ids)
        result = self._parse_output(output_text)

        # Fallback: if model emitted only <think> reasoning with no final content,
        # return the original text rather than an empty string.
        if not result.content.strip():
            logger.warning(
                "Refinement produced empty content (model may have exhausted tokens in reasoning). "
                "Returning original text."
            )
            return GenerationResult(content=text, reasoning=result.reasoning)

        return result

    def generate_custom(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 150,
        temperature: float = 0.7,
    ) -> GenerationResult:
        """
        Generate text using a custom system and user prompt.

        Args:
            system_prompt: The system instruction.
            user_prompt: The user input/query.
            max_tokens: Maximum new tokens to generate.
            temperature: Sampling temperature.

        Returns:
            GenerationResult with 'content' and 'reasoning'.
        """
        messages = self.prompt_builder.build_custom_messages(system_prompt, user_prompt)

        chatml_string = self._messages_to_chatml(messages)
        encoded = self.tokenizer.encode(chatml_string)
        prompt_tokens = encoded.tokens  # CT2 generate_batch() expects List[str], not int IDs

        effective_temp = max(temperature, 0.01)

        results = self.generator.generate_batch(
            [prompt_tokens],
            max_length=max_tokens,
            sampling_temperature=effective_temp,
            sampling_topk=50 if temperature > 0 else 1,
            end_token=self._end_tokens,
            include_prompt_in_result=False,
        )

        output_ids = results[0].sequences_ids[0]
        output_text = self.tokenizer.decode(output_ids)
        return self._parse_output(output_text)
