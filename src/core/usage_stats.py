"""
Usage statistics computation for InsightManager and MOTD generation.

Extracted from ApplicationCoordinator._init_insight_manager() so it is
independently testable and not buried in an init closure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.database.db import TranscriptDB

_SPEAKING_WPM = 150
_TYPING_WPM = 40

_FILLER_SINGLE: frozenset[str] = frozenset(
    {
        "um",
        "uh",
        "uhm",
        "umm",
        "er",
        "err",
        "like",
        "basically",
        "literally",
        "actually",
        "so",
        "well",
        "right",
        "okay",
    }
)
_FILLER_MULTI: tuple[str, ...] = ("you know", "i mean", "kind of", "sort of")


def compute_usage_stats(db: TranscriptDB) -> dict:
    """
    Compute speech usage statistics across all stored transcripts.

    Returns an empty dict if there are no transcripts or the DB is unavailable.
    Used as the stats_provider for both InsightManager and MOTDManager.
    """
    transcripts = db.recent(limit=10000)
    if not transcripts:
        return {}

    count = len(transcripts)
    total_words = 0
    all_words: list[str] = []
    recorded_seconds = 0.0
    total_silence = 0.0
    filler_count = 0

    for t in transcripts:
        text = t.normalized_text or t.raw_text or ""
        words = text.split()
        total_words += len(words)

        lower = text.lower()

        # Multi-word fillers
        for phrase in _FILLER_MULTI:
            idx = 0
            while (idx := lower.find(phrase, idx)) != -1:
                filler_count += 1
                idx += len(phrase)

        # Single-word fillers + vocab collection (one pass)
        for w in lower.split():
            cleaned = w.strip(".,!?;:'\"()[]{}").lower()
            if cleaned:
                all_words.append(cleaned)
                if cleaned in _FILLER_SINGLE:
                    filler_count += 1

        dur = (t.duration_ms or 0) / 1000
        if dur > 0:
            recorded_seconds += dur
            expected = (len(words) / _SPEAKING_WPM) * 60
            total_silence += max(0.0, dur - expected)

    # Fallback estimate when no duration metadata is present
    if recorded_seconds == 0 and total_words > 0:
        recorded_seconds = (total_words / _SPEAKING_WPM) * 60

    typing_seconds = (total_words / _TYPING_WPM) * 60
    time_saved = max(0.0, typing_seconds - recorded_seconds)
    avg_seconds = recorded_seconds / count if count > 0 else 0
    vocab_ratio = len(set(all_words)) / len(all_words) if all_words else 0

    return {
        "count": count,
        "total_words": total_words,
        "recorded_seconds": recorded_seconds,
        "time_saved_seconds": time_saved,
        "avg_seconds": avg_seconds,
        "vocab_ratio": vocab_ratio,
        "total_silence_seconds": total_silence,
        "filler_count": filler_count,
    }
