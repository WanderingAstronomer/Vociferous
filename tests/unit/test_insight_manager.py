"""
InsightManager unit tests.

Tests cache, threshold-based scheduling, and prompt-leak detection guard.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.core.insight_manager import InsightManager
from src.refinement.prompt_builder import PromptBuilder

# ── Inline Cache ──────────────────────────────────────────────────────────


class TestInsightManagerCache:
    def test_empty_cache_returns_empty_text(self, tmp_path: Path) -> None:
        manager, _ = _make_manager_with_emit(tmp_path, "unused")
        assert manager.cached_text == ""

    def test_cache_persists_after_generation(self, tmp_path: Path) -> None:
        manager, emit = _make_manager_with_emit(tmp_path, "Great pace at 150 wpm.")
        manager._generate_task()
        assert manager.cached_text == "Great pace at 150 wpm."
        # Verify on-disk persistence
        cache_data = json.loads(manager._cache_path.read_text())
        assert cache_data["text"] == "Great pace at 150 wpm."
        assert "generated_at" in cache_data


# ── Threshold-Based Scheduling ────────────────────────────────────────────


class TestInsightManagerThresholds:
    """Verify that regeneration fires only when a word-count threshold is crossed."""

    def test_first_generation_always_fires(self, tmp_path: Path) -> None:
        manager, emit = _make_manager_with_emit(tmp_path, "First insight.", today_words=100)
        manager._generate_task()
        emit.assert_called_once()

    def test_no_regeneration_within_same_bracket(self, tmp_path: Path) -> None:
        """After generating at 600 words, 800 words (same 500-bracket) should not regenerate."""
        manager, emit = _make_manager_with_emit(tmp_path, "Insight.", today_words=600, thresholds=(500, 1000))
        manager._generate_task()
        emit.reset_mock()

        # Update stats to 800 words (still in the 500 bracket)
        manager._get_stats = lambda: _make_stats(today_words=800)
        assert manager._should_regenerate(800) is False

    def test_regeneration_on_threshold_crossing(self, tmp_path: Path) -> None:
        """After generating at 600 words, 1100 words (crossed 1000) should regenerate."""
        manager, emit = _make_manager_with_emit(tmp_path, "Insight.", today_words=600, thresholds=(500, 1000))
        manager._generate_task()
        emit.reset_mock()

        assert manager._should_regenerate(1100) is True

    def test_multi_threshold_skip_counts_as_one(self, tmp_path: Path) -> None:
        """Jumping from 0 to 6000 words crosses multiple thresholds but should_regenerate is just True."""
        manager, _ = _make_manager_with_emit(tmp_path, "Insight.", today_words=0, thresholds=(500, 1000, 2500, 5000))
        # Cache exists but at bracket 0
        manager._save_cache("old", 0)
        assert manager._should_regenerate(6000) is True

    def test_below_all_thresholds_no_regeneration(self, tmp_path: Path) -> None:
        """If today_words hasn't reached the first threshold, skip."""
        manager, _ = _make_manager_with_emit(tmp_path, "Insight.", today_words=100, thresholds=(500, 1000))
        # Generate once (first time always fires since cache is empty)
        manager._generate_task()
        # Now 200 words — still below first threshold
        assert manager._should_regenerate(200) is False


# ── Leak Guard ────────────────────────────────────────────────────────────


