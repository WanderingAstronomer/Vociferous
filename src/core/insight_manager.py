"""
Insight Manager — Lazy background SLM insight generation for the UserView dashboard.

Responsibilities:
- Maintain a simple JSON cache of the last generated insight + timestamp.
- Decide when regeneration is due (configurable TTL, default 24h).
- Run SLM inference on a background thread, never blocking anything.
- Emit 'insight_ready' via the EventBus when new content is available.
- Respect the refinement job priority: skip if SLM is already INFERRING.

Architecture constraint:
    The coordinator calls maybe_schedule() after each transcription_complete event.
    This is the only trigger. We do NOT poll on a timer. We do NOT chase view
    navigation. If the user is actively dictating, the insight gets regenerated
    on the next quiet moment after a transcription finishes.
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

# Backward-compat aliases — canonical templates now live in PromptBuilder.
_INSIGHT_PROMPT = PromptBuilder.INSIGHT_TEMPLATE
_MOTD_PROMPT = PromptBuilder.MOTD_TEMPLATE


class InsightCache:
    """Read/write the on-disk insight cache."""

    def __init__(self, cache_path: Path) -> None:
        self._path = cache_path
        self._data: dict = {}
        # Pre-load on init to avoid read-on-property-access loop
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                logger.warning("Failed to read insight cache — starting fresh")

    def load(self) -> dict:
        """Return cached data (in-memory)."""
        return self._data

    def save(self, text: str) -> None:
        """Update cache in memory and on disk."""
        self._data = {
            "text": text,
            "generated_at": time.time(),
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._data, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error("Failed to save insight cache: %s", e)

    @property
    def text(self) -> str:
        return self.load().get("text", "")

    def is_stale(self, ttl_seconds: float) -> bool:
        data = self.load()
        if not data.get("generated_at"):
            return True
        if (time.time() - data["generated_at"]) > ttl_seconds:
            return True
        return False


class InsightManager:
    """
    Manages lazy background insight generation for the UserView dashboard.

    Wires together:
    - InsightCache (persistence)
    - SLMRuntime (inference, accessed via a provider so it can be None when disabled)
    - EventBus (emit 'insight_ready')
    - Stats provider (returns pre-computed usage statistics dict)
    """

    DEFAULT_TTL_HOURS = 24
    DEFAULT_TTL_TRANSCRIPTS = 5

    def __init__(
        self,
        slm_runtime_provider: Callable[[], "SLMRuntime | None"],
        event_emitter: Callable[[str, dict], None],
        stats_provider: Callable[[], dict[str, Any]],
        ttl_hours: float = DEFAULT_TTL_HOURS,
        ttl_transcripts: int = DEFAULT_TTL_TRANSCRIPTS,
        prompt_template: str = _INSIGHT_PROMPT,
        cache_filename: str = "insight_cache.json",
        event_name: str = "insight_ready",
    ) -> None:
        self._slm_provider = slm_runtime_provider
        self._emit = event_emitter
        self._get_stats = stats_provider
        self._ttl = ttl_hours * 3600
        self._ttl_transcripts = ttl_transcripts
        self._prompt_template = prompt_template
        self._event_name = event_name

        cache_path = ResourceManager.get_user_cache_dir("insights") / cache_filename
        self._cache = InsightCache(cache_path)

        self._lock = threading.Lock()
        self._generating = False
        self._transcripts_since_generation = 0

    # ── Public API ──────────────────────────────────────────────────────────

    @property
    def cached_text(self) -> str:
        """Return whatever is in the cache right now, or empty string."""
        return self._cache.text

    def maybe_schedule(self) -> None:
        """
        Called after every transcription_complete. Checks whether a new insight
        generation is due and, if so, starts a background thread to do it.

        Conditions to proceed:
        1. The cache is stale (older than TTL or enough transcripts have passed).
        2. SLM runtime is loaded and not currently inferring.
        3. No generation is already in flight.
        """
        with self._lock:
            self._transcripts_since_generation += 1

            if self._generating:
                logger.debug("Insight: generation already in flight, skipping")
                return

            if self._transcripts_since_generation < self._ttl_transcripts and not self._cache.is_stale(self._ttl):
                logger.debug("Insight: cache is fresh, skipping generation")
                return

            slm = self._slm_provider()
            if slm is None:
                logger.info("Insight: SLM unavailable (refinement disabled or no model), skipping")
                return

            from src.services.slm_types import SLMState

            if slm.state != SLMState.READY:
                logger.info("Insight: SLM not ready (state=%s, refinement may be disabled), skipping", slm.state)
                return

            self._generating = True

        logger.info("Insight: scheduling background generation")
        t = threading.Thread(target=self._generate_task, daemon=True)
        t.start()

    def request_generation(self) -> bool:
        """Force-trigger generation, bypassing TTL and transcript-count checks.

        Returns ``True`` if generation was started, ``False`` if the SLM is
        unavailable or a generation is already in flight.
        """
        with self._lock:
            if self._generating:
                return False

            slm = self._slm_provider()
            if slm is None:
                return False

            from src.services.slm_types import SLMState

            if slm.state != SLMState.READY:
                return False

            self._generating = True

        logger.info("Insight: manual generation requested")
        t = threading.Thread(target=self._generate_task, daemon=True)
        t.start()
        return True

    # ── Internal ─────────────────────────────────────────────────────────────

    @staticmethod
    def _fmt_duration(seconds: float) -> str:
        """Human-readable duration for prompt context."""
        if seconds < 60:
            return f"{round(seconds)}s"
        m = int(seconds // 60)
        if m < 60:
            return f"{m}m"
        h = m // 60
        rm = m % 60
        return f"{h}h {rm}m" if rm else f"{h}h"

    def _generate_task(self) -> None:
        try:
            stats = self._get_stats()
            if not stats or stats.get("count", 0) < 3:
                logger.info("Insight: not enough data for meaningful insight, skipping")
                return

            total_words = stats.get("total_words", 0)
            speech_seconds = stats.get("recorded_seconds", 0) - stats.get("total_silence_seconds", 0)
            avg_pace = round(total_words / (speech_seconds / 60)) if speech_seconds > 0 else 0
            prompt = self._prompt_template.format(
                count=stats.get("count", 0),
                total_words=f"{total_words:,}",
                recorded_time=self._fmt_duration(stats.get("recorded_seconds", 0)),
                time_saved=self._fmt_duration(stats.get("time_saved_seconds", 0)),
                avg_length=self._fmt_duration(stats.get("avg_seconds", 0)),
                vocab_pct=f"{stats.get('vocab_ratio', 0):.0%}",
                silence=self._fmt_duration(stats.get("total_silence_seconds", 0)),
                fillers=stats.get("filler_count", 0),
                avg_pace=avg_pace,
            )

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
                user_prompt="Generate the insight based on the provided statistics.",
                max_tokens=150,
                temperature=0.7,
            )

            if result and result.strip():
                clean = result.strip()
                # Guard: reject output that looks like leaked prompt fragments.
                # If the model echoed back the system prompt, the output will
                # contain these telltale strings from our templates.
                _LEAK_MARKERS = (
                    "speech-to-text application",
                    "usage statistics",
                    "Do NOT begin with",
                    "Do not use bullet points",
                    "Write exactly ONE",
                    "<|im_start|>",
                    "/no_think",
                )
                if any(marker in clean for marker in _LEAK_MARKERS):
                    logger.warning("Insight: output appears to contain leaked prompt fragments, discarding")
                    return
                self._cache.save(clean)
                self._emit(self._event_name, {"text": clean})
                logger.info("Insight: generation complete, cache updated")
                with self._lock:
                    self._transcripts_since_generation = 0

        except Exception:
            logger.exception("Insight: generation failed")
        finally:
            with self._lock:
                self._generating = False
