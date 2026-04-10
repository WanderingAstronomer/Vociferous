"""Tests for src.refinement.skip_check — Phase 1C fast-path gate + Phase 2B scorer."""

from __future__ import annotations

import pytest

from src.refinement.skip_check import (
    MIN_REFINABLE_CHARS,
    MIN_REFINABLE_WORDS,
    SKIP_SCORE_THRESHOLD,
    score_refinement_need,
    should_skip_refinement,
)


class TestShouldSkipRefinement:
    """should_skip_refinement returns a reason string or None."""

    # ── Should skip ─────────────────────────────────────────────────────

    def test_empty_string(self) -> None:
        assert should_skip_refinement("") == "empty"

    def test_none_treated_as_empty(self) -> None:
        # Engine passes text directly; None could arrive from upstream.
        assert should_skip_refinement(None) == "empty"  # type: ignore[arg-type]

    def test_whitespace_only(self) -> None:
        assert should_skip_refinement("   \n\t  ") == "empty"

    def test_too_short_by_chars(self) -> None:
        # Under MIN_REFINABLE_CHARS (15)
        assert should_skip_refinement("hi there") == "too_short"
        assert should_skip_refinement("ok fine") == "too_short"

    def test_too_few_words(self) -> None:
        # At least 15 chars but fewer than MIN_REFINABLE_WORDS (4)
        assert should_skip_refinement("hello everybody!") == "too_few_words"
        # 3 words, 24 chars — passes char check, fails word check
        assert should_skip_refinement("absolutely wonderful day") == "too_few_words"

    def test_three_words_long_enough_chars_still_skipped(self) -> None:
        # 3 words, over 15 chars — should skip (too few words)
        result = should_skip_refinement("extraordinarily long word")
        assert result == "too_few_words"

    def test_filler_only_single(self) -> None:
        # Must pass char+word thresholds first; use enough filler words
        assert should_skip_refinement("um um uh um yeah like") == "filler_only"

    def test_filler_only_mixed(self) -> None:
        assert should_skip_refinement("uh yeah um okay like") == "filler_only"

    def test_filler_only_with_punctuation(self) -> None:
        assert should_skip_refinement("um, uh, yeah, okay...") == "filler_only"

    def test_filler_only_case_insensitive(self) -> None:
        assert should_skip_refinement("Um Uh Yeah Okay Like") == "filler_only"

    # ── Should NOT skip ─────────────────────────────────────────────────

    def test_normal_short_sentence(self) -> None:
        assert should_skip_refinement("i went to the store") is None

    def test_normal_medium_sentence(self) -> None:
        text = "the meeting is scheduled for three oclock tomorrow afternoon"
        assert should_skip_refinement(text) is None

    def test_normal_long_text(self) -> None:
        text = (
            "so the main issue with the current implementation is that we are "
            "loading the model every single time a request comes in which is "
            "absolutely insane from a performance perspective"
        )
        assert should_skip_refinement(text) is None

    def test_text_with_fillers_mixed_with_content(self) -> None:
        # Has fillers but also substantive content — should refine
        text = "um so basically the server crashed yesterday"
        assert should_skip_refinement(text) is None

    def test_exactly_at_word_threshold(self) -> None:
        # Exactly MIN_REFINABLE_WORDS words — should proceed
        text = "one two three four"
        assert should_skip_refinement(text) is None

    def test_exactly_at_char_threshold(self) -> None:
        # Exactly MIN_REFINABLE_CHARS chars with enough words
        text = "a b c d e f g h i"  # 17 chars, 9 words
        assert should_skip_refinement(text) is None

    # ── Phase 2B: Score-based skip ──────────────────────────────────────

    def test_clean_text_skipped_by_score(self) -> None:
        text = "I went to the store and bought some groceries. The weather was nice today."
        result = should_skip_refinement(text)
        assert result == "low_refinement_need"

    def test_noisy_asr_not_skipped_by_score(self) -> None:
        text = "um yeah so basically the the meeting is at uh three oclock tomorrow and we need to prepare"
        assert should_skip_refinement(text) is None

    def test_borderline_text_not_skipped(self) -> None:
        # Text with some issues but not terrible — should proceed
        text = "so the main problem is that we keep running out of memory during peak hours"
        assert should_skip_refinement(text) is None


