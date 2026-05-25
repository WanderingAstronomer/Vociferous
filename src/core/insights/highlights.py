"""Curated highlight builders for the analytics prompt.

These functions take a stats dict and return the exact factual lines the
SLM is allowed to mention. They are pure (no I/O, no SLM access, no
threading) so they can be unit-tested in isolation. The InsightManager is
responsible for orchestration — these helpers are responsible for
*content*.

Each builder returns at most 3 lines, matching the analytics prompt's
three-bullet structure.
"""

from __future__ import annotations

from typing import Any

from src.core.insights.formatting import fmt_duration, fmt_float


def build_daily_highlights(stats: dict[str, Any]) -> list[str]:
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


def build_refinement_impact_highlight(stats: dict[str, Any]) -> str | None:
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
        details.append(f"FK grade {fmt_float(refined_fk)} after refinement vs {fmt_float(raw_fk)} raw")
    return "; ".join(details) + "."


def build_long_term_highlights(stats: dict[str, Any]) -> list[str]:
    """Pick the exact long-term facts the SLM is allowed to mention."""
    total_words = int(stats.get("total_words", 0) or 0)
    total_count = int(stats.get("count", 0) or 0)
    highlights = [f"Total words captured: {total_words:,} across {total_count} transcriptions."]

    time_saved_seconds = float(stats.get("time_saved_seconds", 0) or 0)
    if time_saved_seconds > 0:
        highlights.append(f"Estimated time saved vs typing: {fmt_duration(time_saved_seconds)}.")

    refinement_impact = build_refinement_impact_highlight(stats)
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
            f"Transcription speed: {fmt_float(avg_transcription_speed)}x realtime "
            f"across {timed_transcripts} samples."
        )

    avg_refinement_wpm = int(stats.get("avg_refinement_wpm", 0) or 0)
    refinement_samples = int(stats.get("transcripts_with_refinement_time", 0) or 0)
    if len(highlights) < 3 and avg_refinement_wpm > 0 and refinement_samples > 0:
        highlights.append(f"Refinement throughput: {avg_refinement_wpm} wpm across {refinement_samples} samples.")

    return highlights[:3]


__all__ = [
    "build_daily_highlights",
    "build_long_term_highlights",
    "build_refinement_impact_highlight",
]
