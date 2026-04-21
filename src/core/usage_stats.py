"""Usage statistics computation for the backend analytics pipeline.

This module exposes one explicit contract: the exact fact set consumed by
InsightManager. The frontend computes its own richer dashboard analytics, so we
do not keep a second backend summary API around just to preserve dead baggage.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, TypedDict

from src.core.text_analysis import compute_text_metrics
from src.core.text_analysis import count_fillers as _count_fillers

if TYPE_CHECKING:
    from src.database.db import TranscriptDB

_SPEAKING_WPM = 150
_TYPING_WPM = 40


class InsightStats(TypedDict):
    """Explicit analytics contract for InsightManager."""

    count: int
    total_words: int
    avg_wpm: int
    time_saved_seconds: float
    refined_count: int
    verbatim_filler_count: int
    refined_filler_count: int
    verbatim_filler_density: float
    refined_filler_density: float
    verbatim_avg_fk_grade: float
    refined_avg_fk_grade: float
    avg_transcription_speed_x: float
    avg_refinement_wpm: int
    transcripts_with_transcription_time: int
    transcripts_with_refinement_time: int
    current_streak: int
    longest_streak: int
    today_count: int
    today_words: int
    days_active_this_week: int


def _estimate_speech_seconds(word_count: int) -> float:
    """Estimate speaking time from word count when no duration metadata exists."""
    if word_count <= 0:
        return 0.0
    return (word_count / _SPEAKING_WPM) * 60


def _parse_local_created_at(created_at: str | None) -> datetime | None:
    """Parse an ISO timestamp and normalize it to local time."""
    if not created_at:
        return None
    try:
        return datetime.fromisoformat(created_at.replace("Z", "+00:00")).astimezone()
    except (ValueError, AttributeError):
        return None


def _resolve_duration_metrics(
    word_count: int, duration_ms: int | None, speech_duration_ms: int | None
) -> tuple[float, float, float]:
    """Return (recorded_seconds, speech_seconds, silence_seconds) for one transcript.

    Missing duration metadata is handled per transcript instead of only as a
    global fallback. That avoids undercounting recorded time whenever the data
    set mixes older entries without ``duration_ms`` and newer entries with it.
    """
    recorded_seconds = (duration_ms or 0) / 1000
    estimated_speech_seconds = _estimate_speech_seconds(word_count)

    if recorded_seconds <= 0:
        return estimated_speech_seconds, estimated_speech_seconds, 0.0

    speech_seconds = (speech_duration_ms or 0) / 1000
    if speech_seconds > 0:
        speech_seconds = min(speech_seconds, recorded_seconds)
        return recorded_seconds, speech_seconds, max(0.0, recorded_seconds - speech_seconds)

    estimated_speech_seconds = min(estimated_speech_seconds, recorded_seconds)
    return recorded_seconds, estimated_speech_seconds, max(0.0, recorded_seconds - estimated_speech_seconds)


def compute_usage_stats(db: TranscriptDB, typing_wpm: int = _TYPING_WPM) -> InsightStats | dict[str, object]:
    """
    Compute speech usage statistics across all stored transcripts.

    Parameters
    ----------
    db : TranscriptDB
        Transcript database.
    typing_wpm : int
        Assumed manual typing speed in words-per-minute (default 40).

    Returns an empty dict if there are no transcripts or the DB is unavailable.
    """
    transcripts, _ = db.recent(limit=10000)
    transcripts = [t for t in transcripts if t.include_in_analytics]
    if not transcripts:
        return {}

    typing_wpm = max(1, int(typing_wpm))

    count = len(transcripts)
    total_words = 0
    recorded_seconds = 0.0
    total_speech_seconds = 0.0

    # Verbatim / refined accumulators
    verbatim_filler_count = 0
    refined_filler_count = 0
    refined_count = 0
    verbatim_total_words = 0
    refined_total_words = 0

    # Verbatim text metrics accumulators
    verbatim_fk_sum = 0.0
    verbatim_metrics_count = 0

    # Refined text metrics accumulators
    refined_fk_sum = 0.0
    refined_metrics_count = 0

    # Processing performance accumulators
    total_transcription_time = 0.0  # seconds
    total_refinement_time = 0.0  # seconds
    transcripts_with_transcription_time = 0
    transcripts_with_refinement_time = 0
    timed_recorded_seconds = 0.0
    timed_refined_words = 0

    for t in transcripts:
        raw = t.raw_text or ""
        norm = t.normalized_text or ""
        is_refined = bool(norm and norm != raw)
        text = norm or raw  # best-available

        words = text.split()
        word_count = len(words)
        total_words += word_count

        # Verbatim stats (always computed from raw_text)
        raw_words = raw.split()
        raw_word_count = len(raw_words)
        verbatim_total_words += raw_word_count
        verbatim_filler_count += _count_fillers(raw)

        if raw.strip():
            v_metrics = compute_text_metrics(raw)
            verbatim_fk_sum += v_metrics["fk_grade"]
            verbatim_metrics_count += 1

        # Refined stats (only for actually-refined transcripts)
        if is_refined:
            refined_count += 1
            norm_words = norm.split()
            norm_word_count = len(norm_words)
            refined_total_words += norm_word_count
            refined_filler_count += _count_fillers(norm)

            r_metrics = compute_text_metrics(norm)
            refined_fk_sum += r_metrics["fk_grade"]
            refined_metrics_count += 1
        else:
            norm_word_count = 0

        recorded_for_transcript, speech_for_transcript, silence_for_transcript = _resolve_duration_metrics(
            word_count,
            t.duration_ms,
            t.speech_duration_ms,
        )
        recorded_seconds += recorded_for_transcript
        total_speech_seconds += speech_for_transcript

        # Processing timing — only count transcript content that has matching timing data.
        if t.transcription_time_ms > 0:
            total_transcription_time += t.transcription_time_ms / 1000
            transcripts_with_transcription_time += 1
            timed_recorded_seconds += recorded_for_transcript
        if t.refinement_time_ms > 0:
            total_refinement_time += t.refinement_time_ms / 1000
            transcripts_with_refinement_time += 1
            if is_refined:
                timed_refined_words += norm_word_count

    typing_seconds = (total_words / typing_wpm) * 60
    time_saved = max(0.0, typing_seconds - recorded_seconds)

    # WPM using actual speech time (VAD) when available
    avg_wpm = round(total_words / (total_speech_seconds / 60)) if total_speech_seconds > 0 else 0

    # Verbatim averages
    v_count = verbatim_metrics_count or 1
    verbatim_filler_density = verbatim_filler_count / verbatim_total_words if verbatim_total_words else 0

    # Refined averages
    r_count = refined_metrics_count or 1
    refined_filler_density = refined_filler_count / refined_total_words if refined_total_words else 0

    # ── Streak computation (consecutive active days) ──
    transcript_dates: set[int] = set()
    for t in transcripts:
        dt = _parse_local_created_at(t.created_at)
        if dt is not None:
            transcript_dates.add(dt.toordinal())

    current_streak = 0
    longest_streak = 0
    if transcript_dates:
        today_ordinal = datetime.now().astimezone().toordinal()
        # Walk backward from today counting consecutive days
        d = today_ordinal
        while d in transcript_dates:
            current_streak += 1
            d -= 1

        # Find longest ever streak across all dates
        sorted_dates = sorted(transcript_dates)
        run = 1
        for i in range(1, len(sorted_dates)):
            if sorted_dates[i] == sorted_dates[i - 1] + 1:
                run += 1
            else:
                longest_streak = max(longest_streak, run)
                run = 1
        longest_streak = max(longest_streak, run)

    # ── Session-level stats ──
    now = datetime.now().astimezone()  # local time — matches frontend date boundaries
    today_str = now.strftime("%Y-%m-%d")
    week_start = now.toordinal() - now.weekday()  # Monday = 0
    today_count = 0
    today_words = 0
    active_days: set[int] = set()
    for t in transcripts:
        dt = _parse_local_created_at(t.created_at)
        if dt is None:
            continue
        if dt.strftime("%Y-%m-%d") == today_str:
            today_count += 1
            today_words += len((t.normalized_text or t.raw_text or "").split())
        ordinal = dt.toordinal()
        if ordinal >= week_start:
            active_days.add(ordinal)

    # ── Processing performance ──
    # Transcription speed: realtime multiplier from samples that have both
    # transcript content and matching timing metadata.
    avg_transcription_speed_x = 0.0
    if total_transcription_time > 0 and timed_recorded_seconds > 0:
        avg_transcription_speed_x = round(timed_recorded_seconds / total_transcription_time, 1)

    # Refinement throughput: only count refined words that have matching timing data.
    avg_refinement_wpm = 0
    if total_refinement_time > 0 and timed_refined_words > 0:
        avg_refinement_wpm = round(timed_refined_words / (total_refinement_time / 60))

    return {
        "count": count,
        "total_words": total_words,
        "avg_wpm": avg_wpm,
        "time_saved_seconds": time_saved,
        "verbatim_filler_count": verbatim_filler_count,
        "verbatim_filler_density": round(verbatim_filler_density, 4),
        "verbatim_avg_fk_grade": round(verbatim_fk_sum / v_count, 1),
        "refined_count": refined_count,
        "refined_filler_count": refined_filler_count,
        "refined_filler_density": round(refined_filler_density, 4),
        "refined_avg_fk_grade": round(refined_fk_sum / r_count, 1),
        "avg_transcription_speed_x": avg_transcription_speed_x,
        "avg_refinement_wpm": avg_refinement_wpm,
        "transcripts_with_transcription_time": transcripts_with_transcription_time,
        "transcripts_with_refinement_time": transcripts_with_refinement_time,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "today_count": today_count,
        "today_words": today_words,
        "days_active_this_week": len(active_days),
    }
