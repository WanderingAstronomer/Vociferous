"""
Unit tests for text_analysis — syllable counting, FK grade, sentence splitting.
"""

from __future__ import annotations

import pytest

from src.core.text_analysis import (
    compute_text_metrics,
    estimate_syllables,
    flesch_kincaid_grade,
    split_sentences,
)

# ---------------------------------------------------------------------------
# Syllable estimation
# ---------------------------------------------------------------------------


class TestEstimateSyllables:
    """Verify syllable counting heuristic."""

    @pytest.mark.parametrize(
        "word,expected",
        [
            ("cat", 1),
            ("hello", 2),
            ("beautiful", 3),
            ("internationalization", 8),
            ("the", 1),
            ("a", 1),
            ("make", 1),  # silent-e
            ("baked", 1),  # trailing -ed
            ("", 0),
        ],
    )
    def test_syllable_counts(self, word, expected):
        assert estimate_syllables(word) == expected

    def test_minimum_one_syllable(self):
        assert estimate_syllables("x") >= 1

    def test_punctuated_word(self):
        # Should handle trailing punctuation gracefully
        assert estimate_syllables("hello,") == 2


# ---------------------------------------------------------------------------
# Sentence splitting
# ---------------------------------------------------------------------------


class TestSplitSentences:
    """Verify sentence boundary detection."""

    def test_multiple_sentences(self):
        text = "Hello world. How are you? I am fine!"
        sentences = split_sentences(text)
        assert len(sentences) == 3

    def test_single_sentence_no_period(self):
        text = "Hello world"
        sentences = split_sentences(text)
        assert len(sentences) == 1

    def test_empty_string(self):
        assert split_sentences("") == []
        assert split_sentences("   ") == []

    def test_single_sentence_with_period(self):
        text = "Hello world."
        sentences = split_sentences(text)
        assert len(sentences) == 1


# ---------------------------------------------------------------------------
# Flesch-Kincaid Grade Level
# ---------------------------------------------------------------------------


class TestFleschKincaidGrade:
    """Verify FK computation produces sane results."""

    def test_simple_text_low_grade(self):
        text = "The cat sat. The dog ran. The bird flew."
        grade = flesch_kincaid_grade(text)
        assert 0 <= grade <= 5

    def test_complex_text_higher_grade(self):
        text = (
            "The committee convened to deliberate the preliminary "
            "findings of the investigation. Several distinguished "
            "members expressed considerable reservations about the "
            "proposed methodology."
        )
        grade = flesch_kincaid_grade(text)
        assert grade > 5

    def test_empty_text_returns_zero(self):
        assert flesch_kincaid_grade("") == 0.0
        assert flesch_kincaid_grade("   ") == 0.0

    def test_clamp_at_20_for_unpunctuated_text(self):
        # 200 words with no sentence-ending punctuation => raw FK would be ~80+
        wall = " ".join(["the quick brown fox jumps over the lazy dog"] * 22)
        grade = flesch_kincaid_grade(wall)
        assert grade == 20.0


# ---------------------------------------------------------------------------
# compute_text_metrics
# ---------------------------------------------------------------------------


class TestComputeTextMetrics:
    """Verify the combined metrics dict."""

    def test_returns_all_keys(self):
        metrics = compute_text_metrics("Hello world. This is a test.")
        expected = {
            "word_count",
            "sentence_count",
            "avg_sentence_length",
            "avg_word_length",
            "long_word_ratio",
            "fk_grade",
            "syllables_per_word",
        }
        assert set(metrics.keys()) == expected

    def test_word_count_accurate(self):
        metrics = compute_text_metrics("one two three four five")
        assert metrics["word_count"] == 5

    def test_sentence_count_accurate(self):
        metrics = compute_text_metrics("First sentence. Second sentence.")
        assert metrics["sentence_count"] == 2

    def test_avg_sentence_length(self):
        metrics = compute_text_metrics("One two. Three four five six.")
        # 6 words / 2 sentences = 3.0
        assert metrics["avg_sentence_length"] == 3.0

    def test_empty_text_zeroes(self):
        metrics = compute_text_metrics("")
        assert metrics["word_count"] == 0
        assert metrics["fk_grade"] == 0.0


