"""
Refinement Engine using llama-cpp-python (llama.cpp).

Wraps a GGUF model to provide a simple refine() interface for text cleanup.
Uses instruction-following (ChatML) prompting with layered enforcement.
"""

import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class GenerationResult:
    """Holds the separated content and reasoning from a model generation."""

    content: str
    reasoning: str | None = None


class RefinementEngine:
    """
    Refinement Engine using llama-cpp-python.

    Loads a GGUF model and provides refine/generate_custom interfaces.
    """

    # Constants for dynamic scaling
    HARD_MAX_OUTPUT_TOKENS = 16384
    MIN_PADDING_TOKENS = 150
    SCALING_FACTOR = 0.5
    # Fixed thinking budget: reserved exclusively for <think> reasoning overhead.
    # This is separate from the output budget so thinking never cannibalizes the
    # final answer.  2048 tokens ≈ ~1500 words of internal reasoning — enough for
    # Qwen3 to think through even complex multi-sentence transcripts.
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
            model_path: Path to the GGUF model file.
            system_prompt: Fallback system identity.
            invariants: Global rules prepended to every prompt.
            levels: Layered definitions for refinement levels (0-4).
            n_gpu_layers: GPU layers to offload (-1 = all, 0 = CPU only).
            n_ctx: Context window size.
        """
        from llama_cpp import Llama

        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        self.system_prompt = system_prompt
        self.invariants = invariants or []
        self.levels = levels or {}

        logger.info("Loading GGUF model from %s...", model_path)
        start_time = time.perf_counter()

        self.llm = Llama(
            model_path=str(model_path),
            n_gpu_layers=n_gpu_layers,
            n_ctx=n_ctx,
            verbose=False,
        )

        load_time = time.perf_counter() - start_time
        logger.info("Refinement Engine loaded in %.2fs", load_time)

    def _calculate_dynamic_max_tokens(self, input_token_count: int, use_thinking: bool = False) -> int:
        """Calculate max new tokens, keeping thinking budget separate from output budget.

        llama.cpp's max_tokens is a single pool covering ALL generated tokens —
        thinking blocks AND the final answer.  To prevent the model's reasoning
        from cannibalizing the output, we allocate budgets independently:

            output_budget  = input_tokens + padding  (scales with text length)
            thinking_budget = THINKING_BUDGET_TOKENS  (fixed, thinking mode only)
            total           = output_budget + thinking_budget

        The thinking budget is a fixed constant so shorter inputs still get the
        full reasoning room they need.  The <think> blocks are stripped by
        _parse_output() before the text reaches the user.
        """
        base_count = max(1, input_token_count)
        output_budget = base_count + max(self.MIN_PADDING_TOKENS, int(base_count * self.SCALING_FACTOR))
        thinking_budget = self.THINKING_BUDGET_TOKENS if use_thinking else 0
        return min(self.HARD_MAX_OUTPUT_TOKENS, output_budget + thinking_budget)

    def _parse_output(self, text: str) -> GenerationResult:
        """Separate <think>...</think> blocks from model output."""
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

        return GenerationResult(content=content.strip(), reasoning=reasoning)

    def _get_few_shot_examples(self, level_idx: int, has_instructions: bool = False) -> str:
        """Get few-shot examples to guide the model."""
        base = "\n\n--- EXAMPLES OF DESIRED BEHAVIOR ---\n"

        instruction_example = ""
        if has_instructions:
            instruction_example = """
Input:
<<<BEGIN TRANSCRIPT>>>
The car is blue and the house is red.
<<<END TRANSCRIPT>>>
User Instructions: Replace colors with [COLOR].
Output:
The car is [COLOR] and the house is [COLOR].
"""

        examples = {
            0: """
Input:
<<<BEGIN TRANSCRIPT>>>
hello this is a test. i am writinge with some typos.
<<<END TRANSCRIPT>>>
Output:
Hello this is a test. I am writing with some typos.

Input:
<<<BEGIN TRANSCRIPT>>>
So, um, basically we should go.
<<<END TRANSCRIPT>>>
Output:
So, um, basically we should go.
""",
            1: """
Input:
<<<BEGIN TRANSCRIPT>>>
hello this is a test. i am writinge with some typos.
<<<END TRANSCRIPT>>>
Output:
Hello this is a test. I am writing with some typos.

