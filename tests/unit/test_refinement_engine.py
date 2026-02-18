"""
Refinement Engine unit tests.

Tests the pure logic without loading an actual GGUF model:
- Output parsing (_parse_output): think blocks, leak tokens, edge cases
- Prompt formatting (_format_prompt): level selection, invariants, user instructions
- Dynamic token calculation (_calculate_dynamic_max_tokens)
- Few-shot example generation (_get_few_shot_examples)
- GenerationResult dataclass
"""

from __future__ import annotations

import pytest

from src.refinement.engine import GenerationResult, RefinementEngine

# ── Test Fixture: Engine Without Model ────────────────────────────────────


def _make_engine(
    system_prompt: str = "You are a test editor.",
    invariants: list[str] | None = None,
    levels: dict | None = None,
) -> RefinementEngine:
    """
    Create a RefinementEngine instance without loading a model.

    Bypasses __init__ (which requires a real GGUF file) and sets
    only the attributes needed for prompt/output logic.
    """
    engine = object.__new__(RefinementEngine)
    engine.system_prompt = system_prompt
    engine.invariants = invariants or ["Preserve meaning.", "No fluff."]
    engine.levels = levels or {
        0: {
            "name": "Literal",
            "role": "Mechanical text editor.",
            "permitted": ["Fix spelling."],
            "prohibited": ["Changing structure."],
            "directive": "Minimal changes only.",
        },
        1: {
            "name": "Structural",
            "role": "Transcription cleaner.",
            "permitted": ["Remove fillers.", "Fix syntax."],
            "prohibited": ["Paraphrasing."],
            "directive": "Clean speech noise.",
        },
        2: {
            "name": "Neutral",
            "role": "Professional editor.",
            "permitted": ["Smooth phrasing."],
            "prohibited": ["Adding flair."],
            "directive": "Clear and neutral.",
        },
    }
    engine.llm = None
    return engine


# ── GenerationResult ──────────────────────────────────────────────────────


class TestGenerationResult:
    def test_content_only(self) -> None:
        r = GenerationResult(content="Hello world")
        assert r.content == "Hello world"
        assert r.reasoning is None

    def test_with_reasoning(self) -> None:
        r = GenerationResult(content="output", reasoning="thought process")
        assert r.reasoning == "thought process"

    def test_frozen(self) -> None:
        r = GenerationResult(content="x")
        with pytest.raises(AttributeError):
            r.content = "y"  # type: ignore[misc]


# ── Output Parsing ────────────────────────────────────────────────────────


class TestParseOutput:
    def test_plain_text(self) -> None:
        engine = _make_engine()
        result = engine._parse_output("Clean output text.")
        assert result.content == "Clean output text."
        assert result.reasoning is None

    def test_think_block_extracted(self) -> None:
        engine = _make_engine()
        result = engine._parse_output("<think>I need to fix spelling.</think>The corrected text.")
        assert result.content == "The corrected text."
        assert result.reasoning == "I need to fix spelling."

    def test_think_block_with_newlines(self) -> None:
        engine = _make_engine()
        result = engine._parse_output("<think>\nLine 1\nLine 2\n</think>\nOutput here.")
        assert result.content == "Output here."
        assert "Line 1" in result.reasoning
        assert "Line 2" in result.reasoning

    def test_unclosed_think_block(self) -> None:
        engine = _make_engine()
        result = engine._parse_output("Before <think>reasoning without end tag")
        assert result.content == "Before"
        assert "REASONING TRUNCATED" in result.reasoning

    def test_transcript_markers_stripped(self) -> None:
        engine = _make_engine()
        result = engine._parse_output("<<<BEGIN TRANSCRIPT>>>Hello world<<<END TRANSCRIPT>>>")
        assert "<<<BEGIN TRANSCRIPT>>>" not in result.content
        assert "<<<END TRANSCRIPT>>>" not in result.content
        assert result.content == "Hello world"

    def test_leak_tokens_truncated(self) -> None:
        engine = _make_engine()
        for marker in ["<|im_end|>", "<|eot_id|>", "<|endoftext|>", "</s>", "<|im_start|>"]:
            result = engine._parse_output(f"Good text.{marker}garbage after")
            assert result.content == "Good text."

    def test_empty_input(self) -> None:
        engine = _make_engine()
        result = engine._parse_output("")
        assert result.content == ""
        assert result.reasoning is None

    def test_whitespace_only(self) -> None:
        engine = _make_engine()
        result = engine._parse_output("   \n\t  ")
        assert result.content == ""

    def test_combined_think_and_markers(self) -> None:
        engine = _make_engine()
        result = engine._parse_output(
            "<think>Reasoning here</think><<<BEGIN TRANSCRIPT>>>Clean output<<<END TRANSCRIPT>>><|im_end|>junk"
        )
        assert result.content == "Clean output"
        assert result.reasoning == "Reasoning here"


