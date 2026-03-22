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

    ANALYTICS_TEMPLATE: str = """\
You are embedded in a local AI-powered speech-to-text desktop application. \
The user dictates speech into text on their own machine with full privacy.

Below are the user's usage statistics. Study all of them, then write TWO short \
paragraphs as described in the instructions at the end.

Today's session:
- Transcriptions today: {today_count}
- Words today: {today_words}
- Days active this week: {days_active_this_week}

All-time overview:
- Total transcriptions: {count}
- Total words captured: {total_words}
- Total recording time: {recorded_time}
- Total speech time (VAD): {speech_time}
- Total silence time: {silence_time}
- Estimated time saved vs typing: {time_saved}
- Average recording length: {avg_length}
- Average speaking pace: {avg_pace} wpm
- Current daily streak: {current_streak} days
- Longest daily streak: {longest_streak} days

Verbatim speech quality (raw transcription output):
- Vocabulary diversity: {verbatim_vocab_pct}
- Filler words detected: {verbatim_fillers} ({verbatim_filler_density} of words)
- Top fillers: {top_fillers}
- Average Flesch-Kincaid grade: {verbatim_fk_grade}
- Average sentence length: {verbatim_avg_sentence_len} words

{refinement_section}\
Processing performance:
- Transcription speed: {transcription_speed}x realtime ({transcripts_with_transcription_time} samples)
- Refinement throughput: {refinement_wpm} wpm ({transcripts_with_refinement_time} samples)
- Refinement time saved vs manual editing: {refinement_time_saved}

Instructions — write exactly TWO short paragraphs, separated by a blank line:

PARAGRAPH 1 — Daily: Pick 2–3 of the most interesting statistics from today's \
session (or this week if today is sparse). React to them with specific numbers. \
Think a sharp colleague glancing at your dashboard — direct, a little wry.

PARAGRAPH 2 — Long-term: Pick 2–3 of the most meaningful cumulative or trend \
statistics. Highlight concrete improvements or patterns. If refinement data is \
available, the measurable difference between verbatim and refined quality is \
always worth mentioning.

Rules:
- Be warm, specific, and subtly witty. Write as a confident peer, not a cheerleader.
- Reference concrete numbers in both paragraphs.
- Do NOT begin any sentence with "You" or "Your".
- No exclamation marks. No app name. No preamble or meta-talk.
- Do NOT describe what the app does. Do not use bullet points.
- If today's data is zero, fold daily observations into the long-term paragraph \
and write only ONE paragraph instead.

Output only the paragraphs. Nothing else."""

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
        use_thinking: bool = False,
    ) -> list[dict[str, str]]:
        """Build ChatML messages for freeform generation (insight, MOTD, etc.)."""
        think_directive = "" if use_thinking else "/no_think\n\n"
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
