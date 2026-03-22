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
    def test_analytics_template_has_placeholders(self) -> None:
        for key in [
            "count",
            "total_words",
            "recorded_time",
            "speech_time",
            "silence_time",
            "time_saved",
            "avg_length",
            "avg_pace",
            "current_streak",
            "longest_streak",
            "verbatim_vocab_pct",
            "verbatim_fillers",
            "verbatim_filler_density",
            "verbatim_fk_grade",
            "verbatim_avg_sentence_len",
            "top_fillers",
            "refinement_section",
            "transcription_speed",
            "refinement_wpm",
            "today_count",
            "today_words",
            "days_active_this_week",
        ]:
            assert f"{{{key}}}" in PromptBuilder.ANALYTICS_TEMPLATE

    def test_analytics_template_can_format(self) -> None:
        """Ensure the unified template formats without error given valid data."""
        result = PromptBuilder.ANALYTICS_TEMPLATE.format_map(
            {
                "count": 10,
                "total_words": "1,234",
                "recorded_time": "5m",
                "speech_time": "4m",
                "silence_time": "1m",
                "time_saved": "2m",
                "avg_length": "30s",
                "avg_pace": 150,
                "current_streak": 3,
                "longest_streak": 7,
                "verbatim_vocab_pct": "25%",
                "verbatim_fillers": 5,
                "verbatim_filler_density": "3.2%",
                "verbatim_fk_grade": 6.5,
                "verbatim_avg_sentence_len": 12.3,
                "top_fillers": '"um" (3), "uh" (2)',
                "refinement_section": "",
                "refined_count": 0,
                "transcription_speed": 5.0,
                "transcripts_with_transcription_time": 8,
                "refinement_wpm": 0,
                "transcripts_with_refinement_time": 0,
                "refinement_time_saved": "0s",
                "today_count": 2,
                "today_words": "150",
                "days_active_this_week": 4,
            }
        )
        assert "10" in result
        assert "1,234" in result
        assert "PARAGRAPH 1" in result
        assert "PARAGRAPH 2" in result
