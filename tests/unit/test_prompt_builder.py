"""
PromptBuilder unit tests.

Tests the standalone prompt construction class extracted per ISS-010.
Covers: refinement messages, custom messages, ChatML serialisation,
few-shot examples, and template availability.
"""

from __future__ import annotations

import pytest

from src.refinement.prompt_builder import PromptBuilder

# ── Fixture ───────────────────────────────────────────────────────────────


def _make_builder(
    system_prompt: str = "You are a test editor.",
    invariants: list[str] | None = None,
) -> PromptBuilder:
    return PromptBuilder(
        system_prompt=system_prompt,
        invariants=invariants or ["Preserve meaning.", "No fluff."],
    )


# ── Refinement Messages ──────────────────────────────────────────────────


class TestBuildRefinementMessages:
    def test_returns_two_messages(self) -> None:
        pb = _make_builder()
        msgs = pb.build_refinement_messages("Hello world")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"

    def test_system_prompt_included(self) -> None:
        pb = _make_builder(system_prompt="I am the editor.")
        msgs = pb.build_refinement_messages("text")
        assert "I am the editor." in msgs[0]["content"]

    def test_invariants_in_default_mode(self) -> None:
        pb = _make_builder(invariants=["Rule one.", "Rule two."])
        msgs = pb.build_refinement_messages("text")
        system = msgs[0]["content"]
        assert "Rule one." in system
        assert "Rule two." in system

    def test_invariants_omitted_with_custom_instructions(self) -> None:
        pb = _make_builder(invariants=["Rule one.", "Rule two."])
        msgs = pb.build_refinement_messages("text", user_instructions="Rewrite casually.")
        system = msgs[0]["content"]
        assert "Rule one." not in system
        assert "Rule two." not in system

    def test_default_task_directive(self) -> None:
        pb = _make_builder()
        msgs = pb.build_refinement_messages("text")
        user = msgs[1]["content"]
        assert "Fix all grammar, spelling, punctuation, and capitalization errors." in user

    def test_custom_instructions_replace_default(self) -> None:
        pb = _make_builder()
        msgs = pb.build_refinement_messages("text", user_instructions="Make it fancy.")
        user = msgs[1]["content"]
        assert "Make it fancy." in user
        assert "Fix all grammar" not in user

    def test_no_think_by_default(self) -> None:
        pb = _make_builder()
        msgs = pb.build_refinement_messages("text")
        assert "/no_think" in msgs[1]["content"]

    def test_no_think_absent_when_thinking(self) -> None:
        pb = _make_builder()
        msgs = pb.build_refinement_messages("text", use_thinking=True)
        assert "/no_think" not in msgs[1]["content"]

    def test_user_text_in_user_content(self) -> None:
        pb = _make_builder()
        msgs = pb.build_refinement_messages("My transcript text")
        user = msgs[1]["content"]
        assert "My transcript text" in user
        assert "Text:" in user

    def test_output_only_rule_in_system(self) -> None:
        pb = _make_builder()
        msgs = pb.build_refinement_messages("text")
        system = msgs[0]["content"]
        assert "Output ONLY the corrected text" in system

    def test_rules_absent_with_custom_instructions(self) -> None:
        pb = _make_builder(system_prompt="I am the editor.")
        msgs = pb.build_refinement_messages("text", user_instructions="Go wild.")
        system = msgs[0]["content"]
        assert system == "I am the editor."
        assert "Rules:" not in system


# ── Custom Messages ───────────────────────────────────────────────────────


class TestBuildCustomMessages:
    def test_returns_two_messages(self) -> None:
        pb = _make_builder()
        msgs = pb.build_custom_messages("You are helpful.", "Tell me a joke.")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"

    def test_system_prompt_matches_input(self) -> None:
        pb = _make_builder()
        msgs = pb.build_custom_messages("Custom system.", "Custom user.")
        assert msgs[0]["content"] == "Custom system."

    def test_user_prompt_has_no_think(self) -> None:
        pb = _make_builder()
        msgs = pb.build_custom_messages("sys", "Generate insight.")
        assert "/no_think" in msgs[1]["content"]
        assert "Generate insight." in msgs[1]["content"]


# ── ChatML Serialisation ─────────────────────────────────────────────────


class TestMessagesToChatml:
    def test_basic_format(self) -> None:
        msgs = [
            {"role": "system", "content": "You help."},
            {"role": "user", "content": "Hello."},
        ]
        result = PromptBuilder.messages_to_chatml(msgs)
        assert "<|im_start|>system\nYou help.<|im_end|>" in result
        assert "<|im_start|>user\nHello.<|im_end|>" in result
        assert result.endswith("<|im_start|>assistant\n")

    def test_assistant_turn_appended(self) -> None:
        msgs = [{"role": "system", "content": "x"}]
        result = PromptBuilder.messages_to_chatml(msgs)
        assert result.endswith("<|im_start|>assistant\n")


# ── Few-Shot Examples ─────────────────────────────────────────────────────


class TestGetFewShotExamples:
    def test_level_0_has_examples(self) -> None:
        examples = PromptBuilder.get_few_shot_examples(0)
        assert "EXAMPLES OF DESIRED BEHAVIOR" in examples
        assert "hello this is a test" in examples

    def test_level_1_has_filler_removal(self) -> None:
        examples = PromptBuilder.get_few_shot_examples(1)
        assert "I I want to" in examples or "I want to go" in examples

    def test_all_levels_produce_examples(self) -> None:
        for level in range(5):
            examples = PromptBuilder.get_few_shot_examples(level)
            assert "EXAMPLES OF DESIRED BEHAVIOR" in examples

    def test_instruction_example_when_flagged(self) -> None:
        examples = PromptBuilder.get_few_shot_examples(0, has_instructions=True)
        assert "User Instructions" in examples

    def test_no_instruction_example_by_default(self) -> None:
        examples = PromptBuilder.get_few_shot_examples(0, has_instructions=False)
        assert "User Instructions" not in examples


# ── Templates ─────────────────────────────────────────────────────────────


class TestTemplates:
    def test_insight_template_has_placeholders(self) -> None:
        for key in [
            "count",
            "total_words",
            "recorded_time",
            "time_saved",
            "avg_length",
            "vocab_pct",
            "silence",
            "fillers",
        ]:
            assert f"{{{key}}}" in PromptBuilder.INSIGHT_TEMPLATE

    def test_motd_template_has_placeholders(self) -> None:
        for key in ["count", "total_words", "avg_pace", "vocab_pct"]:
            assert f"{{{key}}}" in PromptBuilder.MOTD_TEMPLATE

    def test_insight_template_can_format(self) -> None:
        """Ensure the template formats without error given valid data."""
        result = PromptBuilder.INSIGHT_TEMPLATE.format(
            count=10,
            total_words="1,234",
            recorded_time="5m",
            time_saved="2m",
            avg_length="30s",
            vocab_pct="25%",
            silence="10s",
            fillers=5,
        )
        assert "10" in result
        assert "1,234" in result

    def test_motd_template_can_format(self) -> None:
        result = PromptBuilder.MOTD_TEMPLATE.format(
            count=5,
            total_words="500",
            avg_pace=120,
            vocab_pct="30%",
        )
        assert "5" in result
        assert "120" in result
