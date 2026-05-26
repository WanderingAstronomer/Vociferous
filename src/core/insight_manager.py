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
from typing import TYPE_CHECKING, Any, Callable

from src.core.insights.formatting import (
    combine_text,
    highlight_block as _highlight_block,
    parse_generated_insight,
    split_legacy_text,
    stats_fingerprint,
    today_key,
)
from src.core.insights.highlights import build_daily_highlights, build_long_term_highlights
from src.core.resource_manager import ResourceManager
from src.refinement.prompt_builder import PromptBuilder

if TYPE_CHECKING:
    from src.services.slm_runtime import SLMRuntime

logger = logging.getLogger(__name__)

InsightPayload = dict[str, str | float | bool | list[str]]

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
        return str(self.cached_payload.get("text", ""))

    @property
    def cached_payload(self) -> InsightPayload:
        """Return the structured insight cache payload consumed by the API and WebSocket."""
        return self._cache_payload()

    def mark_dirty(self, reason: str, *, schedule: bool = True) -> None:
        """Mark cached insight text stale and optionally try to regenerate immediately."""
        clean_reason = reason.strip() or "analytics_data_changed"
        with self._lock:
            reasons = [str(r) for r in self._cache.get("dirty_reasons", []) if isinstance(r, str)]
            if clean_reason not in reasons:
                reasons.append(clean_reason)
            self._cache["dirty"] = True
            self._cache["dirty_reasons"] = reasons[-8:]
            self._write_cache()

        if schedule:
            self.maybe_schedule(reason=clean_reason)

    def clear_cache(self, reason: str = "analytics_data_cleared") -> None:
        """Clear stale insight text when the analytics population is no longer meaningful."""
        with self._lock:
            self._cache = {}
            self._last_generated_today_words = 0
            try:
                self._cache_path.unlink(missing_ok=True)
            except Exception as e:
                logger.debug("Failed to remove insight cache after %s: %s", reason, e)
        self._emit(self._event_name, self._cache_payload())

    def request_refresh(self) -> InsightPayload:
        """Force a low-priority refresh attempt and return the current cached payload."""
        self.mark_dirty("manual_refresh")
        return self.cached_payload

    def maybe_schedule(
        self, new_transcript_words: int | None = None, *, reason: str = "transcription_completed"
    ) -> None:
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
                if self._cache.get("text") or self._cache.get("daily_text") or self._cache.get("lifetime_text"):
                    self._cache = {}
                    self._last_generated_today_words = 0
                    self._write_cache()
                    emit_payload = self._cache_payload()
                else:
                    emit_payload = None
            else:
                emit_payload = None

            if emit_payload is not None:
                self._emit(self._event_name, emit_payload)
            if not stats or stats.get("count", 0) < 3:
                return

            if not self._should_regenerate(stats, reason=reason):
                logger.debug(
                    "Insight: no regeneration needed (reason=%s, today_words=%d, last=%d), skipping",
                    reason,
                    int(stats.get("today_words", 0) or 0),
                    self._last_generated_today_words,
                )
                return

            self._generating = True

        today_words = int(stats.get("today_words", 0) or 0)
        logger.info("Insight: scheduling background generation (reason=%s, today_words=%d)", reason, today_words)
        thread = threading.Thread(target=self._generate_task, args=(reason,), daemon=True)
        thread.start()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _cache_payload(self) -> InsightPayload:
        today = today_key()
        generated_for_date = str(self._cache.get("generated_for_date") or "")
        text = str(self._cache.get("text") or "")
        daily_text = str(self._cache.get("daily_text") or "")
        lifetime_text = str(self._cache.get("lifetime_text") or "")

        if text and not (daily_text or lifetime_text):
            daily_text, lifetime_text = split_legacy_text(text, has_daily=generated_for_date == today)

        if generated_for_date != today:
            daily_text = ""

        combined = combine_text(daily_text, lifetime_text)
        dirty_reasons = [str(r) for r in self._cache.get("dirty_reasons", []) if isinstance(r, str)]
        return {
            "text": combined,
            "daily_text": daily_text.strip(),
            "lifetime_text": lifetime_text.strip(),
            "generated_at": float(self._cache.get("generated_at", 0.0) or 0.0),
            "generated_for_date": generated_for_date,
            "stale": bool(self._cache.get("dirty")) or (bool(text or daily_text) and generated_for_date != today),
            "dirty_reasons": dirty_reasons,
        }

    def _write_cache(self) -> None:
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(json.dumps(self._cache, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error("Failed to save insight cache: %s", e)

    def _should_regenerate(self, stats: dict[str, Any], *, reason: str = "transcription_completed") -> bool:
        """Return True if today_words has crossed a threshold or the
        growth-and-time freshness rule (ISS-122) has tripped since last generation."""
        today_words = int(stats.get("today_words", 0) or 0)
        if reason == "manual_refresh":
            return True

        # No cache at all → always generate.
        if not (self._cache.get("text") or self._cache.get("daily_text") or self._cache.get("lifetime_text")):
            return True

        if self._cache.get("dirty"):
            return True

        if self._cache.get("generated_for_date") != today_key() and today_words > 0:
            return True

        fingerprint = stats_fingerprint(stats)
        if self._cache.get("stats_fingerprint") and self._cache.get("stats_fingerprint") != fingerprint:
            generated_at = float(self._cache.get("generated_at", 0.0) or 0.0)
            if generated_at <= 0.0 or (time.time() - generated_at) >= _FRESHNESS_MIN_INTERVAL_S:
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

    def _save_cache(self, daily_text: str, lifetime_text: str, today_words: int, stats: dict[str, Any]) -> None:
        """Update cache in memory and on disk."""
        text = combine_text(daily_text, lifetime_text)
        with self._lock:
            self._cache = {
                "text": text,
                "daily_text": daily_text,
                "lifetime_text": lifetime_text,
                "generated_at": time.time(),
                "generated_for_date": today_key(),
                "last_today_words": today_words,
                "stats_fingerprint": stats_fingerprint(stats),
                "dirty": False,
                "dirty_reasons": [],
            }
            self._last_generated_today_words = today_words
            self._write_cache()

    def _generate_task(self, reason: str = "scheduled") -> None:
        try:
            stats = self._get_stats()
            if not stats or stats.get("count", 0) < 3:
                logger.info("Insight: not enough data for meaningful insight, skipping")
                self.clear_cache("insufficient_data")
                return

            today_words = int(stats.get("today_words", 0) or 0)
            daily_highlights = build_daily_highlights(stats)
            long_term_highlights = build_long_term_highlights(stats)
            fmt = {
                "daily_highlights": _highlight_block(daily_highlights),
                "long_term_highlights": _highlight_block(long_term_highlights),
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
                clean_lower = clean.lower()
                if any(marker.lower() in clean_lower for marker in _LEAK_MARKERS):
                    logger.warning("Insight: output appears to contain leaked prompt fragments, discarding")
                    return
                daily_text, lifetime_text = parse_generated_insight(clean, has_daily=bool(daily_highlights))
                if not daily_text and not lifetime_text:
                    logger.warning("Insight: output could not be parsed into structured fields, discarding")
                    return
                self._save_cache(daily_text, lifetime_text, today_words, stats)
                self._emit(self._event_name, self._cache_payload())
                logger.info("Insight: generation complete, cache updated (reason=%s)", reason)

        except Exception:
            logger.exception("Insight: generation failed")
        finally:
            with self._lock:
                self._generating = False
