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

    def test_user_prompt_has_no_think_by_default(self) -> None:
        pb = _make_builder()
        msgs = pb.build_custom_messages("sys", "Generate insight.")
        assert "/no_think" in msgs[1]["content"]
        assert "Generate insight." in msgs[1]["content"]

    def test_no_think_absent_when_thinking_enabled(self) -> None:
        pb = _make_builder()
        msgs = pb.build_custom_messages("sys", "Generate insight.", use_thinking=True)
        assert "/no_think" not in msgs[1]["content"]
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


# ── Templates ─────────────────────────────────────────────────────────────


class TestTemplates:
    def test_analytics_system_prompt_is_constrained(self) -> None:
        assert "Use ONLY the facts and numbers provided by the user message." in PromptBuilder.ANALYTICS_SYSTEM_PROMPT
        assert "already selected" in PromptBuilder.ANALYTICS_SYSTEM_PROMPT
        assert "Never invent, estimate, recompute" in PromptBuilder.ANALYTICS_SYSTEM_PROMPT

    def test_analytics_template_has_placeholders(self) -> None:
        for key in ["daily_highlights", "long_term_highlights"]:
            assert f"{{{key}}}" in PromptBuilder.ANALYTICS_TEMPLATE

    def test_analytics_template_can_format(self) -> None:
        """Ensure the unified template formats without error given valid data."""
        result = PromptBuilder.ANALYTICS_TEMPLATE.format_map(
            {
                "daily_highlights": "- Words today: 150.\n- Transcriptions today: 2.",
                "long_term_highlights": "- Total words captured: 1,234 across 10 transcriptions.\n- Estimated time saved vs typing: 2m.",
            }
        )
        assert "150" in result
        assert "1,234" in result
        assert "Daily highlights:" in result
        assert "Long-term highlights:" in result
        assert "Required structure:" in result