# ── Prompt Formatting ─────────────────────────────────────────────────────


class TestFormatPrompt:
    def test_returns_two_messages(self) -> None:
        engine = _make_engine()
        messages = engine._format_prompt("Hello world", profile=1)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_system_prompt_included(self) -> None:
        engine = _make_engine(system_prompt="I am the editor.")
        messages = engine._format_prompt("text", profile=0)
        assert "I am the editor." in messages[0]["content"]

    def test_invariants_included(self) -> None:
        engine = _make_engine(invariants=["Rule one.", "Rule two."])
        messages = engine._format_prompt("text", profile=0)
        system = messages[0]["content"]
        assert "Rule one." in system
        assert "Rule two." in system

    def test_invariants_omitted_with_custom_instructions(self) -> None:
        """When custom instructions are provided, invariants must NOT be sent."""
        engine = _make_engine(invariants=["Rule one.", "Rule two."])
        messages = engine._format_prompt("text", profile=0, user_instructions="Rewrite casually.")
        system = messages[0]["content"]
        assert "Rule one." not in system
        assert "Rule two." not in system

    def test_default_task_present(self) -> None:
        engine = _make_engine()
        messages = engine._format_prompt("text", profile=0)
        user = messages[1]["content"]
        assert "Fix all grammar, spelling, punctuation, and capitalization errors." in user

    def test_rules_in_system(self) -> None:
        engine = _make_engine()
        messages = engine._format_prompt("text", profile=0)
        system = messages[0]["content"]
        assert "Output ONLY the corrected text" in system

    def test_rules_absent_with_custom_instructions(self) -> None:
        """Custom instructions mode: system message is ONLY the identity prompt."""
        engine = _make_engine(system_prompt="I am the editor.")
        messages = engine._format_prompt("text", profile=0, user_instructions="Make it fancy.")
        system = messages[0]["content"]
        assert system == "I am the editor."
        assert "Rules:" not in system
        assert "Output ONLY" not in system

    def test_profile_ignored_for_behavior(self) -> None:
        engine = _make_engine()
        low = engine._format_prompt("text", profile=0)[1]["content"]
        high = engine._format_prompt("text", profile=4)[1]["content"]
        assert low == high

    def test_task_directive_in_user_content(self) -> None:
        engine = _make_engine()
        messages = engine._format_prompt("text", profile=1)
        user = messages[1]["content"]
        assert "Fix all grammar" in user

    def test_input_text_in_user_content(self) -> None:
        engine = _make_engine()
        messages = engine._format_prompt("My transcript text", profile=0)
        user = messages[1]["content"]
        assert "My transcript text" in user
        assert "Text:" in user

    def test_user_instructions_replace_default(self) -> None:
        engine = _make_engine()
        messages = engine._format_prompt("text", profile=0, user_instructions="Make it formal.")
        user = messages[1]["content"]
        assert "Make it formal." in user
        assert "Fix all grammar" not in user

    def test_no_think_directive_by_default(self) -> None:
        """Prompt should default to /no_think for efficient grammar edits."""
        engine = _make_engine()
        messages = engine._format_prompt("text", profile=0)
        user = messages[1]["content"]
        assert "/no_think" in user

    def test_no_think_absent_when_thinking_enabled(self) -> None:
        """Prompt should NOT include /no_think when use_thinking=True."""
        engine = _make_engine()
        messages = engine._format_prompt("text", profile=2, use_thinking=True)
        user = messages[1]["content"]
        assert "/no_think" not in user

    def test_user_instruction_overrides_default_task(self) -> None:
        """Custom instructions should replace the default task line."""
        engine = _make_engine()
        messages = engine._format_prompt("text", profile=0)
        base_user = messages[1]["content"]
        assert "Fix all grammar" in base_user

        messages = engine._format_prompt("text", profile=0, user_instructions="Make formal.")
        user = messages[1]["content"]
        assert "Make formal." in user
        assert "Fix all grammar" not in user

    # --- Profile compatibility ---

    def test_integer_profile_accepted(self) -> None:
        engine = _make_engine()
        messages = engine._format_prompt("text", profile=2)
        user = messages[1]["content"]
        assert "Fix all grammar" in user

    def test_string_profile_accepted(self) -> None:
        engine = _make_engine()
        messages = engine._format_prompt("text", profile="MINIMAL")
        user = messages[1]["content"]
        assert "Fix all grammar" in user

    def test_balanced_profile_accepted(self) -> None:
        engine = _make_engine()
        messages = engine._format_prompt("text", profile="BALANCED")
        user = messages[1]["content"]
        assert "Fix all grammar" in user

    def test_unknown_string_profile_accepted(self) -> None:
        engine = _make_engine()
        messages = engine._format_prompt("text", profile="NONEXISTENT")
        user = messages[1]["content"]
        assert "Fix all grammar" in user

    def test_missing_level_still_formats_prompt(self) -> None:
        engine = _make_engine()
        messages = engine._format_prompt("text", profile=99)
        user = messages[1]["content"]
        assert "Fix all grammar" in user