Input:
<<<BEGIN TRANSCRIPT>>>
I I want to go to the the park.
<<<END TRANSCRIPT>>>
Output:
I want to go to the park.
""",
            2: """
Input:
<<<BEGIN TRANSCRIPT>>>
It was raining really hard and the car broke down and we were stuck there for hours.
<<<END TRANSCRIPT>>>
Output:
It was raining really hard. The car broke down, and we were stuck there for hours.
""",
            3: """
Input:
<<<BEGIN TRANSCRIPT>>>
I want to make the app better so people like it more.
<<<END TRANSCRIPT>>>
Output:
I intend to enhance the application to maximize user engagement and satisfaction.
""",
            4: """
Input:
<<<BEGIN TRANSCRIPT>>>
The meeting was okay but we need to talk about the budget cause it's too high.
<<<END TRANSCRIPT>>>
Output:
While the meeting was productive, we must address the budget, which is currently excessive.
""",
        }

        return base + examples.get(level_idx, "") + instruction_example

    def _format_prompt(
        self,
        user_text: str,
        profile: str | int = "BALANCED",
        user_instructions: str = "",
        use_thinking: bool = False,
    ) -> list[dict[str, str]]:
        """Format input as ChatML messages.

        Two modes:
        - **Default (no custom instructions)**: Grammar-fix pipeline with
          invariants enforcing meaning-preservation and output discipline.
        - **Custom instructions provided**: The user's instructions become
          the ENTIRE task.  Invariants are NOT sent — the user is in control
          and the safety rails would only confuse the model or fight the
          user's intent.

        The `profile` argument is retained for API compatibility but ignored.
        """

        custom = user_instructions.strip() if user_instructions else ""

        if custom:
            # User provided explicit instructions — they take FULL precedence.
            # No invariants, no default rules, just the system identity + their task.
            system_content = self.system_prompt
            task_directive = custom
        else:
            # Default grammar-fix mode: invariants enforce discipline.
            invariants_text = "\n".join(f"- {i}" for i in self.invariants)
            system_content = f"""{self.system_prompt}

Rules:
{invariants_text}
- Output ONLY the corrected text. No explanations, no preamble.""".strip()
            task_directive = "Fix all grammar, spelling, punctuation, and capitalization errors."

        # Thinking directive: /no_think suppresses reasoning for speed and fidelity.
        think_directive = "" if use_thinking else "/no_think\n\n"

        user_content = f"""{think_directive}{task_directive}

Text:
{user_text}""".strip()

        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]

    def refine(
        self,
        text: str,
        profile: str | int = "BALANCED",
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
            profile: Refinement intensity level (0-4 or name string).
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

        messages = self._format_prompt(text, profile, user_instructions, use_thinking=use_thinking)

        # Estimate input tokens for dynamic max calculation
        prompt_text = " ".join(m["content"] for m in messages)
        input_count = len(prompt_text.split()) * 2  # rough estimate
        max_new_tokens = self._calculate_dynamic_max_tokens(input_count, use_thinking=use_thinking)

        logger.debug(
            "Refining ~%d estimated tokens (thinking=%s) with limit of %d new tokens.",
            input_count,
            use_thinking,
            max_new_tokens,
        )

        response = self.llm.create_chat_completion(
            messages=messages,  # type: ignore[arg-type]
            max_tokens=max_new_tokens,
            temperature=max(temperature, 0.01),  # llama.cpp needs >0
            top_p=top_p,
            top_k=top_k,
            repeat_penalty=1.0,
            stop=["<|im_end|>", "<|endoftext|>"],
        )

        output_text = response["choices"][0]["message"]["content"]  # type: ignore[index]
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
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"/no_think\n\n{user_prompt}"},
        ]

        response = self.llm.create_chat_completion(
            messages=messages,  # type: ignore[arg-type]
            max_tokens=max_tokens,
            temperature=max(temperature, 0.01),
            top_k=50 if temperature > 0 else 1,
            stop=["<|im_end|>", "<|endoftext|>"],
        )

        output_text = response["choices"][0]["message"]["content"]  # type: ignore[index]
        return self._parse_output(output_text)
