"""
Usage statistics computation for InsightManager and MOTD generation.

Extracted from ApplicationCoordinator._init_insight_manager() so it is
independently testable and not buried in an init closure.

Statistics are split into three views:
- **Overall**: Aggregate metrics across all transcripts (best-available text).
- **Verbatim**: Metrics computed from raw_text only.
- **Refined**: Metrics computed from normalized_text on transcripts that were
  actually refined (normalized_text != raw_text).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.core.text_analysis import compute_text_metrics

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


def _count_fillers(text: str) -> int:
    """Count filler words/phrases in a text string."""
    if not text:
        return 0
    lower = text.lower()
    count = 0

    # Multi-word fillers
    for phrase in _FILLER_MULTI:
        idx = 0
        while (idx := lower.find(phrase, idx)) != -1:
            count += 1
            idx += len(phrase)

    # Single-word fillers
    for w in lower.split():
        cleaned = w.strip(".,!?;:'\"()[]{}").lower()
        if cleaned and cleaned in _FILLER_SINGLE:
            count += 1

    return count


def _count_fillers_by_word(text: str) -> dict[str, int]:
    """Return per-filler breakdown: {filler_word_or_phrase: count}.

    Only includes fillers that actually appear at least once.
    """
    if not text:
        return {}
    lower = text.lower()
    breakdown: dict[str, int] = {}

    for phrase in _FILLER_MULTI:
        idx = 0
        while (idx := lower.find(phrase, idx)) != -1:
            breakdown[phrase] = breakdown.get(phrase, 0) + 1
            idx += len(phrase)

    for w in lower.split():
        cleaned = w.strip(".,!?;:'\"()[]{}").lower()
        if cleaned and cleaned in _FILLER_SINGLE:
            breakdown[cleaned] = breakdown.get(cleaned, 0) + 1

    return breakdown


def _collect_cleaned_words(text: str) -> list[str]:
    """Extract cleaned lowercase words from text for vocabulary analysis."""
    words: list[str] = []
    for w in text.lower().split():
        cleaned = w.strip(".,!?;:'\"()[]{}").lower()
        if cleaned:
            words.append(cleaned)
    return words


def compute_usage_stats(db: TranscriptDB, typing_wpm: int = _TYPING_WPM) -> dict:
    """
    Compute speech usage statistics across all stored transcripts.

    Parameters
    ----------
    db : TranscriptDB
        Transcript database.
    typing_wpm : int
        Assumed manual typing speed in words-per-minute (default 40).

    Returns an empty dict if there are no transcripts or the DB is unavailable.
    Used as the stats_provider for both InsightManager and MOTDManager.
    """
    transcripts, _ = db.recent(limit=10000)
    transcripts = [t for t in transcripts if t.include_in_analytics]
    if not transcripts:
        return {}

    count = len(transcripts)
    total_words = 0
    all_words: list[str] = []
    recorded_seconds = 0.0
    total_speech_seconds = 0.0
    total_silence = 0.0
    filler_count = 0

    # Verbatim / refined accumulators
    verbatim_filler_count = 0
    refined_filler_count = 0
    refined_count = 0
    verbatim_total_words = 0
    refined_total_words = 0
    verbatim_all_words: list[str] = []
    refined_all_words: list[str] = []

    # Filler breakdown (per-word counts)
    filler_breakdown: dict[str, int] = {}

    # Verbatim text metrics accumulators
    verbatim_fk_sum = 0.0
    verbatim_avg_sentence_len_sum = 0.0
    verbatim_metrics_count = 0

    # Refined text metrics accumulators
    refined_fk_sum = 0.0
    refined_avg_sentence_len_sum = 0.0

    # Processing performance accumulators
    total_transcription_time = 0.0  # seconds
    total_refinement_time = 0.0  # seconds
    transcripts_with_transcription_time = 0
    transcripts_with_refinement_time = 0

    for t in transcripts:
        raw = t.raw_text or ""
        norm = t.normalized_text or ""
        is_refined = bool(norm and norm != raw)
        text = norm or raw  # best-available

        words = text.split()
        total_words += len(words)

        # Overall filler count (best-available text)
        filler_count += _count_fillers(text)
        all_words.extend(_collect_cleaned_words(text))

        # Filler breakdown (aggregate per-word counts across all transcripts)
        for word, wcount in _count_fillers_by_word(text).items():
            filler_breakdown[word] = filler_breakdown.get(word, 0) + wcount

        # Verbatim stats (always computed from raw_text)
        raw_words = raw.split()
        verbatim_total_words += len(raw_words)
        verbatim_filler_count += _count_fillers(raw)
        verbatim_all_words.extend(_collect_cleaned_words(raw))

        if raw.strip():
            v_metrics = compute_text_metrics(raw)
            verbatim_fk_sum += v_metrics["fk_grade"]
            verbatim_avg_sentence_len_sum += v_metrics["avg_sentence_length"]
            verbatim_metrics_count += 1

        # Refined stats (only for actually-refined transcripts)
        if is_refined:
            refined_count += 1
            norm_words = norm.split()
            refined_total_words += len(norm_words)
            refined_filler_count += _count_fillers(norm)
            refined_all_words.extend(_collect_cleaned_words(norm))

            r_metrics = compute_text_metrics(norm)
            refined_fk_sum += r_metrics["fk_grade"]
            refined_avg_sentence_len_sum += r_metrics["avg_sentence_length"]

        # Duration / silence — use VAD speech_duration_ms when available
        dur = (t.duration_ms or 0) / 1000
        if dur > 0:
            recorded_seconds += dur
            speech = (t.speech_duration_ms or 0) / 1000
            if speech > 0:
                total_speech_seconds += speech
                total_silence += max(0.0, dur - speech)
            else:
                # No VAD data — fall back to word-count estimate
                expected = (len(words) / _SPEAKING_WPM) * 60
                total_speech_seconds += min(expected, dur)
                total_silence += max(0.0, dur - expected)

        # Processing timing — only count transcripts that have data (post-v10 migration)
        if t.transcription_time_ms > 0:
            total_transcription_time += t.transcription_time_ms / 1000
            transcripts_with_transcription_time += 1
        if t.refinement_time_ms > 0:
            total_refinement_time += t.refinement_time_ms / 1000
            transcripts_with_refinement_time += 1

    # Fallback estimate when no duration metadata is present
    if recorded_seconds == 0 and total_words > 0:
        recorded_seconds = (total_words / _SPEAKING_WPM) * 60
        total_speech_seconds = recorded_seconds  # no silence estimate possible

    typing_seconds = (total_words / typing_wpm) * 60
    time_saved = max(0.0, typing_seconds - recorded_seconds)
    avg_seconds = recorded_seconds / count if count > 0 else 0
    vocab_ratio = len(set(all_words)) / len(all_words) if all_words else 0

    # WPM using actual speech time (VAD) when available
    avg_wpm = round(total_words / (total_speech_seconds / 60)) if total_speech_seconds > 0 else 0

    # Verbatim averages
    v_count = verbatim_metrics_count or 1
    verbatim_vocab_ratio = len(set(verbatim_all_words)) / len(verbatim_all_words) if verbatim_all_words else 0
    verbatim_filler_density = verbatim_filler_count / verbatim_total_words if verbatim_total_words else 0

    # Refined averages
    r_count = refined_count or 1
    refined_vocab_ratio = len(set(refined_all_words)) / len(refined_all_words) if refined_all_words else 0
    refined_filler_density = refined_filler_count / refined_total_words if refined_total_words else 0

    # ── Streak computation (consecutive active days) ──
    transcript_dates: set[int] = set()
    for t in transcripts:
        try:
            dt = datetime.fromisoformat(t.created_at.replace("Z", "+00:00"))
            transcript_dates.add(dt.toordinal())
        except (ValueError, AttributeError):
            continue

    current_streak = 0
    longest_streak = 0
    if transcript_dates:
        today_ordinal = datetime.now(timezone.utc).toordinal()
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
    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    week_start = now.toordinal() - now.weekday()  # Monday = 0
    today_count = 0
    today_words = 0
    active_days: set[int] = set()
    for t in transcripts:
        try:
            dt = datetime.fromisoformat(t.created_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if dt.strftime("%Y-%m-%d") == today_str:
            today_count += 1
            today_words += len((t.normalized_text or t.raw_text or "").split())
        ordinal = dt.toordinal()
        if ordinal >= week_start:
            active_days.add(ordinal)

    # Top fillers — sorted by count descending, capped at 5
    top_fillers = dict(sorted(filler_breakdown.items(), key=lambda x: x[1], reverse=True)[:5])

    # ── Processing performance ──
    # Transcription speed: realtime multiplier (recording_duration / transcription_time)
    avg_transcription_speed_x = 0.0
    if total_transcription_time > 0 and recorded_seconds > 0:
        avg_transcription_speed_x = round(recorded_seconds / total_transcription_time, 1)

    # Refinement throughput: words processed per minute by SLM
    avg_refinement_wpm = 0
    if total_refinement_time > 0 and refined_total_words > 0:
        avg_refinement_wpm = round(refined_total_words / (total_refinement_time / 60))

    # Refinement time saved: estimated manual editing time minus actual SLM time
    # Manual editing speed ≈ typing_wpm / 2 (reading + restructuring is slower than straight typing)
    manual_editing_wpm = max(1, typing_wpm / 2)
    refinement_time_saved = 0.0
    if refined_total_words > 0:
        manual_edit_seconds = (refined_total_words / manual_editing_wpm) * 60
        refinement_time_saved = max(0.0, manual_edit_seconds - total_refinement_time)

    return {
        # ── Overall (backward-compatible) ──
        "count": count,
        "total_words": total_words,
        "recorded_seconds": recorded_seconds,
        "total_speech_seconds": total_speech_seconds,
        "avg_wpm": avg_wpm,
        "time_saved_seconds": time_saved,
        "avg_seconds": avg_seconds,
        "vocab_ratio": vocab_ratio,
        "total_silence_seconds": total_silence,
        "filler_count": filler_count,
        "filler_breakdown": top_fillers,
        # ── Verbatim pipeline ──
        "verbatim_total_words": verbatim_total_words,
        "verbatim_filler_count": verbatim_filler_count,
        "verbatim_filler_density": round(verbatim_filler_density, 4),
        "verbatim_vocab_ratio": round(verbatim_vocab_ratio, 3),
        "verbatim_avg_fk_grade": round(verbatim_fk_sum / v_count, 1),
        "verbatim_avg_sentence_length": round(verbatim_avg_sentence_len_sum / v_count, 1),
        # ── Refinement pipeline ──
        "refined_count": refined_count,
        "refined_total_words": refined_total_words,
        "refined_filler_count": refined_filler_count,
        "refined_filler_density": round(refined_filler_density, 4),
        "refined_vocab_ratio": round(refined_vocab_ratio, 3),
        "refined_avg_fk_grade": round(refined_fk_sum / r_count, 1),
        "refined_avg_sentence_length": round(refined_avg_sentence_len_sum / r_count, 1),
        # ── Processing performance ──
        "total_transcription_time_seconds": round(total_transcription_time, 1),
        "total_refinement_time_seconds": round(total_refinement_time, 1),
        "avg_transcription_speed_x": avg_transcription_speed_x,
        "avg_refinement_wpm": avg_refinement_wpm,
        "refinement_time_saved_seconds": round(refinement_time_saved, 1),
        "transcripts_with_transcription_time": transcripts_with_transcription_time,
        "transcripts_with_refinement_time": transcripts_with_refinement_time,
        # ── Streaks ──
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        # ── Session-level ──
        "today_count": today_count,
        "today_words": today_words,
        "days_active_this_week": len(active_days),
    }