# ── Dynamic Token Calculation ─────────────────────────────────────────────


class TestDynamicTokenCalculation:
    def test_small_input(self) -> None:
        engine = _make_engine()
        result = engine._calculate_dynamic_max_tokens(10)
        # 10 + max(150, 10*0.5=5) = 10 + 150 = 160
        assert result == 160

    def test_small_input_with_thinking(self) -> None:
        engine = _make_engine()
        result = engine._calculate_dynamic_max_tokens(10, use_thinking=True)
        # output_budget = 10 + max(150, 5) = 160; thinking_budget = 2048 -> 2208
        assert result == 2208

    def test_medium_input(self) -> None:
        engine = _make_engine()
        result = engine._calculate_dynamic_max_tokens(500)
        # 500 + max(150, 500*0.5=250) = 500 + 250 = 750
        assert result == 750

    def test_medium_input_with_thinking(self) -> None:
        engine = _make_engine()
        result = engine._calculate_dynamic_max_tokens(500, use_thinking=True)
        # output_budget = 500 + max(150, 250) = 750; thinking_budget = 2048 -> 2798
        assert result == 2798

    def test_large_input_capped(self) -> None:
        engine = _make_engine()
        result = engine._calculate_dynamic_max_tokens(50000)
        # Would be 50000 + 25000 = 75000, capped at HARD_MAX
        assert result == engine.HARD_MAX_OUTPUT_TOKENS

    def test_zero_input(self) -> None:
        engine = _make_engine()
        result = engine._calculate_dynamic_max_tokens(0)
        # max(1, 0) = 1, padding = max(150, 0) = 150, total = 1 + 150 = 151
        assert result == 151

    def test_result_never_exceeds_hard_max(self) -> None:
        engine = _make_engine()
        for count in [0, 100, 1000, 10000, 100000]:
            result = engine._calculate_dynamic_max_tokens(count)
            assert result <= engine.HARD_MAX_OUTPUT_TOKENS


# ── Few-Shot Examples ─────────────────────────────────────────────────────


class TestFewShotExamples:
    def test_level_0_has_examples(self) -> None:
        engine = _make_engine()
        examples = engine._get_few_shot_examples(0)
        assert "EXAMPLES OF DESIRED BEHAVIOR" in examples
        assert "hello this is a test" in examples

    def test_level_1_differs_from_level_0(self) -> None:
        engine = _make_engine()
        _ex0 = engine._get_few_shot_examples(0)
        ex1 = engine._get_few_shot_examples(1)
        # Level 1 should have filler removal examples
        assert "I I want to" in ex1 or "I want to go" in ex1

    def test_each_level_produces_examples(self) -> None:
        engine = _make_engine()
        for level in range(5):
            examples = engine._get_few_shot_examples(level)
            assert "EXAMPLES OF DESIRED BEHAVIOR" in examples

    def test_instruction_example_included_when_flagged(self) -> None:
        engine = _make_engine()
        examples = engine._get_few_shot_examples(0, has_instructions=True)
        assert "User Instructions" in examples

    def test_instruction_example_absent_by_default(self) -> None:
        engine = _make_engine()
        examples = engine._get_few_shot_examples(0, has_instructions=False)
        assert "User Instructions" not in examples


# ── Refine Guard: Empty Input ─────────────────────────────────────────────


class TestRefineGuard:
    """refine() with empty/blank text returns input unchanged without calling LLM."""

    def test_empty_string_returns_empty(self) -> None:
        engine = _make_engine()
        result = engine.refine("")
        assert result.content == ""

    def test_whitespace_only_returns_input(self) -> None:
        engine = _make_engine()
        result = engine.refine("   \n\t  ")
        assert result.content == "   \n\t  "

    def test_none_like_empty(self) -> None:
        engine = _make_engine()
        # text="" is falsy, should short-circuit
        result = engine.refine("")
        assert isinstance(result, GenerationResult)
