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

    def _calculate_dynamic_max_tokens(self, input_token_count: int) -> int:
        """Calculate dynamic max_length based on input size."""
        base_count = max(1, input_token_count)
        padding = max(self.MIN_PADDING_TOKENS, int(base_count * self.SCALING_FACTOR))
        return min(self.HARD_MAX_OUTPUT_TOKENS, base_count + padding)

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
        content = content.replace("<<<BEGIN TRANSCRIPT>>>", "").replace(
            "<<<END TRANSCRIPT>>>", ""
        )

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

    def _get_few_shot_examples(
        self, level_idx: int, has_instructions: bool = False
    ) -> str:
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
    ) -> list[dict[str, str]]:
        """Format input as ChatML messages using the 4-layer enforcement model."""

        # Resolve level
        mapping = {"MINIMAL": 0, "BALANCED": 1, "STRONG": 2, "OVERKILL": 4}
        level_idx = 1
        if isinstance(profile, int):
            level_idx = profile
        elif isinstance(profile, str) and profile.upper() in mapping:
            level_idx = mapping[profile.upper()]

        level_data = (
            self.levels.get(level_idx)
            or self.levels.get(str(level_idx))
            or self.levels.get(1)
            or {}
        )

        # Extract components
        invariants_text = "\n".join(f"- {i}" for i in self.invariants)
        role = level_data.get("role", "You are a text editor.")
        permitted = "\n".join(f"- {p}" for p in level_data.get("permitted", []))
        prohibited = "\n".join(f"- {p}" for p in level_data.get("prohibited", []))
        directive = level_data.get("directive", "Clean the text.")

        examples = self._get_few_shot_examples(
            level_idx, has_instructions=bool(user_instructions.strip())
        )

        system_content = f"""{self.system_prompt}

OPERATIONAL CONSTRAINTS:
{invariants_text}""".strip()

        task_instructions = ""
        if user_instructions and user_instructions.strip():
            task_instructions = f"User Instructions: {user_instructions.strip()}\n"

        user_content = f"""/no_think

# YOUR ROLE: {role}

# PERMITTED ACTIONS:
{permitted}

# PROHIBITED ACTIONS:
{prohibited}

# PRIMARY DIRECTIVE:
{directive}

{examples}

--- ACTUAL TASK ---
Input:
<<<BEGIN TRANSCRIPT>>>
{user_text}
<<<END TRANSCRIPT>>>
{task_instructions}Output:""".strip()

        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]

    def refine(
        self,
        text: str,
        profile: str | int = "BALANCED",
        user_instructions: str = "",
        temperature: float = 0.0,
    ) -> GenerationResult:
        """
        Refine the input text using the loaded model.

        Args:
            text: Raw input text.
            profile: Refinement intensity level (0-4 or name string).
            user_instructions: Optional specific instructions from the user.
            temperature: Sampling temperature. 0.0 = deterministic.

        Returns:
            GenerationResult containing refined text and optional reasoning.
        """
        if not text or not text.strip():
            return GenerationResult(content=text)

        messages = self._format_prompt(text, profile, user_instructions)

        # Estimate input tokens for dynamic max calculation
        prompt_text = " ".join(m["content"] for m in messages)
        input_count = len(prompt_text.split()) * 2  # rough estimate
        max_new_tokens = self._calculate_dynamic_max_tokens(input_count)

        logger.debug(
            "Refining ~%d estimated tokens with limit of %d new tokens.",
            input_count,
            max_new_tokens,
        )

        response = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=max_new_tokens,
            temperature=max(temperature, 0.01),  # llama.cpp needs >0
            top_k=1 if temperature == 0 else 50,
            stop=["<|im_end|>", "<|endoftext|>"],
        )

        output_text = response["choices"][0]["message"]["content"]
        return self._parse_output(output_text)

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
            messages=messages,
            max_tokens=max_tokens,
            temperature=max(temperature, 0.01),
            top_k=50 if temperature > 0 else 1,
            stop=["<|im_end|>", "<|endoftext|>"],
        )

        output_text = response["choices"][0]["message"]["content"]
        return self._parse_output(output_text)
