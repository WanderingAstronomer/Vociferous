import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import ctranslate2
    from tokenizers import Tokenizer
except ImportError:
    ctranslate2 = None
    Tokenizer = None

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class GenerationResult:
    """Holds the separated content and reasoning from a generic model generation."""

    content: str
    reasoning: str | None = None


class RefinementEngine:
    """
    Refinement Engine using CTranslate2 and Qwen3-4B-Instruct.

    Wraps the loaded model and tokenizer to provide a simple refine() interface.
    Uses instruction-following (ChatML-like) prompting for granular control.
    """

    # Constants for dynamic scaling
    HARD_MAX_OUTPUT_TOKENS = 16384  # (~1 hour of fluent speech)
    MIN_PADDING_TOKENS = 150
    SCALING_FACTOR = 0.5  # 50% headroom

    def __init__(
        self,
        model_path: Path,
        tokenizer_path: Path,
        system_prompt: str = "",
        invariants: list[str] | None = None,
        levels: dict[int | str, dict[str, Any]] | None = None,
        device: str = "cpu",
        device_index: int = 0,
        prompt_format: str = "chatml",
    ):
        """
        Initialize the Refinement engine.

        Args:
            model_path: Path to the directory containing CTranslate2 model artifacts
            tokenizer_path: Path to the tokenizer.json file
            system_prompt: Fallback system identity
            invariants: Global rules prepended to every prompt
            levels: Layered definitions for refinement levels (0-4)
            device: 'cpu' or 'cuda'
            device_index: Index of GPU to use (default 0)
            prompt_format: 'chatml' or 'llama3'
        """
        if ctranslate2 is None or Tokenizer is None:
            raise ImportError("ctranslate2 and tokenizers are required for Refinement")

        if not model_path.exists():
            raise FileNotFoundError(f"Model path not found: {model_path}")
        if not tokenizer_path.exists():
            raise FileNotFoundError(f"Tokenizer path not found: {tokenizer_path}")

        self.system_prompt = system_prompt
        self.invariants = invariants or []
        self.levels = levels or {}
        self.prompt_format = prompt_format

        logger.info(
            f"Loading Refinement Engine from {model_path} on {device}:{device_index}..."
        )
        start_time = time.perf_counter()

        # Load Tokenizer
        self.tokenizer = Tokenizer.from_file(str(tokenizer_path))

        # Load Model
        # Optimize compute_type for device
        # CPU: "int8" is most efficient for quantized models
        # GPU (CUDA): "int8_float16" is standard for int8 weights + fp16 math (Tensor Cores)
        # Using pure "int8" on GPU can sometimes be slower or unsupported depending on arch
        compute_type = "int8_float16" if device == "cuda" else "int8"

        logger.info(
            f"Initializing CTranslate2 Generator on {device} with {compute_type}..."
        )

        self.generator = ctranslate2.Generator(
            str(model_path),
            device=device,
            device_index=[device_index],
            compute_type=compute_type,
        )

        # Get stop token ID for ChatML/Instruct models
        # Check for multiple possible stop tokens (ChatML, Llama 3, etc.)
        stop_tokens = [
            "<|im_end|>",  # ChatML (Qwen, etc.)
            "<|eot_id|>",  # Llama 3
            "<|end_of_text|>",  # Some newer models
            "<|endoftext|>",  # Standard base models
            "</s>",  # Llama 2 / Mistral / others
        ]
        self.end_token_id = []
        for token in stop_tokens:
            tid = self.tokenizer.token_to_id(token)
            if tid is not None:
                self.end_token_id.append(tid)

        if self.end_token_id:
            logger.debug(f"Using end_token_id(s): {self.end_token_id}")
        else:
            self.end_token_id = None

        load_time = time.perf_counter() - start_time
        logger.info(f"Refinement Engine loaded in {load_time:.2f}s")

    def _calculate_dynamic_max_tokens(self, input_token_count: int) -> int:
        """
        Calculate dynamic max_length based on a sliding scale padding model.
        Small inputs get a baseline buffer, large inputs get proportional headroom,
        capped at HARD_MAX_OUTPUT_TOKENS.
        """
        # Ensure at least 1 token as per user requirement
        base_count = max(1, input_token_count)

        # Inverted logarithm / accelerating scale logic:
        # We afford more absolute padding as the input grows, but also ensure
        # that roughly doubling the size is allowed for smaller snippets.
        padding = max(self.MIN_PADDING_TOKENS, int(base_count * self.SCALING_FACTOR))

        # Total allowed NEW tokens is input + padding, clamped to hard maximum.
        # This ensures if you input 10k tokens, you can get 15k+ back (if it fits in context)
        # but prevents runaway GPU usage for tiny 10-token inputs.
        dynamic_limit = min(self.HARD_MAX_OUTPUT_TOKENS, base_count + padding)

        return dynamic_limit

    def _parse_output(self, text: str) -> GenerationResult:
        """
        Separate <think>...</think> blocks and transcript markers from the model output.
        Returns a GenerationResult with 'content' and 'reasoning'.
        """
        if not text:
            return GenerationResult(content="")

        reasoning = None
        content = text

        # 1. Extract complete think blocks
        # Capture the first think block if present
        match = re.search(r"<think>(.*?)</think>", text, flags=re.DOTALL)
        if match:
            reasoning = match.group(1).strip()
            # Remove the thinking block from content
            content = text.replace(match.group(0), "")
        else:
            # 2. Check for truncated think block (start but no end)
            if "<think>" in text:
                parts = text.split("<think>", 1)
                # content is anything BEFORE the think block
                content = parts[0]
                # reasoning is what came after (and it was truncated)
                reasoning = parts[1].strip() + " [REASONING TRUNCATED]"

        # 3. Strip accidental echo of transcript markers
        # Some models echo the delimiters in the prompt
        content = content.replace("<<<BEGIN TRANSCRIPT>>>", "").replace(
            "<<<END TRANSCRIPT>>>", ""
        )

        # 4. Truncate at common end tokens if they leaked as literal strings
        # (Defensive check in case tokenizer IDs did not match for some reason)
        leaked_markers = [
            "<|im_end|>",
            "<|eot_id|>",
            "<|end_of_text|>",
            "<|endoftext|>",
            "</s>",
            "<|im_start|>",
        ]
        for marker in leaked_markers:
            if marker in content:
                content = content.split(marker)[0]

        return GenerationResult(content=content.strip(), reasoning=reasoning)

    def _get_few_shot_examples(
        self, level_idx: int, has_instructions: bool = False
    ) -> str:
        """Get few-shot examples to guide the model without thinking mode."""
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

        if level_idx == 0:  # Literal
            return (
                base
                + """
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
"""
                + instruction_example
            )

        elif level_idx == 1:  # Structural
            return (
                base
                + """
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
"""
                + instruction_example
            )

        elif level_idx == 2:  # Neutral
            return (
                base
                + """
Input:
<<<BEGIN TRANSCRIPT>>>
It was raining really hard and the car broke down and we were stuck there for hours.
<<<END TRANSCRIPT>>>
Output:
It was raining really hard. The car broke down, and we were stuck there for hours.
"""
                + instruction_example
            )

        elif level_idx == 3:  # Intent
            return (
                base
                + """
Input:
<<<BEGIN TRANSCRIPT>>>
I want to make the app better so people like it more.
<<<END TRANSCRIPT>>>
Output:
I intend to enhance the application to maximize user engagement and satisfaction.
"""
                + instruction_example
            )

        elif level_idx == 4:  # Overkill
            return (
                base
                + """
Input:
<<<BEGIN TRANSCRIPT>>>
The meeting was okay but we need to talk about the budget cause it's too high.
<<<END TRANSCRIPT>>>
Output:
While the meeting was productive, we must address the budget, which is currently excessive.

Input:
<<<BEGIN TRANSCRIPT>>>
i think we should maybe try to use the newer model because it is faster and better at some tasks but we have to check the cost.
<<<END TRANSCRIPT>>>
Output:
We should evaluate the newer model; although cost-sensitive, its performance and speed offer significant advantages.
"""
                + instruction_example
            )

        return ""

    def _apply_template(self, system: str, user: str) -> str:
        """Apply the configured chat template to the system and user messages."""
        if self.prompt_format == "llama3":
            # Llama 3 Instruct Format
            return (
                f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
                f"{system}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n"
                f"{user}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
            )
        else:
            # Default to ChatML (Qwen, etc.)
            return (
                f"<|im_start|>system\n{system}\n<|im_end|>\n"
                f"<|im_start|>user\n{user}\n<|im_end|>\n"
                f"<|im_start|>assistant\n"
            )

    def _format_prompt(
        self,
        user_text: str,
        profile: str | int = "BALANCED",
        user_instructions: str = "",
    ) -> str:
        """Format input using the 4-layer enforcement model (Invariants, Role, Actions, Directive)."""

        # 1. Resolve level (mapping for backward compatibility with string profiles)
        mapping = {"MINIMAL": 0, "BALANCED": 1, "STRONG": 2, "OVERKILL": 4}
        level_idx = 1
        if isinstance(profile, int):
            level_idx = profile
        elif isinstance(profile, str) and profile.upper() in mapping:
            level_idx = mapping[profile.upper()]

        # Support both numeric and string keys in the levels dictionary
        level_data = (
            self.levels.get(level_idx)
            or self.levels.get(str(level_idx))
            or self.levels.get(1)
            or {}
        )

        # 2. Extract components
        invariants_text = "\n".join(f"- {i}" for i in self.invariants)
        role = level_data.get("role", "You are a text editor.")
        permitted = "\n".join(f"- {p}" for p in level_data.get("permitted", []))
        prohibited = "\n".join(f"- {p}" for p in level_data.get("prohibited", []))
        directive = level_data.get("directive", "Clean the text.")

        examples = self._get_few_shot_examples(
            level_idx, has_instructions=bool(user_instructions.strip())
        )

        # 3. Assemble layered prompt
        system_content = f"""
{self.system_prompt}

OPERATIONAL CONSTRAINTS:
{invariants_text}
""".strip()

        # Build instruction block for task
        task_instructions = ""
        if user_instructions and user_instructions.strip():
            task_instructions = f"User Instructions: {user_instructions.strip()}\n"

        user_content = f"""
/no_think

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
{task_instructions}Output:
""".strip()

        return self._apply_template(system_content, user_content)

    def refine(
        self,
        text: str,
        profile: str = "BALANCED",
        user_instructions: str = "",
        temperature: float = 0.0,
        seed_variation: str = "",
    ) -> GenerationResult:
        """
        Refine the input text using the loaded Instruct model.

        Args:
            text: Raw input text
            profile: Refinement intensity (MINIMAL, BALANCED, STRONG)
            user_instructions: Optional specific instructions from the user.
            temperature: Sampling temperature. 0.0 = deterministic (default).
                         Use >0.0 (e.g., 0.3-0.5) for retries/variability.
            seed_variation: Optional randomization string to inject into prompt
                            to force different outputs (e.g. Unix timestamp).

        Returns:
            GenerationResult containing refined text and optional reasoning.
        """
        if not text or not text.strip():
            return GenerationResult(content=text)

        # 1. Prepare Input (Chat Template)
        prompt = self._format_prompt(text, profile, user_instructions)

        # Inject hidden seed if provided (to break deterministic cache/state if any)
        # We append it as a comment in the user block if needed, but Qwen might see it.
        # Safer: Just rely on temperature sampling if > 0.
        # But if we strictly need to change the prompt to force change even at temp=0:
        if seed_variation:
            # We inject it into the system prompt or user directive invisibly?
            # Or just append to the directive block.
            # Let's rebuild the prompt logic slightly to allow this or just accept that
            # temperature is enough. If temp=0, we need prompt change.
            # Hack: Append a non-printing space or unique ID to system prompt.
            prompt = prompt.replace(
                "<|im_start|>system\n",
                f"<|im_start|>system\n[Refinement ID: {seed_variation}]\n",
                1,
            )

        # 2. Tokenize
        tokens = self.tokenizer.encode(prompt).tokens
        input_count = len(tokens)

        # 3. Generate
        # max_length refers to new tokens.
        max_new_tokens = self._calculate_dynamic_max_tokens(input_count)

        logger.debug(
            f"Refining {input_count} tokens with dynamic limit of {max_new_tokens} new tokens."
        )

        # Configure sampling
        if temperature > 0:
            beam_size = 1
            sampling_topk = 50
            sampling_temperature = temperature
        else:
            beam_size = 1
            sampling_topk = 1
            sampling_temperature = 0

        results = self.generator.generate_batch(
            [tokens],
            max_batch_size=1,
            beam_size=beam_size,
            sampling_topk=sampling_topk,
            sampling_temperature=sampling_temperature,
            max_length=max_new_tokens,
            include_prompt_in_result=False,
            end_token=self.end_token_id,
        )

        # 4. Detokenize
        # Use sequences_ids if available from CTranslate2 to avoid string token round-trip
        # generate_batch returns GenerationResult
        # result.sequences_ids is likely available.
        # But `results[0].sequences_ids` might not be populated if we didn't ask for it
        # Actually ct2 results have .sequences (list of list of str) and .sequences_ids (list of list of int)

        output_ids = results[0].sequences_ids[0]
        refined_text = self.tokenizer.decode(output_ids)

        return self._parse_output(refined_text)

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
            temperature: Sampling temperature (0.0 = deterministic, >0.0 = random).

        Returns:
            GenerationResult with 'content' and 'reasoning'.
        """
        # Use helper to apply configured template
        prompt = self._apply_template(system_prompt, f"/no_think\n\n{user_prompt}")

        tokens = self.tokenizer.encode(prompt).tokens

        # Determine sampling strategy
        if temperature > 0:
            beam_size = 1
            sampling_topk = 50
            sampling_temperature = temperature
        else:
            beam_size = 1
            sampling_topk = 1
            sampling_temperature = 0

        # Run generation
        # Note: max_length is OUTPUT length (new tokens), not total length including prompt
        results = self.generator.generate_batch(
            [tokens],
            max_batch_size=1,
            beam_size=beam_size,
            sampling_topk=sampling_topk,
            sampling_temperature=sampling_temperature,
            max_length=max_tokens,  # This is the max NEW tokens to generate
            include_prompt_in_result=False,
            end_token=self.end_token_id,
        )

        # Use sequences_ids (list of int) and decode directly
        # (Same pattern as refine() method)
        output_ids = results[0].sequences_ids[0]
        generated_text = self.tokenizer.decode(output_ids)

        logger.debug(
            f"generate_custom: output_ids count={len(output_ids)}, text={generated_text[:200] if generated_text else '(empty)'}..."
        )

        return self._parse_output(generated_text)
