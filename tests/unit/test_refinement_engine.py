"""
Refinement Engine unit tests.

Tests the pure logic without loading an actual CT2 model:
- Output parsing (_parse_output): think blocks, leak tokens, edge cases
- Prompt formatting (_format_prompt): invariants, user instructions
- Dynamic token calculation (_calculate_dynamic_max_tokens)
- GenerationResult dataclass
"""

from __future__ import annotations

import pytest

from src.refinement.engine import GenerationResult, RefinementEngine
from src.refinement.prompt_builder import PromptBuilder

# ── Test Fixture: Engine Without Model ────────────────────────────────────


def _make_engine(
    system_prompt: str = "You are a test editor.",
    invariants: list[str] | None = None,
) -> RefinementEngine:
    """
    Create a RefinementEngine instance without loading a model.

    Bypasses __init__ (which requires a real CT2 directory) and sets
    only the attributes needed for prompt/output logic.
    """
    engine = object.__new__(RefinementEngine)
    engine.system_prompt = system_prompt
    engine.invariants = invariants or ["Preserve meaning.", "No fluff."]
    # CT2 engine attributes (not used by pure-logic tests)
    engine.generator = None
    engine.tokenizer = None
    engine._end_tokens = []
    engine._im_end_id = None
    engine._eos_id = None
    # PromptBuilder (used by delegated prompt/chatml methods)
    engine.prompt_builder = PromptBuilder(
        system_prompt=engine.system_prompt,
        invariants=engine.invariants,
    )
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

    def test_role_marker_stripped(self) -> None:
        """ChatML role markers that survive after im_start removal are stripped."""
        engine = _make_engine()
        result = engine._parse_output("system\nThe actual output here.")
        assert result.content == "The actual output here."

    def test_no_think_directive_stripped(self) -> None:
        """Echoed /no_think directive is stripped from output."""
        engine = _make_engine()
        result = engine._parse_output("/no_think\n\nClean result.")
        assert result.content == "Clean result."

    def test_assistant_role_marker_stripped(self) -> None:
        engine = _make_engine()
        result = engine._parse_output("assistant\nHere is your text.")
        assert result.content == "Here is your text."


# ── Prompt Formatting ─────────────────────────────────────────────────────


class TestFormatPrompt:
    def test_returns_two_messages(self) -> None:
        engine = _make_engine()
        messages = engine._format_prompt("Hello world")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_system_prompt_included(self) -> None:
        engine = _make_engine(system_prompt="I am the editor.")
        messages = engine._format_prompt("text")
        assert "I am the editor." in messages[0]["content"]

    def test_invariants_included(self) -> None:
        engine = _make_engine(invariants=["Rule one.", "Rule two."])
        messages = engine._format_prompt("text")
        system = messages[0]["content"]
        assert "Rule one." in system
        assert "Rule two." in system

    def test_invariants_omitted_with_custom_instructions(self) -> None:
        """When custom instructions are provided, invariants must NOT be sent."""
        engine = _make_engine(invariants=["Rule one.", "Rule two."])
        messages = engine._format_prompt("text", user_instructions="Rewrite casually.")
        system = messages[0]["content"]
        assert "Rule one." not in system
        assert "Rule two." not in system

    def test_default_task_present(self) -> None:
        engine = _make_engine()
        messages = engine._format_prompt("text")
        user = messages[1]["content"]
        assert "Fix all grammar, spelling, punctuation, and capitalization errors." in user

    def test_rules_in_system(self) -> None:
        engine = _make_engine()
        messages = engine._format_prompt("text")
        system = messages[0]["content"]
        assert "Output ONLY the corrected text" in system

    def test_rules_absent_with_custom_instructions(self) -> None:
        """Custom instructions mode: system message is ONLY the identity prompt."""
        engine = _make_engine(system_prompt="I am the editor.")
        messages = engine._format_prompt("text", user_instructions="Make it fancy.")
        system = messages[0]["content"]
        assert system == "I am the editor."
        assert "Rules:" not in system
        assert "Output ONLY" not in system

    # test_task_directive_in_user_content deleted in v6.5.1 — subsumed by
    # test_default_task_present which already asserts the same substring.

    def test_input_text_in_user_content(self) -> None:
        engine = _make_engine()
        messages = engine._format_prompt("My transcript text")
        user = messages[1]["content"]
        assert "My transcript text" in user
        assert "Text:" in user

    def test_user_instructions_replace_default(self) -> None:
        engine = _make_engine()
        messages = engine._format_prompt("text", user_instructions="Make it formal.")
        user = messages[1]["content"]
        assert "Make it formal." in user
        assert "Fix all grammar" not in user

    def test_no_think_directive_by_default(self) -> None:
        """Prompt should default to /no_think for efficient grammar edits."""
        engine = _make_engine()
        messages = engine._format_prompt("text")
        user = messages[1]["content"]
        assert "/no_think" in user

    def test_no_think_absent_when_thinking_enabled(self) -> None:
        """Prompt should NOT include /no_think when use_thinking=True."""
        engine = _make_engine()
        messages = engine._format_prompt("text", use_thinking=True)
        user = messages[1]["content"]
        assert "/no_think" not in user

    # test_user_instruction_overrides_default_task deleted in v6.5.1 —
    # exact duplicate of test_user_instructions_replace_default above.


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

    # test_none_like_empty deleted in v6.5.1 — same input as
    # test_empty_string_returns_empty with a weaker `isinstance` assertion.

    def test_skip_gate_applies_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        engine = _make_engine()

        monkeypatch.setattr("src.refinement.skip_check.should_skip_refinement", lambda text: "short_text")

        result = engine.refine("ok")

        assert result.content == "ok"

    def test_skip_gate_can_be_bypassed_for_explicit_requests(self, monkeypatch: pytest.MonkeyPatch) -> None:
        engine = _make_engine()

        monkeypatch.setattr("src.refinement.skip_check.should_skip_refinement", lambda text: "short_text")
        engine._format_prompt = lambda text, user_instructions="", use_thinking=False: [  # type: ignore[method-assign]
            {"role": "system", "content": "sys"},
            {"role": "user", "content": user_instructions or text},
        ]
        engine._messages_to_chatml = lambda messages: "chatml"  # type: ignore[method-assign]

        class _Encoded:
            tokens = ["a", "b"]

        class _Tokenizer:
            def encode(self, value: str) -> _Encoded:
                assert value == "chatml"
                return _Encoded()

            def decode(self, ids: list[int]) -> str:
                return "Refined output"

        class _Result:
            sequences_ids = [[1, 2, 3]]

        class _Generator:
            def generate_batch(self, prompts: list[list[str]], **kwargs: object) -> list[_Result]:
                assert prompts == [["a", "b"]]
                return [_Result()]

        engine.tokenizer = _Tokenizer()
        engine.generator = _Generator()

        result = engine.refine("ok", user_instructions="Fix this anyway.", allow_skip=False)

        assert result.content == "Refined output"
