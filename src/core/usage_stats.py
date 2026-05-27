"""Usage statistics computation for the backend analytics pipeline.

This module exposes explicit analytics contracts for InsightManager and the
User View. The frontend renders these facts; it must not recompute aggregate
analytics from a paginated transcript slice.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from typing import TYPE_CHECKING, Any, TypedDict

from src.core.text_analysis import FILLER_MULTI, FILLER_SINGLE, compute_text_metrics
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
    avg_retranscription_speed_x: float
    avg_refinement_tokens_per_second: float
    avg_refinement_prompt_tokens: int
    avg_refinement_completion_tokens: int
    transcripts_with_transcription_time: int
    transcripts_with_retranscription_time: int
    transcripts_with_refinement_time: int
    transcripts_with_refinement_tokens: int
    total_retranscriptions: int
    transcription_provider_counts: dict[str, int]
    transcription_model_counts: dict[str, int]
    retranscription_provider_counts: dict[str, int]
    retranscription_model_counts: dict[str, int]
    refinement_provider_counts: dict[str, int]
    refinement_model_counts: dict[str, int]
    current_streak: int
    longest_streak: int
    today_count: int
    today_words: int
    days_active_this_week: int


class FillerBreakdownEntry(TypedDict):
    label: str
    count: int


class DailyWordBucket(TypedDict):
    date: str
    words: int


class UserViewMetricsPayload(TypedDict):
    user_name: str
    typing_wpm: int
    count: int
    total_words: int
    total_recorded_seconds: float
    total_speech_seconds: float
    avg_seconds: float
    avg_wpm: int
    time_saved_seconds: float
    total_silence_seconds: float
    avg_silence_seconds: float
    vocabulary_ratio: float
    filler_count: int
    filler_breakdown: list[FillerBreakdownEntry]
    current_streak: int
    longest_streak: int
    refined_count: int
    fillers_removed: int
    verbatim_avg_fk_grade: float
    refined_avg_fk_grade: float
    verbatim_fk_for_refined: float
    fk_grade_delta: float
    total_transcription_seconds: float
    total_refinement_seconds: float
    has_timing_data: bool
    avg_transcription_speed_x: float
    avg_refinement_wpm: int
    refinement_time_saved_seconds: float
    daily_word_buckets: list[DailyWordBucket]


_PUNCT_TRIM_RE = re.compile(r'^[.,!?;:\'"()\[\]{}]+|[.,!?;:\'"()\[\]{}]+$')


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


def _count_value(values: dict[str, int], value: str | None) -> None:
    if not value:
        return
    values[value] = values.get(value, 0) + 1


def _count_phrase(text: str, phrase: str) -> int:
    escaped = re.escape(phrase).replace(r"\ ", r"\s+")
    return len(re.findall(rf"(?:^|[^a-zA-Z]){escaped}(?![a-zA-Z])", text))


def _count_fillers_by_word(text: str) -> dict[str, int]:
    if not text:
        return {}
    lower = text.lower()
    breakdown: dict[str, int] = {}

    for phrase in FILLER_MULTI:
        count = _count_phrase(lower, phrase)
        if count > 0:
            breakdown[phrase] = count

    for word in lower.split():
        cleaned = _PUNCT_TRIM_RE.sub("", word)
        if cleaned and cleaned in FILLER_SINGLE:
            breakdown[cleaned] = breakdown.get(cleaned, 0) + 1

    return breakdown


def _clean_words(text: str) -> list[str]:
    cleaned: list[str] = []
    for word in text.lower().split():
        token = _PUNCT_TRIM_RE.sub("", word)
        if token:
            cleaned.append(token)
    return cleaned


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


def _analytics_population(db: TranscriptDB | None) -> list[Any]:
    if db is None:
        return []
    analytics_transcripts = getattr(db, "analytics_transcripts", None)
    if callable(analytics_transcripts):
        return analytics_transcripts()

    transcripts: list[Any] = []
    offset = 0
    page_size = 1000
    while True:
        page, total = db.recent(limit=page_size, offset=offset)
        transcripts.extend(transcript for transcript in page if transcript.include_in_analytics)
        offset += len(page)
        if not page or offset >= total:
            break
    return transcripts


def _build_analytics_rollup(transcripts: list[Any], typing_wpm: int) -> dict[str, Any]:
    typing_wpm = max(1, int(typing_wpm))

    count = len(transcripts)
    raw_total_words = 0
    display_total_words = 0
    total_recorded_seconds = 0.0
    total_speech_seconds = 0.0
    total_silence_seconds = 0.0
    transcripts_with_duration = 0

    verbatim_filler_count = 0
    refined_filler_count = 0
    raw_fillers_in_refined = 0
    refined_count = 0
    verbatim_total_words = 0
    refined_total_words = 0

    verbatim_fk_sum = 0.0
    verbatim_metrics_count = 0
    refined_fk_sum = 0.0
    refined_metrics_count = 0
    verbatim_fk_for_refined_sum = 0.0
    verbatim_fk_for_refined_count = 0

    total_transcription_time = 0.0
    total_retranscription_time = 0.0
    total_refinement_time = 0.0
    total_refinement_token_time = 0.0
    transcripts_with_transcription_time = 0
    transcripts_with_retranscription_time = 0
    transcripts_with_refinement_time = 0
    transcripts_with_refinement_tokens = 0
    timed_recorded_seconds = 0.0
    timed_retranscribed_recorded_seconds = 0.0
    timed_refined_words = 0
    total_retranscriptions = 0
    total_refinement_prompt_tokens = 0
    total_refinement_completion_tokens = 0
    total_refinement_tokens = 0

    transcription_provider_counts: dict[str, int] = {}
    transcription_model_counts: dict[str, int] = {}
    retranscription_provider_counts: dict[str, int] = {}
    retranscription_model_counts: dict[str, int] = {}
    refinement_provider_counts: dict[str, int] = {}
    refinement_model_counts: dict[str, int] = {}

    filler_breakdown: Counter[str] = Counter()
    vocabulary_tokens = 0
    vocabulary_unique: set[str] = set()
    transcript_dates: set[int] = set()
    daily_word_counts: Counter[str] = Counter()

    now = datetime.now().astimezone()
    today_str = now.strftime("%Y-%m-%d")
    week_start = now.toordinal() - now.weekday()
    today_count = 0
    today_words = 0
    active_days: set[int] = set()

    for transcript in transcripts:
        raw = transcript.raw_text or ""
        norm = transcript.normalized_text or ""
        display = norm or raw
        is_refined = bool(norm and norm != raw)

        _count_value(transcription_provider_counts, transcript.transcription_provider)
        _count_value(transcription_model_counts, transcript.transcription_model_id)
        _count_value(retranscription_provider_counts, transcript.last_retranscription_provider)
        _count_value(retranscription_model_counts, transcript.last_retranscription_model_id)
        _count_value(refinement_provider_counts, transcript.refinement_provider)
        _count_value(refinement_model_counts, transcript.refinement_model_id)
        total_retranscriptions += transcript.retranscription_count

        raw_word_count = len(raw.split())
        display_word_count = len(display.split())
        raw_total_words += raw_word_count
        display_total_words += display_word_count
        verbatim_total_words += raw_word_count

        recorded_for_transcript, speech_for_transcript, silence_for_transcript = _resolve_duration_metrics(
            raw_word_count,
            transcript.duration_ms,
            transcript.speech_duration_ms,
        )
        total_recorded_seconds += recorded_for_transcript
        total_speech_seconds += speech_for_transcript
        total_silence_seconds += silence_for_transcript
        if (transcript.duration_ms or 0) > 0:
            transcripts_with_duration += 1

        verbatim_filler_count += _count_fillers(raw)
        filler_breakdown.update(_count_fillers_by_word(raw))

        cleaned_words = _clean_words(raw)
        vocabulary_tokens += len(cleaned_words)
        vocabulary_unique.update(cleaned_words)

        if raw.strip():
            raw_metrics = compute_text_metrics(raw)
            verbatim_fk_sum += raw_metrics["fk_grade"]
            verbatim_metrics_count += 1

        if is_refined:
            refined_count += 1
            norm_word_count = len(norm.split())
            refined_total_words += norm_word_count
            raw_fillers_in_refined += _count_fillers(raw)
            refined_filler_count += _count_fillers(norm)

            refined_metrics = compute_text_metrics(norm)
            refined_fk_sum += refined_metrics["fk_grade"]
            refined_metrics_count += 1

            raw_refined_metrics = compute_text_metrics(raw)
            verbatim_fk_for_refined_sum += raw_refined_metrics["fk_grade"]
            verbatim_fk_for_refined_count += 1
        else:
            norm_word_count = 0

        if transcript.transcription_time_ms > 0:
            total_transcription_time += transcript.transcription_time_ms / 1000
            transcripts_with_transcription_time += 1
            timed_recorded_seconds += recorded_for_transcript

        if transcript.last_retranscription_time_ms > 0:
            total_retranscription_time += transcript.last_retranscription_time_ms / 1000
            transcripts_with_retranscription_time += 1
            timed_retranscribed_recorded_seconds += recorded_for_transcript

        if transcript.refinement_time_ms > 0:
            total_refinement_time += transcript.refinement_time_ms / 1000
            transcripts_with_refinement_time += 1
            if is_refined:
                timed_refined_words += norm_word_count

        if transcript.refinement_time_ms > 0 and transcript.refinement_total_tokens > 0:
            total_refinement_token_time += transcript.refinement_time_ms / 1000
            transcripts_with_refinement_tokens += 1
            total_refinement_prompt_tokens += transcript.refinement_prompt_tokens
            total_refinement_completion_tokens += transcript.refinement_completion_tokens
            total_refinement_tokens += transcript.refinement_total_tokens

        dt = _parse_local_created_at(transcript.created_at)
        if dt is None:
            continue

        ordinal = dt.toordinal()
        transcript_dates.add(ordinal)
        if ordinal >= week_start:
            active_days.add(ordinal)

        day_key = dt.strftime("%Y-%m-%d")
        daily_word_counts[day_key] += raw_word_count

        if day_key == today_str:
            today_count += 1
            today_words += display_word_count

    current_streak = 0
    longest_streak = 0
    if transcript_dates:
        today_ordinal = datetime.now().astimezone().toordinal()
        day_cursor = today_ordinal
        while day_cursor in transcript_dates:
            current_streak += 1
            day_cursor -= 1

        sorted_dates = sorted(transcript_dates)
        run = 1
        for i in range(1, len(sorted_dates)):
            if sorted_dates[i] == sorted_dates[i - 1] + 1:
                run += 1
            else:
                longest_streak = max(longest_streak, run)
                run = 1
        longest_streak = max(longest_streak, run)

    display_typing_seconds = (display_total_words / typing_wpm) * 60 if display_total_words > 0 else 0.0
    raw_typing_seconds = (raw_total_words / typing_wpm) * 60 if raw_total_words > 0 else 0.0
    avg_display_wpm = round(display_total_words / (total_speech_seconds / 60)) if total_speech_seconds > 0 else 0
    avg_raw_wpm = round(raw_total_words / (total_speech_seconds / 60)) if total_speech_seconds > 0 else 0
    avg_transcription_speed_x = (
        round(timed_recorded_seconds / total_transcription_time, 1)
        if total_transcription_time > 0 and timed_recorded_seconds > 0
        else 0.0
    )
    avg_retranscription_speed_x = (
        round(timed_retranscribed_recorded_seconds / total_retranscription_time, 1)
        if total_retranscription_time > 0 and timed_retranscribed_recorded_seconds > 0
        else 0.0
    )
    avg_refinement_wpm = (
        round(timed_refined_words / (total_refinement_time / 60))
        if total_refinement_time > 0 and timed_refined_words > 0
        else 0
    )
    avg_refinement_tokens_per_second = (
        round(total_refinement_tokens / total_refinement_token_time, 1)
        if total_refinement_token_time > 0 and total_refinement_tokens > 0
        else 0.0
    )
    avg_refinement_prompt_tokens = (
        round(total_refinement_prompt_tokens / transcripts_with_refinement_tokens)
        if transcripts_with_refinement_tokens > 0
        else 0
    )
    avg_refinement_completion_tokens = (
        round(total_refinement_completion_tokens / transcripts_with_refinement_tokens)
        if transcripts_with_refinement_tokens > 0
        else 0
    )

    verbatim_filler_density = verbatim_filler_count / verbatim_total_words if verbatim_total_words else 0.0
    refined_filler_density = refined_filler_count / refined_total_words if refined_total_words else 0.0
    verbatim_avg_fk_grade = round(verbatim_fk_sum / (verbatim_metrics_count or 1), 1)
    refined_avg_fk_grade = round(refined_fk_sum / (refined_metrics_count or 1), 1)
    verbatim_fk_for_refined = round(verbatim_fk_for_refined_sum / (verbatim_fk_for_refined_count or 1), 1)
    fk_grade_delta = round(refined_avg_fk_grade - verbatim_fk_for_refined, 1) if refined_count > 0 else 0.0

    return {
        "count": count,
        "raw_total_words": raw_total_words,
        "display_total_words": display_total_words,
        "total_recorded_seconds": total_recorded_seconds,
        "total_speech_seconds": total_speech_seconds,
        "total_silence_seconds": total_silence_seconds,
        "avg_seconds": (total_recorded_seconds / count) if count > 0 else 0.0,
        "avg_raw_wpm": avg_raw_wpm,
        "avg_display_wpm": avg_display_wpm,
        "display_time_saved_seconds": max(0.0, display_typing_seconds - total_recorded_seconds),
        "raw_time_saved_seconds": max(0.0, raw_typing_seconds - total_recorded_seconds),
        "avg_silence_seconds": (total_silence_seconds / transcripts_with_duration)
        if transcripts_with_duration > 0
        else 0.0,
        "vocabulary_ratio": (len(vocabulary_unique) / vocabulary_tokens) if vocabulary_tokens > 0 else 0.0,
        "verbatim_filler_count": verbatim_filler_count,
        "verbatim_filler_density": round(verbatim_filler_density, 4),
        "refined_filler_count": refined_filler_count,
        "refined_filler_density": round(refined_filler_density, 4),
        "refined_count": refined_count,
        "raw_fillers_in_refined": raw_fillers_in_refined,
        "fillers_removed": raw_fillers_in_refined - refined_filler_count,
        "verbatim_avg_fk_grade": verbatim_avg_fk_grade,
        "refined_avg_fk_grade": refined_avg_fk_grade,
        "verbatim_fk_for_refined": verbatim_fk_for_refined,
        "fk_grade_delta": fk_grade_delta,
        "total_transcription_seconds": total_transcription_time,
        "total_refinement_seconds": total_refinement_time,
        "has_timing_data": total_transcription_time > 0 or total_refinement_time > 0,
        "avg_transcription_speed_x": avg_transcription_speed_x,
        "avg_retranscription_speed_x": avg_retranscription_speed_x,
        "avg_refinement_wpm": avg_refinement_wpm,
        "avg_refinement_tokens_per_second": avg_refinement_tokens_per_second,
        "avg_refinement_prompt_tokens": avg_refinement_prompt_tokens,
        "avg_refinement_completion_tokens": avg_refinement_completion_tokens,
        "refinement_time_saved_seconds": max(
            0.0,
            ((timed_refined_words / max(1, typing_wpm / 2)) * 60 if timed_refined_words > 0 else 0.0)
            - total_refinement_time,
        ),
        "transcripts_with_transcription_time": transcripts_with_transcription_time,
        "transcripts_with_retranscription_time": transcripts_with_retranscription_time,
        "transcripts_with_refinement_time": transcripts_with_refinement_time,
        "transcripts_with_refinement_tokens": transcripts_with_refinement_tokens,
        "total_retranscriptions": total_retranscriptions,
        "transcription_provider_counts": transcription_provider_counts,
        "transcription_model_counts": transcription_model_counts,
        "retranscription_provider_counts": retranscription_provider_counts,
        "retranscription_model_counts": retranscription_model_counts,
        "refinement_provider_counts": refinement_provider_counts,
        "refinement_model_counts": refinement_model_counts,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "today_count": today_count,
        "today_words": today_words,
        "days_active_this_week": len(active_days),
        "filler_breakdown": [{"label": label, "count": count} for label, count in filler_breakdown.most_common(5)],
        "daily_word_buckets": [{"date": date, "words": words} for date, words in sorted(daily_word_counts.items())],
    }


def _empty_user_view_metrics_payload(typing_wpm: int, user_name: str) -> UserViewMetricsPayload:
    safe_typing_wpm = max(1, int(typing_wpm))
    return {
        "user_name": user_name,
        "typing_wpm": safe_typing_wpm,
        "count": 0,
        "total_words": 0,
        "total_recorded_seconds": 0.0,
        "total_speech_seconds": 0.0,
        "avg_seconds": 0.0,
        "avg_wpm": 0,
        "time_saved_seconds": 0.0,
        "total_silence_seconds": 0.0,
        "avg_silence_seconds": 0.0,
        "vocabulary_ratio": 0.0,
        "filler_count": 0,
        "filler_breakdown": [],
        "current_streak": 0,
        "longest_streak": 0,
        "refined_count": 0,
        "fillers_removed": 0,
        "verbatim_avg_fk_grade": 0.0,
        "refined_avg_fk_grade": 0.0,
        "verbatim_fk_for_refined": 0.0,
        "fk_grade_delta": 0.0,
        "total_transcription_seconds": 0.0,
        "total_refinement_seconds": 0.0,
        "has_timing_data": False,
        "avg_transcription_speed_x": 0.0,
        "avg_refinement_wpm": 0,
        "refinement_time_saved_seconds": 0.0,
        "daily_word_buckets": [],
    }


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
    transcripts = _analytics_population(db)
    if not transcripts:
        return {}
    rollup = _build_analytics_rollup(transcripts, typing_wpm)

    return {
        "count": rollup["count"],
        "total_words": rollup["display_total_words"],
        "avg_wpm": rollup["avg_display_wpm"],
        "time_saved_seconds": rollup["display_time_saved_seconds"],
        "verbatim_filler_count": rollup["verbatim_filler_count"],
        "verbatim_filler_density": rollup["verbatim_filler_density"],
        "verbatim_avg_fk_grade": rollup["verbatim_avg_fk_grade"],
        "refined_count": rollup["refined_count"],
        "refined_filler_count": rollup["refined_filler_count"],
        "refined_filler_density": rollup["refined_filler_density"],
        "refined_avg_fk_grade": rollup["refined_avg_fk_grade"],
        "avg_transcription_speed_x": rollup["avg_transcription_speed_x"],
        "avg_refinement_wpm": rollup["avg_refinement_wpm"],
        "avg_retranscription_speed_x": rollup["avg_retranscription_speed_x"],
        "avg_refinement_tokens_per_second": rollup["avg_refinement_tokens_per_second"],
        "avg_refinement_prompt_tokens": rollup["avg_refinement_prompt_tokens"],
        "avg_refinement_completion_tokens": rollup["avg_refinement_completion_tokens"],
        "transcripts_with_transcription_time": rollup["transcripts_with_transcription_time"],
        "transcripts_with_retranscription_time": rollup["transcripts_with_retranscription_time"],
        "transcripts_with_refinement_time": rollup["transcripts_with_refinement_time"],
        "transcripts_with_refinement_tokens": rollup["transcripts_with_refinement_tokens"],
        "total_retranscriptions": rollup["total_retranscriptions"],
        "transcription_provider_counts": rollup["transcription_provider_counts"],
        "transcription_model_counts": rollup["transcription_model_counts"],
        "retranscription_provider_counts": rollup["retranscription_provider_counts"],
        "retranscription_model_counts": rollup["retranscription_model_counts"],
        "refinement_provider_counts": rollup["refinement_provider_counts"],
        "refinement_model_counts": rollup["refinement_model_counts"],
        "current_streak": rollup["current_streak"],
        "longest_streak": rollup["longest_streak"],
        "today_count": rollup["today_count"],
        "today_words": rollup["today_words"],
        "days_active_this_week": rollup["days_active_this_week"],
    }


def compute_user_view_metrics(
    db: TranscriptDB | None,
    typing_wpm: int = _TYPING_WPM,
    user_name: str = "",
) -> UserViewMetricsPayload:
    transcripts = _analytics_population(db)
    if not transcripts:
        return _empty_user_view_metrics_payload(typing_wpm, user_name)

    rollup = _build_analytics_rollup(transcripts, typing_wpm)
    return {
        "user_name": user_name,
        "typing_wpm": max(1, int(typing_wpm)),
        "count": rollup["count"],
        "total_words": rollup["raw_total_words"],
        "total_recorded_seconds": round(rollup["total_recorded_seconds"], 1),
        "total_speech_seconds": round(rollup["total_speech_seconds"], 1),
        "avg_seconds": round(rollup["avg_seconds"], 1),
        "avg_wpm": rollup["avg_raw_wpm"],
        "time_saved_seconds": round(rollup["raw_time_saved_seconds"], 1),
        "total_silence_seconds": round(rollup["total_silence_seconds"], 1),
        "avg_silence_seconds": round(rollup["avg_silence_seconds"], 1),
        "vocabulary_ratio": round(rollup["vocabulary_ratio"], 4),
        "filler_count": rollup["verbatim_filler_count"],
        "filler_breakdown": rollup["filler_breakdown"],
        "current_streak": rollup["current_streak"],
        "longest_streak": rollup["longest_streak"],
        "refined_count": rollup["refined_count"],
        "fillers_removed": rollup["fillers_removed"],
        "verbatim_avg_fk_grade": rollup["verbatim_avg_fk_grade"],
        "refined_avg_fk_grade": rollup["refined_avg_fk_grade"],
        "verbatim_fk_for_refined": rollup["verbatim_fk_for_refined"],
        "fk_grade_delta": rollup["fk_grade_delta"],
        "total_transcription_seconds": round(rollup["total_transcription_seconds"], 1),
        "total_refinement_seconds": round(rollup["total_refinement_seconds"], 1),
        "has_timing_data": rollup["has_timing_data"],
        "avg_transcription_speed_x": rollup["avg_transcription_speed_x"],
        "avg_refinement_wpm": rollup["avg_refinement_wpm"],
        "refinement_time_saved_seconds": round(rollup["refinement_time_saved_seconds"], 1),
        "daily_word_buckets": rollup["daily_word_buckets"],
    }
