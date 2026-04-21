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
# Per ISS-119: enforced explicitly at scheduling time so trivially short
# transcripts cannot drag insight regeneration around.
_MIN_TRANSCRIPT_WORDS = 100

# Default daily word-count thresholds at which insight regeneration fires.
_DEFAULT_THRESHOLDS: tuple[int, ...] = (500, 1000, 2500, 5000, 10_000)

# Per ISS-122: between bracket crossings the cache can still go stale when
# users keep talking. These two constants form a growth-and-time freshness
# rule that runs in addition to bracket crossings.
_FRESHNESS_GROWTH_WORDS = 250
_FRESHNESS_MIN_INTERVAL_S = 120.0


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

    def maybe_schedule(self, new_transcript_words: int | None = None) -> None:
        """
        Called after every transcription_complete and when SLM becomes idle.
        Checks whether a threshold has been crossed and, if so, starts a
        background thread to regenerate.

        Conditions to proceed:
        1. If `new_transcript_words` is given, it must be >= _MIN_TRANSCRIPT_WORDS.
           This is the explicit per-transcript gate (ISS-119) that prevents a
           burst of trivially short transcripts from poking the SLM.
        2. today_words has crossed a threshold OR the freshness growth rule
           has tripped since last generation (ISS-122).
        3. SLM runtime is loaded and READY.
        4. No generation is already in flight.
        """
        if new_transcript_words is not None and new_transcript_words < _MIN_TRANSCRIPT_WORDS:
            logger.debug(
                "Insight: skipping schedule, transcript word count %d below minimum %d",
                new_transcript_words,
                _MIN_TRANSCRIPT_WORDS,
            )
            return

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
                logger.debug(
                    "Insight: no threshold crossed (today_words=%d, last=%d), skipping",
                    today_words,
                    self._last_generated_today_words,
                )
                return

            self._generating = True

        logger.info("Insight: scheduling background generation (threshold crossed, today_words=%d)", today_words)
        thread = threading.Thread(target=self._generate_task, daemon=True)
        thread.start()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _should_regenerate(self, today_words: int) -> bool:
        """Return True if today_words has crossed a threshold or the
        growth-and-time freshness rule (ISS-122) has tripped since last generation."""
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

        if current_bracket > last_bracket:
            return True

        # Growth-and-time freshness rule: between bracket crossings the
        # cached insight can lag obvious activity. Refresh once enough new
        # words have accumulated AND enough wall time has passed since the
        # last generation. The time gate keeps this from spamming.
        growth = today_words - self._last_generated_today_words
        if growth >= _FRESHNESS_GROWTH_WORDS:
            generated_at = float(self._cache.get("generated_at", 0.0) or 0.0)
            if generated_at <= 0.0 or (time.time() - generated_at) >= _FRESHNESS_MIN_INTERVAL_S:
                return True

        return False

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

    @staticmethod
    def _fmt_float(value: Any, decimals: int = 1) -> str:
        """Format numeric values consistently for prompt highlights."""
        try:
            return f"{float(value):.{decimals}f}"
        except (TypeError, ValueError):
            return f"{0.0:.{decimals}f}"

    @staticmethod
    def _highlight_block(lines: list[str]) -> str:
        """Render curated highlight lines for the analytics prompt."""
        if not lines:
            return "- none"
        return "\n".join(f"- {line}" for line in lines)

    def _build_daily_highlights(self, stats: dict[str, Any]) -> list[str]:
        """Pick the exact daily facts the SLM is allowed to mention."""
        today_words = int(stats.get("today_words", 0) or 0)
        if today_words <= 0:
            return []

        highlights = [f"Words today: {today_words:,}."]

        today_count = int(stats.get("today_count", 0) or 0)
        if today_count > 0:
            highlights.append(f"Transcriptions today: {today_count}.")

        days_active_this_week = int(stats.get("days_active_this_week", 0) or 0)
        if days_active_this_week > 0:
            highlights.append(f"Active days this week: {days_active_this_week}.")

        current_streak = int(stats.get("current_streak", 0) or 0)
        if current_streak > 0 and len(highlights) < 3:
            highlights.append(f"Current streak: {current_streak} days.")

        return highlights[:3]

    def _build_refinement_impact_highlight(self, stats: dict[str, Any]) -> str | None:
        """Build one exact refinement-impact fact instead of asking the SLM to infer one."""
        refined_count = int(stats.get("refined_count", 0) or 0)
        if refined_count <= 0:
            return None

        raw_fillers = int(stats.get("verbatim_filler_count", 0) or 0)
        refined_fillers = int(stats.get("refined_filler_count", 0) or 0)
        raw_density = float(stats.get("verbatim_filler_density", 0) or 0)
        refined_density = float(stats.get("refined_filler_density", 0) or 0)
        raw_fk = float(stats.get("verbatim_avg_fk_grade", 0) or 0)
        refined_fk = float(stats.get("refined_avg_fk_grade", 0) or 0)

        details: list[str] = [f"Refinement sample: {refined_count} transcripts"]
        if raw_fillers or refined_fillers:
            details.append(
                "fillers "
                f"{refined_fillers} ({refined_density:.1%}) after refinement vs "
                f"{raw_fillers} ({raw_density:.1%}) raw"
            )
        if raw_fk or refined_fk:
            details.append(f"FK grade {self._fmt_float(refined_fk)} after refinement vs {self._fmt_float(raw_fk)} raw")
        return "; ".join(details) + "."

    def _build_long_term_highlights(self, stats: dict[str, Any]) -> list[str]:
        """Pick the exact long-term facts the SLM is allowed to mention."""
        total_words = int(stats.get("total_words", 0) or 0)
        total_count = int(stats.get("count", 0) or 0)
        highlights = [f"Total words captured: {total_words:,} across {total_count} transcriptions."]

        time_saved_seconds = float(stats.get("time_saved_seconds", 0) or 0)
        if time_saved_seconds > 0:
            highlights.append(f"Estimated time saved vs typing: {self._fmt_duration(time_saved_seconds)}.")

        refinement_impact = self._build_refinement_impact_highlight(stats)
        if refinement_impact:
            highlights.append(refinement_impact)

        avg_wpm = int(stats.get("avg_wpm", 0) or 0)
        if avg_wpm > 0 and len(highlights) < 3:
            highlights.append(f"Average speaking pace: {avg_wpm} wpm.")

        current_streak = int(stats.get("current_streak", 0) or 0)
        longest_streak = int(stats.get("longest_streak", 0) or 0)
        if len(highlights) < 3 and (current_streak > 0 or longest_streak > 0):
            if current_streak > 0 and longest_streak > 0:
                highlights.append(f"Streaks: current {current_streak} days, longest {longest_streak} days.")
            elif longest_streak > 0:
                highlights.append(f"Longest streak: {longest_streak} days.")
            else:
                highlights.append(f"Current streak: {current_streak} days.")

        avg_transcription_speed = float(stats.get("avg_transcription_speed_x", 0) or 0)
        timed_transcripts = int(stats.get("transcripts_with_transcription_time", 0) or 0)
        if len(highlights) < 3 and avg_transcription_speed > 0 and timed_transcripts > 0:
            highlights.append(
                f"Transcription speed: {self._fmt_float(avg_transcription_speed)}x realtime across {timed_transcripts} samples."
            )

        avg_refinement_wpm = int(stats.get("avg_refinement_wpm", 0) or 0)
        refinement_samples = int(stats.get("transcripts_with_refinement_time", 0) or 0)
        if len(highlights) < 3 and avg_refinement_wpm > 0 and refinement_samples > 0:
            highlights.append(f"Refinement throughput: {avg_refinement_wpm} wpm across {refinement_samples} samples.")

        return highlights[:3]

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

            today_words = stats.get("today_words", 0)
            fmt = {
                "daily_highlights": self._highlight_block(self._build_daily_highlights(stats)),
                "long_term_highlights": self._highlight_block(self._build_long_term_highlights(stats)),
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
                system_prompt=PromptBuilder.ANALYTICS_SYSTEM_PROMPT,
                user_prompt=prompt,
                max_tokens=220,
                temperature=0.4,
                use_thinking=False,
            )

            if result and result.strip():
                clean = result.strip()
                # Guard: reject output that looks like leaked prompt fragments.
                _LEAK_MARKERS = (
                    "speech-to-text application",
                    "speech-to-text desktop application",
                    "usage statistics",
                    "Write the dashboard summary using only the facts below",
                    "Required structure:",
                    "Quote numbers exactly as written above",
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
