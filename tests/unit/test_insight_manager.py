"""
InsightManager unit tests.

Tests cache, scheduling logic, and prompt-leak detection guard.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.core.insight_manager import InsightCache, InsightManager

# ── InsightCache ──────────────────────────────────────────────────────────


class TestInsightCache:
    def test_empty_cache_returns_empty_text(self, tmp_path: Path) -> None:
        cache = InsightCache(tmp_path / "cache.json")
        assert cache.text == ""

    def test_save_and_load(self, tmp_path: Path) -> None:
        cache = InsightCache(tmp_path / "cache.json")
        cache.save("Hello world")
        assert cache.text == "Hello world"

    def test_is_stale_when_empty(self, tmp_path: Path) -> None:
        cache = InsightCache(tmp_path / "cache.json")
        assert cache.is_stale(3600) is True

    def test_not_stale_after_save(self, tmp_path: Path) -> None:
        cache = InsightCache(tmp_path / "cache.json")
        cache.save("Fresh insight")
        assert cache.is_stale(3600) is False

    def test_persists_to_disk(self, tmp_path: Path) -> None:
        path = tmp_path / "cache.json"
        cache = InsightCache(path)
        cache.save("Persisted")
        # Read from disk
        data = json.loads(path.read_text())
        assert data["text"] == "Persisted"
        assert "generated_at" in data


# ── InsightManager Leak Guard ─────────────────────────────────────────────


class TestInsightManagerLeakGuard:
    """Verify that prompt fragments in SLM output are detected and rejected."""

    def _make_manager(
        self,
        tmp_path: Path,
        slm_result: str,
    ) -> tuple[InsightManager, MagicMock]:
        """Create an InsightManager wired to a mock SLM that returns `slm_result`."""
        mock_slm = MagicMock()
        mock_slm.state = MagicMock()
        mock_slm.state.value = "ready"
        mock_slm.generate_custom_sync.return_value = slm_result

        # Patch SLMState check: we need the state comparison to pass
        import src.services.slm_types as slm_types

        mock_slm.state = slm_types.SLMState.READY

        emit = MagicMock()
        stats = {
            "count": 10,
            "total_words": 1000,
            "recorded_seconds": 600,
            "time_saved_seconds": 300,
            "avg_seconds": 60,
            "vocab_ratio": 0.25,
            "total_silence_seconds": 30,
            "filler_count": 5,
        }

        manager = InsightManager(
            slm_runtime_provider=lambda: mock_slm,
            event_emitter=emit,
            stats_provider=lambda: stats,
            cache_filename=f"test_cache_{id(self)}.json",
        )
        # Override cache path to use tmp_path
        manager._cache = InsightCache(tmp_path / "test_cache.json")

        return manager, emit

    def test_clean_output_is_accepted(self, tmp_path: Path) -> None:
        manager, emit = self._make_manager(tmp_path, "Great pace at 150 wpm — keep it up.")
        manager._generate_task()
        emit.assert_called_once()
        assert "Great pace" in emit.call_args[0][1]["text"]

    def test_leaked_prompt_fragment_is_rejected(self, tmp_path: Path) -> None:
        """Output containing 'speech-to-text application' (from our template) is rejected."""
        manager, emit = self._make_manager(
            tmp_path,
            "You are embedded in Vociferous, a local AI-powered speech-to-text application.",
        )
        manager._generate_task()
        emit.assert_not_called()

    def test_leaked_no_think_is_rejected(self, tmp_path: Path) -> None:
        manager, emit = self._make_manager(tmp_path, "/no_think\n\nSome output")
        manager._generate_task()
        emit.assert_not_called()

    def test_leaked_chatml_token_is_rejected(self, tmp_path: Path) -> None:
        manager, emit = self._make_manager(tmp_path, "Text <|im_start|>system more text")
        manager._generate_task()
        emit.assert_not_called()

    def test_empty_output_not_emitted(self, tmp_path: Path) -> None:
        manager, emit = self._make_manager(tmp_path, "")
        manager._generate_task()
        emit.assert_not_called()