class TestInsightManagerLeakGuard:
    """Verify that prompt fragments in SLM output are detected and rejected."""

    def test_clean_output_is_accepted(self, tmp_path: Path) -> None:
        manager, emit = _make_manager_with_emit(tmp_path, "Great pace at 150 wpm — keep it up.")
        manager._generate_task()
        emit.assert_called_once()
        assert "Great pace" in emit.call_args[0][1]["text"]

    def test_leaked_prompt_fragment_is_rejected(self, tmp_path: Path) -> None:
        manager, emit = _make_manager_with_emit(
            tmp_path,
            "Write the dashboard summary using only the facts below.",
        )
        manager._generate_task()
        emit.assert_not_called()

    def test_leaked_no_think_is_rejected(self, tmp_path: Path) -> None:
        manager, emit = _make_manager_with_emit(tmp_path, "/no_think\n\nSome output")
        manager._generate_task()
        emit.assert_not_called()

    def test_leaked_chatml_token_is_rejected(self, tmp_path: Path) -> None:
        manager, emit = _make_manager_with_emit(tmp_path, "Text <|im_start|>system more text")
        manager._generate_task()
        emit.assert_not_called()

    def test_leaked_paragraph_marker_is_rejected(self, tmp_path: Path) -> None:
        manager, emit = _make_manager_with_emit(tmp_path, "PARAGRAPH 1 — Today you spoke 500 words.")
        manager._generate_task()
        emit.assert_not_called()

    def test_empty_output_not_emitted(self, tmp_path: Path) -> None:
        manager, emit = _make_manager_with_emit(tmp_path, "")
        manager._generate_task()
        emit.assert_not_called()


class TestInsightManagerPromptContract:
    def test_generation_uses_compact_system_prompt_and_fact_user_prompt(self, tmp_path: Path) -> None:
        manager, _ = _make_manager_with_emit(tmp_path, "Tight summary.")

        manager._generate_task()

        kwargs = manager._slm_provider().generate_custom_sync.call_args.kwargs
        assert kwargs["system_prompt"] == PromptBuilder.ANALYTICS_SYSTEM_PROMPT
        assert "Daily highlights:" in kwargs["user_prompt"]
        assert "Long-term highlights:" in kwargs["user_prompt"]
        assert "- Words today: 500." in kwargs["user_prompt"]
        assert "- Total words captured: 1,000 across 10 transcriptions." in kwargs["user_prompt"]
        assert kwargs["temperature"] == 0.4
        assert kwargs["use_thinking"] is False

    def test_zero_today_words_marks_daily_highlights_none(self, tmp_path: Path) -> None:
        manager, _ = _make_manager_with_emit(tmp_path, "Long-term only.", today_words=0)

        manager._generate_task()

        kwargs = manager._slm_provider().generate_custom_sync.call_args.kwargs
        assert "Daily highlights:\n- none" in kwargs["user_prompt"]


# ── Helpers ───────────────────────────────────────────────────────────────


def _make_stats(today_words: int = 500) -> dict:
    return {
        "count": 10,
        "total_words": 1000,
        "time_saved_seconds": 300,
        "avg_wpm": 150,
        "verbatim_filler_count": 5,
        "verbatim_filler_density": 0.005,
        "verbatim_avg_fk_grade": 8.0,
        "refined_count": 0,
        "refined_filler_count": 0,
        "refined_filler_density": 0,
        "refined_avg_fk_grade": 0,
        "avg_transcription_speed_x": 5.0,
        "transcripts_with_transcription_time": 8,
        "avg_refinement_wpm": 0,
        "transcripts_with_refinement_time": 0,
        "current_streak": 3,
        "longest_streak": 7,
        "today_count": 4,
        "today_words": today_words,
        "days_active_this_week": 3,
    }


def _make_manager_with_emit(
    tmp_path: Path,
    slm_result: str,
    today_words: int = 500,
    thresholds: tuple[int, ...] = (500, 1000, 2500, 5000, 10_000),
) -> tuple[InsightManager, MagicMock]:
    """Create an InsightManager wired to a mock SLM that returns `slm_result`."""
    mock_slm = MagicMock()
    mock_slm.generate_custom_sync.return_value = slm_result

    import src.services.slm_types as slm_types

    mock_slm.state = slm_types.SLMState.READY

    emit = MagicMock()

    manager = InsightManager(
        slm_runtime_provider=lambda: mock_slm,
        event_emitter=emit,
        stats_provider=lambda: _make_stats(today_words),
        daily_word_thresholds=thresholds,
        cache_filename=f"test_cache_{id(mock_slm)}.json",
    )
    # Override cache path to use tmp_path
    manager._cache_path = tmp_path / "test_cache.json"
    manager._cache = {}

    return manager, emit