class TestThresholdConstants:
    """Verify thresholds are sane."""

    def test_min_words_is_reasonable(self) -> None:
        assert 2 <= MIN_REFINABLE_WORDS <= 10

    def test_min_chars_is_reasonable(self) -> None:
        assert 10 <= MIN_REFINABLE_CHARS <= 50

    def test_skip_score_threshold_is_conservative(self) -> None:
        # Threshold must be low enough that messy text never gets skipped
        assert 0.05 <= SKIP_SCORE_THRESHOLD <= 0.3


# ===========================================================================
# Phase 2B: Refinement-need scoring
# ===========================================================================


class TestScoreRefinementNeed:
    """score_refinement_need returns 0.0–1.0 based on text quality signals."""

    # ── Edge cases ──────────────────────────────────────────────────────

    def test_empty_returns_max(self) -> None:
        assert score_refinement_need("") == 1.0

    def test_none_returns_max(self) -> None:
        assert score_refinement_need(None) == 1.0  # type: ignore[arg-type]

    def test_whitespace_returns_max(self) -> None:
        assert score_refinement_need("   \n  ") == 1.0

    def test_too_few_words_returns_max(self) -> None:
        assert score_refinement_need("hi there buddy") == 1.0

    # ── Clean text should score low ─────────────────────────────────────

    def test_clean_well_punctuated_text_scores_low(self) -> None:
        text = "The server was restarted at noon. All services came back online within five minutes. No data was lost."
        score = score_refinement_need(text)
        assert score < 0.3, f"Clean text scored too high: {score}"

    def test_clean_single_sentence_scores_moderate(self) -> None:
        # Single sentence = no run-on, but limited punctuation signal
        text = "The quarterly revenue report shows strong growth in all segments."
        score = score_refinement_need(text)
        assert score < 0.4, f"Clean single sentence scored too high: {score}"

    # ── Messy text should score high ────────────────────────────────────

    def test_no_punctuation_scores_high(self) -> None:
        text = "so basically the server crashed and we lost all our data and nobody knew what to do about it"
        score = score_refinement_need(text)
        assert score > 0.5, f"No punctuation text scored too low: {score}"

    def test_filler_heavy_text_scores_high(self) -> None:
        text = "um so basically like the um thing is that uh we basically need to um figure this out"
        score = score_refinement_need(text)
        assert score > 0.5, f"Filler-heavy text scored too low: {score}"

    def test_no_caps_no_punct_scores_very_high(self) -> None:
        text = "the server went down and we lost all the data and then the backup failed too and nobody could figure out what happened so we just sat there waiting for someone to fix it"
        score = score_refinement_need(text)
        assert score > 0.5, f"No caps/punct text scored too low: {score}"

    def test_repeated_words_increase_score(self) -> None:
        clean = "The meeting is at three. Please bring the report."
        stuttered = "The the meeting is is at three. Please bring the the report."
        score_clean = score_refinement_need(clean)
        score_stutter = score_refinement_need(stuttered)
        assert score_stutter > score_clean, (
            f"Stuttered text ({score_stutter}) should score higher than clean ({score_clean})"
        )

    # ── Score range ─────────────────────────────────────────────────────

    def test_score_is_bounded(self) -> None:
        texts = [
            "Hello world, this is a test.",
            "um like so basically uh the thing is yeah",
            "the server went down and we lost all the data and then everything broke",
            "The server was restarted at noon. All services resumed. No data loss occurred.",
        ]
        for text in texts:
            score = score_refinement_need(text)
            assert 0.0 <= score <= 1.0, f"Score {score} out of bounds for: {text[:50]}"

    # ── Relative ordering ───────────────────────────────────────────────

    def test_clean_scores_lower_than_messy(self) -> None:
        clean = "The meeting starts at three o'clock. Please bring the quarterly report. Coffee will be provided."
        messy = "um so like the meeting um starts at three oclock and uh please bring the quarterly report and like coffee will be provided"
        assert score_refinement_need(clean) < score_refinement_need(messy)
