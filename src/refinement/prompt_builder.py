"""
PromptBuilder — Centralised prompt construction for all SLM interactions.

Owns all prompt templates, ChatML formatting, and few-shot examples.
Used by RefinementEngine (grammar pipeline) and InsightManager (freeform generation).
"""

from __future__ import annotations


class PromptBuilder:
    """
    Builds ChatML-formatted prompts for CTranslate2 Generator.

    Two modes:
    - **Refinement**: Grammar-fix pipeline with invariants and few-shot examples.
    - **Custom generation**: Freeform system+user prompt (insight, MOTD, etc.).
    """

    # ── Analytics insight template (unified) ────────────────────────────────

    ANALYTICS_SYSTEM_PROMPT: str = """\
You are an automated analytics summarizer for a speech-to-text dashboard.

Constraints:
- You receive pre-calculated facts. Render them into readable summaries.
- Output ONLY a valid JSON object with string keys "daily" and "lifetime".
- Each value must be one short paragraph (maximum 2 sentences).
- If a daily fact is "- none", set the "daily" value to "".
- Do not introduce new metrics, estimate values, or hallucinate stats.
- Provide NO conversational text outside the JSON object."""

    ANALYTICS_TEMPLATE: str = """\
Write the dashboard summary using only the curated highlights below.

Daily highlights:
{daily_highlights}

Long-term highlights:
{long_term_highlights}

Required JSON shape:
{{"daily":"...","lifetime":"..."}}

Rules:
- The "daily" value uses only Daily highlights.
- The "lifetime" value uses only Long-term highlights.
- If Daily highlights is "- none", set "daily" to "".
- Keep every number exactly as written.
- Do not introduce any new metrics, comparisons, or conclusions beyond the highlights.

Output only the JSON object."""

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
        thinking_directive: str = "/no_think",
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

        think_directive = "" if use_thinking or not thinking_directive else f"{thinking_directive}\n\n"

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
        use_thinking: bool = False,
        thinking_directive: str = "/no_think",
    ) -> list[dict[str, str]]:
        """Build ChatML messages for freeform generation (insight, MOTD, etc.)."""
        think_directive = "" if use_thinking or not thinking_directive else f"{thinking_directive}\n\n"
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{think_directive}{user_prompt}"},
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
