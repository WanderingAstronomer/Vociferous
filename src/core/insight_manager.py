"""
Insight Manager — Unified SLM analytics paragraph generation.

Produces a single analytics insight shared by both UserView and TranscribeView.
Regeneration is triggered by daily word-count thresholds (ISS-098), not by
fixed transcript counts or manual refresh buttons.

Responsibilities:
- Maintain a simple JSON cache of the last generated insight + timestamp.
- Decide when regeneration is due based on daily word-count thresholds.
- Run SLM inference on a background thread, never blocking anything.
- Emit 'insight_ready' via the EventBus when new content is available.
- Respect the refinement job priority: skip if SLM is already INFERRING.

Architecture constraint:
    The coordinator calls maybe_schedule() after each transcription_complete event
    and when the SLM becomes idle. This is the only trigger. We do NOT poll on a
    timer. We do NOT chase view navigation.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from src.core.resource_manager import ResourceManager
from src.refinement.prompt_builder import PromptBuilder

if TYPE_CHECKING:
    from src.services.slm_runtime import SLMRuntime

logger = logging.getLogger(__name__)

# Minimum word count for a meaningful transcript to trigger threshold check.
_MIN_TRANSCRIPT_WORDS = 100

# Default daily word-count thresholds at which insight regeneration fires.
_DEFAULT_THRESHOLDS: tuple[int, ...] = (500, 1000, 2500, 5000, 10_000)


class InsightManager:
    """
    Manages lazy background analytics insight generation.

    Wires together:
    - On-disk JSON cache (inlined, no separate class)
    - SLMRuntime (inference, accessed via a provider so it can be None when disabled)
    - EventBus (emit 'insight_ready')
    - Stats provider (returns pre-computed usage statistics dict)
    """

    def __init__(
        self,
        slm_runtime_provider: Callable[[], "SLMRuntime | None"],
        event_emitter: Callable[[str, dict], None],
        stats_provider: Callable[[], dict[str, Any]],
        daily_word_thresholds: tuple[int, ...] = _DEFAULT_THRESHOLDS,
        prompt_template: str = PromptBuilder.ANALYTICS_TEMPLATE,
        cache_filename: str = "analytics_insight_cache.json",
        event_name: str = "insight_ready",
    ) -> None:
        self._slm_provider = slm_runtime_provider
        self._emit = event_emitter
        self._get_stats = stats_provider
        self._prompt_template = prompt_template
        self._event_name = event_name
        self._thresholds = sorted(daily_word_thresholds)

        # Inline cache: just a dict backed by a JSON file.
        self._cache_path = ResourceManager.get_user_cache_dir("insights") / cache_filename
        self._cache: dict = {}
        if self._cache_path.exists():
            try:
                self._cache = json.loads(self._cache_path.read_text(encoding="utf-8"))
            except Exception:
                logger.warning("Failed to read insight cache — starting fresh")

        self._lock = threading.Lock()
        self._generating = False
        # Track the today_words value at last generation to detect threshold crossings.
        self._last_generated_today_words: int = self._cache.get("last_today_words", 0)

    # ── Public API ──────────────────────────────────────────────────────────

    @property
    def cached_text(self) -> str:
        """Return whatever is in the cache right now, or empty string."""
        return self._cache.get("text", "")

    def maybe_schedule(self) -> None:
        """
        Called after every transcription_complete and when SLM becomes idle.
        Checks whether a threshold has been crossed and, if so, starts a
        background thread to regenerate.

        Conditions to proceed:
        1. today_words has crossed a threshold since last generation.
        2. SLM runtime is loaded and READY.
        3. No generation is already in flight.
        """
        with self._lock:
            if self._generating:
                logger.debug("Insight: generation already in flight, skipping")
                return

            slm = self._slm_provider()
            if slm is None:
                logger.info("Insight: SLM unavailable, skipping")
                return

            from src.services.slm_types import SLMState

            if slm.state != SLMState.READY:
                logger.info("Insight: SLM not ready (state=%s), skipping", slm.state)
                return

            # Check threshold crossing. We fetch stats here (cheap dict lookup)
            # to determine today_words before committing to a full generation.
            stats = self._get_stats()
            if not stats or stats.get("count", 0) < 3:
                return

            today_words = stats.get("today_words", 0)
            if not self._should_regenerate(today_words):
                logger.debug("Insight: no threshold crossed (today_words=%d, last=%d), skipping",
                             today_words, self._last_generated_today_words)
                return

            self._generating = True

        logger.info("Insight: scheduling background generation (threshold crossed, today_words=%d)", today_words)
        thread = threading.Thread(target=self._generate_task, daemon=True)
        thread.start()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _should_regenerate(self, today_words: int) -> bool:
        """Return True if today_words has crossed a threshold since last generation."""
        # No cache at all → always generate.
        if not self._cache.get("text"):
            return True

        # Find the highest threshold that today_words has reached.
        current_bracket = 0
        for t in self._thresholds:
            if today_words >= t:
                current_bracket = t
            else:
                break

        # Find the bracket the last generation was in.
        last_bracket = 0
        for t in self._thresholds:
            if self._last_generated_today_words >= t:
                last_bracket = t
            else:
                break

        return current_bracket > last_bracket

    @staticmethod
    def _fmt_duration(seconds: float) -> str:
        """Human-readable duration for prompt context."""
        if seconds < 60:
            return f"{round(seconds)}s"
        minutes = int(seconds // 60)
        if minutes < 60:
            return f"{minutes}m"
        hours = minutes // 60
        remaining_minutes = minutes % 60
        return f"{hours}h {remaining_minutes}m" if remaining_minutes else f"{hours}h"

    def _save_cache(self, text: str, today_words: int) -> None:
        """Update cache in memory and on disk."""
        self._cache = {
            "text": text,
            "generated_at": time.time(),
            "last_today_words": today_words,
        }
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(json.dumps(self._cache, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error("Failed to save insight cache: %s", e)

    def _generate_task(self) -> None:
        try:
            stats = self._get_stats()
            if not stats or stats.get("count", 0) < 3:
                logger.info("Insight: not enough data for meaningful insight, skipping")
                return

            total_words = stats.get("total_words", 0)
            today_words = stats.get("today_words", 0)

            # Build the refinement comparison section if data exists
            refined_count = stats.get("refined_count", 0)
            if refined_count > 0:
                refinement_section = (
                    f"Refined text quality (after AI refinement — {refined_count} transcripts):\n"
                    f"- Vocabulary diversity: {stats.get('refined_vocab_ratio', 0):.0%}\n"
                    f"- Filler words remaining: {stats.get('refined_filler_count', 0)} "
                    f"({stats.get('refined_filler_density', 0):.1%} of words)\n"
                    f"- Average Flesch-Kincaid grade: {stats.get('refined_avg_fk_grade', 0)}\n"
                    f"- Average sentence length: {stats.get('refined_avg_sentence_length', 0)} words\n"
                    f"- Fillers removed by refinement: "
                    f"{stats.get('verbatim_filler_count', 0) - stats.get('refined_filler_count', 0)}\n\n"
                )
            else:
                refinement_section = ""

            # Format top fillers for display
            filler_breakdown = stats.get("filler_breakdown", {})
            if filler_breakdown:
                top_items = sorted(filler_breakdown.items(), key=lambda x: x[1], reverse=True)[:5]
                top_fillers_str = ", ".join(f'"{w}" ({n})' for w, n in top_items)
            else:
                top_fillers_str = "none detected"

            # Full format dict — every stat available to the template.
            fmt = {
                # Session-level
                "today_count": stats.get("today_count", 0),
                "today_words": f"{today_words:,}",
                "days_active_this_week": stats.get("days_active_this_week", 0),
                # All-time overview
                "count": stats.get("count", 0),
                "total_words": f"{total_words:,}",
                "recorded_time": self._fmt_duration(stats.get("recorded_seconds", 0)),
                "speech_time": self._fmt_duration(stats.get("total_speech_seconds", 0)),
                "silence_time": self._fmt_duration(stats.get("total_silence_seconds", 0)),
                "time_saved": self._fmt_duration(stats.get("time_saved_seconds", 0)),
                "avg_length": self._fmt_duration(stats.get("avg_seconds", 0)),
                "avg_pace": stats.get("avg_wpm", 0),
                "current_streak": stats.get("current_streak", 0),
                "longest_streak": stats.get("longest_streak", 0),
                # Verbatim pipeline
                "verbatim_vocab_pct": f"{stats.get('verbatim_vocab_ratio', 0):.0%}",
                "verbatim_fillers": stats.get("verbatim_filler_count", 0),
                "verbatim_filler_density": f"{stats.get('verbatim_filler_density', 0):.1%}",
                "verbatim_fk_grade": stats.get("verbatim_avg_fk_grade", 0),
                "verbatim_avg_sentence_len": stats.get("verbatim_avg_sentence_length", 0),
                "top_fillers": top_fillers_str,
                # Refinement section (pre-built block or empty string)
                "refinement_section": refinement_section,
                "refined_count": refined_count,
                # Processing performance
                "transcription_speed": stats.get("avg_transcription_speed_x", 0),
                "transcripts_with_transcription_time": stats.get("transcripts_with_transcription_time", 0),
                "refinement_wpm": stats.get("avg_refinement_wpm", 0),
                "transcripts_with_refinement_time": stats.get("transcripts_with_refinement_time", 0),
                "refinement_time_saved": self._fmt_duration(stats.get("refinement_time_saved_seconds", 0)),
            }
            prompt = self._prompt_template.format_map(fmt)

            slm = self._slm_provider()
            if slm is None:
                logger.warning("Insight: SLM disappeared before generation could start")
                return

            from src.services.slm_types import SLMState

            if slm.state != SLMState.READY:
                logger.warning("Insight: SLM no longer ready (%s), aborting", slm.state)
                return

            logger.info("Insight: running SLM inference...")
            result = slm.generate_custom_sync(
                system_prompt=prompt,
                user_prompt="Generate the analytics insight based on the provided statistics.",
                max_tokens=250,
                temperature=0.7,
                use_thinking=True,
            )

            if result and result.strip():
                clean = result.strip()
                # Guard: reject output that looks like leaked prompt fragments.
                _LEAK_MARKERS = (
                    "speech-to-text application",
                    "speech-to-text desktop application",
                    "usage statistics",
                    "Do NOT begin with",
                    "Do not use bullet points",
                    "Write exactly TWO",
                    "PARAGRAPH 1",
                    "PARAGRAPH 2",
                    "<|im_start|>",
                    "/no_think",
                )
                if any(marker in clean for marker in _LEAK_MARKERS):
                    logger.warning("Insight: output appears to contain leaked prompt fragments, discarding")
                    return
                self._save_cache(clean, today_words)
                self._last_generated_today_words = today_words
                self._emit(self._event_name, {"text": clean})
                logger.info("Insight: generation complete, cache updated")

        except Exception:
            logger.exception("Insight: generation failed")
        finally:
            with self._lock:
                self._generating = False
