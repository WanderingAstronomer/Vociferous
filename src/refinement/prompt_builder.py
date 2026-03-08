"""
PromptBuilder — Centralised prompt construction for all SLM interactions.

Owns all prompt templates, ChatML formatting, and few-shot examples.
Used by RefinementEngine (grammar pipeline) and InsightManager (freeform generation).

Extraction from engine.py per ISS-010: prompt logic was inline, blocking
ISS-011 (custom prompts) and tangled with ISS-007/008 coupling.
"""

from __future__ import annotations

from typing import Any


class PromptBuilder:
    """
    Builds ChatML-formatted prompts for CTranslate2 Generator.

    Two modes:
    - **Refinement**: Grammar-fix pipeline with invariants and few-shot examples.
    - **Custom generation**: Freeform system+user prompt (insight, MOTD, etc.).
    """

    # ── Insight / MOTD templates ────────────────────────────────────────────

    INSIGHT_TEMPLATE: str = """\
You are a witty, encouraging assistant embedded in Vociferous, a local AI-powered \
speech-to-text application. The user dictates speech into text on their own machine \
with full privacy — no cloud, no data collection.

Here are the user's current usage statistics:

- Total transcriptions: {count}
- Total words captured: {total_words}
- Total recording time: {recorded_time}
- Estimated time saved vs typing: {time_saved}
- Average recording length: {avg_length}
- Vocabulary diversity (unique/total words): {vocab_pct}
- Total estimated silence in recordings: {silence}
- Filler words detected: {fillers}

Write exactly ONE short paragraph (2-3 sentences) giving the user personalized, \
specific feedback based on these statistics. Be warm, direct, and subtly witty. \
Reference concrete numbers. Do not use bullet points. Do not begin with "You" or \
"Your". Do not mention the app name. Do not use exclamation marks more than once. \
Write as a confident peer, not a cheerleader."""

    MOTD_TEMPLATE: str = """\
You are embedded in Vociferous, a local AI-powered speech-to-text desktop application.
The user has captured the following usage data:

- Total transcriptions: {count}
- Total words captured: {total_words}
- Average pace: {avg_pace} wpm
- Vocabulary diversity: {vocab_pct}

Write ONE sentence reacting to these stats with dry, specific wit. \
Think a laconic colleague glancing at your numbers \
and saying exactly one thing — insightful, a little wry, never motivational.

Rules:
- Maximum 15 words.
- Do NOT begin with "You" or "Your".
- Do NOT list multiple stats. Pick one angle, say one thing.
- No exclamation marks. No app name. No preamble.
- Do NOT describe what the app does or what the user is doing.

Bad example: "You've made 13 transcriptions with 2,071 words at 150 wpm and 29% vocabulary diversity."
Good example: "Consistent pace, narrow vocabulary — dictating or just not a big reader?"
Good example: "153 words per minute and you still find time to say 'um' 78 times."

Output only the sentence. Nothing else."""

    def __init__(
        self,
        system_prompt: str = "",
        invariants: list[str] | None = None,
    ) -> None:
        self.system_prompt = system_prompt
        self.invariants = invariants or []

    # ── Public: Refinement prompt ───────────────────────────────────────────

    def build_refinement_messages(
        self,
        user_text: str,
        user_instructions: str = "",
        use_thinking: bool = False,
    ) -> list[dict[str, str]]:
        """Build ChatML messages for the grammar-fix refinement pipeline.

        Two modes:
        - **Default (no custom instructions)**: Grammar-fix pipeline with
          invariants enforcing meaning-preservation and output discipline.
        - **Custom instructions provided**: The user's instructions become
          the ENTIRE task.  Invariants are NOT sent — the user is in control
          and the safety rails would only confuse the model or fight the
          user's intent.
        """
        custom = user_instructions.strip() if user_instructions else ""

        if custom:
            system_content = self.system_prompt
            task_directive = custom
        else:
            invariants_text = "\n".join(f"- {i}" for i in self.invariants)
            system_content = f"""{self.system_prompt}

Rules:
{invariants_text}
- Output ONLY the corrected text. No explanations, no preamble.""".strip()
            task_directive = "Fix all grammar, spelling, punctuation, and capitalization errors."

        think_directive = "" if use_thinking else "/no_think\n\n"

        user_content = f"""{think_directive}{task_directive}

Text:
{user_text}""".strip()

        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]

    # ── Public: Custom / freeform prompt ────────────────────────────────────

    def build_custom_messages(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> list[dict[str, str]]:
        """Build ChatML messages for freeform generation (insight, MOTD, etc.)."""
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"/no_think\n\n{user_prompt}"},
        ]

    # ── Public: ChatML serialisation ────────────────────────────────────────

    @staticmethod
    def messages_to_chatml(messages: list[dict[str, str]]) -> str:
        """Convert a list of chat messages to a ChatML-formatted string.

        CTranslate2 Generator works at the token level — no built-in chat
        template support.  We apply the ChatML template ourselves, then
        tokenize, then generate.
        """
        parts: list[str] = []
        for msg in messages:
            parts.append(f"<|im_start|>{msg['role']}\n{msg['content']}<|im_end|>")
        parts.append("<|im_start|>assistant\n")
        return "\n".join(parts)
