"""
Text analysis utilities — readability metrics, sentence splitting, syllable counting.

All functions are pure, stateless, and operate on plain strings.
Used by usage_stats (backend) and mirrored in frontend/src/lib/textAnalysis.ts.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Syllable estimation
# ---------------------------------------------------------------------------

# Vowel groups in a word approximate syllable count.  Not perfect,
# but good enough for Flesch-Kincaid without dragging in NLTK.
_VOWELS = re.compile(r"[aeiouy]+", re.IGNORECASE)
_SILENT_E = re.compile(r"[^l]e$", re.IGNORECASE)
_TRAILING_ES = re.compile(r"(?:es|ed)$", re.IGNORECASE)


def estimate_syllables(word: str) -> int:
    """Estimate syllable count for an English word.

    Uses a simple vowel-group heuristic with common corrections.
    Every word has at least one syllable.
    """
    w = word.strip().lower()
    if not w:
        return 0
    # Remove trailing punctuation
    w = re.sub(r"[^a-z]", "", w)
    if not w:
        return 0

    count = len(_VOWELS.findall(w))

    # Silent-e at end (e.g. "make" = 1 syllable, not 2)
    if _SILENT_E.search(w):
        count -= 1

    # Trailing -es/-ed that don't add a syllable (e.g. "baked", "makes")
    if _TRAILING_ES.search(w) and len(w) > 3:
        count -= 1

    return max(count, 1)


# ---------------------------------------------------------------------------
# Sentence splitting
# ---------------------------------------------------------------------------

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    """Split text into sentences on .!? boundaries.

    If no sentence-ending punctuation is found, treat the entire text
    as one sentence.  Whisper output almost always has punctuation.
    """
    if not text or not text.strip():
        return []
    sentences = [s.strip() for s in _SENTENCE_BOUNDARY.split(text.strip()) if s.strip()]
    return sentences if sentences else [text.strip()]


# ---------------------------------------------------------------------------
# Flesch-Kincaid Grade Level
# ---------------------------------------------------------------------------


def flesch_kincaid_grade(text: str) -> float:
    """Compute the Flesch-Kincaid Grade Level for a block of text.

    Returns 0.0 for empty or degenerate input.
    """
    sentences = split_sentences(text)
    if not sentences:
        return 0.0

    words = text.split()
    if not words:
        return 0.0

    total_syllables = sum(estimate_syllables(w) for w in words)
    word_count = len(words)
    sentence_count = len(sentences)

    grade = 0.39 * (word_count / sentence_count) + 11.8 * (total_syllables / word_count) - 15.59
    return round(min(max(grade, 0.0), 20.0), 1)


# ---------------------------------------------------------------------------
# Aggregate text metrics
# ---------------------------------------------------------------------------


def compute_text_metrics(text: str) -> dict:
    """Compute a full metrics dict for a block of text.

    Returns:
        word_count: int
        sentence_count: int
        avg_sentence_length: float  (words per sentence)
        avg_word_length: float  (characters per word)
        long_word_ratio: float  (words > 6 chars / total)
        fk_grade: float  (Flesch-Kincaid grade level)
        syllables_per_word: float
    """
    if not text or not text.strip():
        return {
            "word_count": 0,
            "sentence_count": 0,
            "avg_sentence_length": 0.0,
            "avg_word_length": 0.0,
            "long_word_ratio": 0.0,
            "fk_grade": 0.0,
            "syllables_per_word": 0.0,
        }

    words = text.split()
    word_count = len(words)
    sentences = split_sentences(text)
    sentence_count = len(sentences)

    # Clean words for character-level metrics
    cleaned = [re.sub(r"[^a-zA-Z]", "", w) for w in words]
    cleaned = [c for c in cleaned if c]

    total_chars = sum(len(c) for c in cleaned)
    long_words = sum(1 for c in cleaned if len(c) > 6)
    total_syllables = sum(estimate_syllables(w) for w in words)

    avg_word_length = total_chars / len(cleaned) if cleaned else 0.0
    long_word_ratio = long_words / len(cleaned) if cleaned else 0.0

    return {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "avg_sentence_length": round(word_count / sentence_count, 1) if sentence_count else 0.0,
        "avg_word_length": round(avg_word_length, 1),
        "long_word_ratio": round(long_word_ratio, 3),
        "fk_grade": flesch_kincaid_grade(text),
        "syllables_per_word": round(total_syllables / word_count, 2) if word_count else 0.0,
    }

