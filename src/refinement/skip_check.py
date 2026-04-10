"""
Refinement skip-check — fast-path gate for trivially short or clean text,
plus confidence-gated refinement scoring.

Phase 1C + Phase 2B of the CPU Refinement Speedup Plan.

- ``should_skip_refinement``: Binary gate — skip or proceed. Used by engine.
- ``score_refinement_need``: Continuous 0.0–1.0 score indicating how badly
  text needs SLM cleanup. Used for routing and prioritisation.

All checks are cheap (string ops only, no model, no tokenizer) and are
designed to be called *before* any engine or runtime work.
"""

from __future__ import annotations

import re

# Minimum word count worth sending through the SLM.  Below this threshold,
# the model's prompt overhead dwarfs the actual text, and the cleanup value
# is near zero.  A 3-word fragment like "yeah um okay" is not going to get
# meaningfully cleaner.
MIN_REFINABLE_WORDS: int = 4

# Characters below which refinement is pointless even if word count passes
# (catches things like "hi" "ok" "no" which technically are 1 word each).
MIN_REFINABLE_CHARS: int = 15

# Pattern for text that's only filler/noise — nothing substantive to refine.
_FILLER_ONLY_PATTERN = re.compile(
    r"^[\s,.!?;:]*"
    r"(?:um|uh|ah|er|like|you know|i mean|so|yeah|okay|ok|well|right|hmm|huh|mhm)"
    r"(?:[\s,.!?;:]+(?:um|uh|ah|er|like|you know|i mean|so|yeah|okay|ok|well|right|hmm|huh|mhm))*"
    r"[\s,.!?;:]*$",
    re.IGNORECASE,
)


# Score below which text is considered "clean enough" to skip refinement.
# Conservative: benchmark ASR samples score 0.51–0.77.  A score of 0.15
# means no fillers, good punctuation, proper caps, reasonable sentences.
SKIP_SCORE_THRESHOLD: float = 0.15


def should_skip_refinement(text: str) -> str | None:
    """Check whether text should skip the SLM refinement pipeline entirely.

    Returns:
        None if refinement should proceed.
        A short reason string if refinement should be skipped.
    """
    if not text or not text.strip():
        return "empty"

    stripped = text.strip()

    if len(stripped) < MIN_REFINABLE_CHARS:
        return "too_short"

    word_count = len(stripped.split())
    if word_count < MIN_REFINABLE_WORDS:
        return "too_few_words"

    if _FILLER_ONLY_PATTERN.match(stripped):
        return "filler_only"

    # Phase 2B gate: score-based skip for clean text
    if score_refinement_need(stripped) < SKIP_SCORE_THRESHOLD:
        return "low_refinement_need"

    return None


# ── Refinement-need scoring (Phase 2B) ─────────────────────────────────────
#
# Continuous 0.0–1.0 score: how badly does this text need SLM cleanup?
# Higher = more refinement-worthy.  The score is a weighted sum of cheap
# text-quality signals.  Callers can compare against a threshold to decide
# whether to route text through the SLM or pass it through untouched.

# Individual signal weights — these sum to 1.0.
_W_FILLER_DENSITY = 0.30
_W_PUNCTUATION = 0.25
_W_CAPITALIZATION = 0.20
_W_SENTENCE_STRUCTURE = 0.15
_W_REPETITION = 0.10

# Signal-specific thresholds
_HIGH_FILLER_DENSITY = 0.15  # Above this, text is clearly messy
_EXPECTED_SENTENCE_LEN = 20  # Words; avg ASR sentence length

# Pattern: sentence-ending punctuation
_SENTENCE_ENDERS = re.compile(r"[.!?]")

# Pattern: starts with uppercase letter
_STARTS_UPPER = re.compile(r"^[A-Z]")


def score_refinement_need(text: str) -> float:
    """Score how much a transcript needs SLM refinement (0.0–1.0).

    Combines cheap heuristic signals:
    - Filler word density
    - Missing/poor punctuation
    - Capitalization quality
    - Sentence structure (run-on detection)
    - Word repetition density

    Returns 0.0 for text that looks clean, 1.0 for text that desperately
    needs cleanup.  Returns 1.0 for empty/trivial text that would be
    caught by should_skip_refinement anyway.
    """
    if not text or not text.strip():
        return 1.0

    stripped = text.strip()
    words = stripped.split()
    word_count = len(words)

    if word_count < MIN_REFINABLE_WORDS:
        return 1.0

    # --- Signal 1: Filler density ---
    from src.core.usage_stats import _count_fillers

    filler_count = _count_fillers(stripped)
    filler_density = filler_count / word_count
    # Normalize: 0 fillers = 0.0, >= _HIGH_FILLER_DENSITY = 1.0
    filler_score = min(filler_density / _HIGH_FILLER_DENSITY, 1.0)

    # --- Signal 2: Punctuation quality ---
    # Check for sentence-ending punctuation.  Raw ASR often has it (Whisper
    # is pretty good), but when it's missing, the text needs cleanup.
    sentence_enders = len(_SENTENCE_ENDERS.findall(stripped))
    # Expected: roughly 1 sentence-ender per 15-25 words
    expected_enders = max(1, word_count // _EXPECTED_SENTENCE_LEN)
    if sentence_enders == 0:
        punct_score = 1.0
    elif sentence_enders >= expected_enders:
        punct_score = 0.0
    else:
        punct_score = 1.0 - (sentence_enders / expected_enders)

    # --- Signal 3: Capitalization quality ---
    # Check if sentences start with uppercase.  Split on sentence enders
    # and check each fragment.
    fragments = _SENTENCE_ENDERS.split(stripped)
    fragments = [f.strip() for f in fragments if f.strip()]
    if fragments:
        caps_ok = sum(1 for f in fragments if _STARTS_UPPER.match(f))
        cap_score = 1.0 - (caps_ok / len(fragments))
    else:
        # No sentence enders = no capitalization structure
        cap_score = 0.5 if _STARTS_UPPER.match(stripped) else 1.0

    # --- Signal 4: Sentence structure (run-on detection) ---
    # If average "sentence" (between punctuation) is very long, it's a
    # run-on mess that needs restructuring.
    if fragments:
        avg_fragment_words = sum(len(f.split()) for f in fragments) / len(fragments)
        if avg_fragment_words <= _EXPECTED_SENTENCE_LEN:
            structure_score = 0.0
        elif avg_fragment_words >= _EXPECTED_SENTENCE_LEN * 3:
            structure_score = 1.0
        else:
            structure_score = (avg_fragment_words - _EXPECTED_SENTENCE_LEN) / (_EXPECTED_SENTENCE_LEN * 2)
    else:
        # No punctuation at all = entire text is one run-on
        structure_score = min(word_count / (_EXPECTED_SENTENCE_LEN * 2), 1.0)

    # --- Signal 5: Word repetition ---
    # Consecutive repeated words ("the the", "i i") indicate ASR stutter.
    lower_words = [w.lower().strip(".,!?;:'\"") for w in words]
    repeats = sum(1 for i in range(1, len(lower_words)) if lower_words[i] == lower_words[i - 1])
    repeat_density = repeats / max(word_count - 1, 1)
    repeat_score = min(repeat_density / 0.05, 1.0)  # 5% repeat rate = max score

    # --- Weighted sum ---
    score = (
        _W_FILLER_DENSITY * filler_score
        + _W_PUNCTUATION * punct_score
        + _W_CAPITALIZATION * cap_score
        + _W_SENTENCE_STRUCTURE * structure_score
        + _W_REPETITION * repeat_score
    )

    return round(min(max(score, 0.0), 1.0), 3)
