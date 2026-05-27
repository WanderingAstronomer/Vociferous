"""Unit tests for the backend analytics contract in usage_stats.compute_usage_stats()."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.core.usage_stats import compute_usage_stats, compute_user_view_metrics
from src.database.db import TranscriptDB


@pytest.fixture()
def db(tmp_path: Path) -> Generator[TranscriptDB, None, None]:
    database = TranscriptDB(db_path=tmp_path / "stats_test.db")
    yield database
    database.close()


def _insert_transcript(
    db: TranscriptDB,
    *,
    created_at: str,
    raw_text: str,
    normalized_text: str | None = None,
    duration_ms: int = 0,
    speech_duration_ms: int = 0,
    transcription_time_ms: int = 0,
    refinement_time_ms: int = 0,
    include_in_analytics: int = 1,
) -> None:
    normalized = normalized_text if normalized_text is not None else raw_text
    with db._conn as con:
        con.execute(
            "INSERT INTO transcripts (timestamp, raw_text, normalized_text, display_name, "
            "duration_ms, speech_duration_ms, transcription_time_ms, refinement_time_ms, "
            "include_in_analytics, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                created_at,
                raw_text,
                normalized,
                "",
                duration_ms,
                speech_duration_ms,
                transcription_time_ms,
                refinement_time_ms,
                include_in_analytics,
                created_at,
            ),
        )


class TestUsageStatsContract:
    def test_empty_db_returns_empty_dict(self, db):
        assert compute_usage_stats(db) == {}

    def test_returns_only_live_consumer_keys(self, db):
        db.add_transcript(raw_text="hello world test", duration_ms=5000)

        stats = compute_usage_stats(db)

        assert set(stats.keys()) == {
            "count",
            "total_words",
            "avg_wpm",
            "time_saved_seconds",
            "refined_count",
            "verbatim_filler_count",
            "refined_filler_count",
            "verbatim_filler_density",
            "refined_filler_density",
            "verbatim_avg_fk_grade",
            "refined_avg_fk_grade",
            "avg_transcription_speed_x",
            "avg_refinement_wpm",
            "avg_retranscription_speed_x",
            "avg_refinement_tokens_per_second",
            "avg_refinement_prompt_tokens",
            "avg_refinement_completion_tokens",
            "transcripts_with_transcription_time",
            "transcripts_with_retranscription_time",
            "transcripts_with_refinement_time",
            "transcripts_with_refinement_tokens",
            "total_retranscriptions",
            "transcription_provider_counts",
            "transcription_model_counts",
            "retranscription_provider_counts",
            "retranscription_model_counts",
            "refinement_provider_counts",
            "refinement_model_counts",
            "current_streak",
            "longest_streak",
            "today_count",
            "today_words",
            "days_active_this_week",
        }

    def test_excluded_transcripts_are_ignored(self, db):
        db.add_transcript(raw_text="alpha beta", duration_ms=2000)
        _insert_transcript(
            db,
            created_at=datetime.now(timezone.utc).isoformat(),
            raw_text="should not count at all",
            duration_ms=4000,
            include_in_analytics=0,
        )

        stats = compute_usage_stats(db)

        assert stats["count"] == 1
        assert stats["total_words"] == 2

    def test_hidden_compound_children_do_not_double_count_analytics(self, db):
        root = db.add_transcript(raw_text="alpha beta", duration_ms=4000)
        source = db.add_transcript(raw_text="gamma delta epsilon", duration_ms=6000)

        db.append_to_transcript(root.id, source.id)

        stats = compute_usage_stats(db)

        assert stats["count"] == 1
        assert stats["total_words"] == 5

    def test_analytics_population_is_not_recent_page_limited(self, db):
        created_at = datetime.now(timezone.utc).isoformat()
        with db._conn as con:
            con.executemany(
                "INSERT INTO transcripts (timestamp, raw_text, normalized_text, display_name, created_at) "
                "VALUES (?,?,?,?,?)",
                [(created_at, "word", "word", "", created_at) for _ in range(10_001)],
            )

        stats = compute_usage_stats(db)

        assert stats["count"] == 10_001
        assert stats["total_words"] == 10_001


class TestCoreMetrics:
    def test_time_saved_estimates_missing_duration_per_transcript(self, db):
        words = " ".join(["word"] * 150)
        db.add_transcript(raw_text=words, duration_ms=60_000)
        db.add_transcript(raw_text=words, duration_ms=0)

        stats = compute_usage_stats(db)

        assert stats["time_saved_seconds"] == pytest.approx(330.0, rel=0.01)

    def test_avg_wpm_uses_vad_speech_seconds(self, db):
        words = " ".join(["word"] * 60)
        db.add_transcript(raw_text=words, duration_ms=30_000, speech_duration_ms=20_000)

        stats = compute_usage_stats(db)

        assert stats["avg_wpm"] == 180

    def test_refined_metrics_use_refined_population_only(self, db):
        transcript = db.add_transcript(raw_text="um like I basically went um there", duration_ms=5000)
        db.update_normalized_text(transcript.id, "I went there.")

        stats = compute_usage_stats(db)

        assert stats["refined_count"] == 1
        assert stats["verbatim_filler_count"] == 4
        assert stats["verbatim_filler_density"] == pytest.approx(4 / 7, rel=0.001)
        assert stats["refined_filler_count"] == 0
        assert stats["refined_filler_density"] == 0.0

    def test_fk_grades_are_computed_from_raw_and_refined_text(self, db):
        transcript = db.add_transcript(
            raw_text=(
                "The committee convened to discuss the preliminary findings. "
                "Several members expressed reservations about the methodology."
            ),
            duration_ms=10_000,
        )
        db.update_normalized_text(
            transcript.id,
            "The committee met to discuss the findings. Several members questioned the method.",
        )

        stats = compute_usage_stats(db)

        assert stats["verbatim_avg_fk_grade"] > 0
        assert stats["refined_avg_fk_grade"] > 0


class TestTimingMetrics:
    def test_transcription_speed_uses_only_timed_samples(self, db):
        db.add_transcript(
            raw_text=" ".join(["word"] * 30),
            duration_ms=30_000,
            transcription_time_ms=10_000,
        )
        db.add_transcript(
            raw_text=" ".join(["word"] * 60),
            duration_ms=60_000,
            transcription_time_ms=0,
        )

        stats = compute_usage_stats(db)

        assert stats["transcripts_with_transcription_time"] == 1
        assert stats["avg_transcription_speed_x"] == 3.0

    def test_refinement_throughput_uses_only_timed_refined_words(self, db):
        timed = db.add_transcript(raw_text="rough text", duration_ms=3000)
        db.update_normalized_text(timed.id, " ".join(["word"] * 50))
        db.update_refinement_time(timed.id, 30_000)

        untimed = db.add_transcript(raw_text="rough text", duration_ms=3000)
        db.update_normalized_text(untimed.id, " ".join(["word"] * 100))

        stats = compute_usage_stats(db)

        assert stats["transcripts_with_refinement_time"] == 1
        assert stats["avg_refinement_wpm"] == 100

    def test_processing_forecasting_metadata_is_aggregated_from_matching_samples(self, db):
        transcript = db.add_transcript(
            raw_text="rough source text",
            duration_ms=20_000,
            transcription_time_ms=5_000,
            transcription_provider="groq",
            transcription_model_id="whisper-large-v3-turbo",
        )
        db.update_normalized_text(transcript.id, "refined source text")
        db.update_retranscription_processing_context(
            transcript.id,
            normalized_text="retranscribed source text",
            retranscription_time_ms=10_000,
            retranscription_provider="local_faster_whisper",
            retranscription_model_id="large-v3",
            retranscription_resolved_device="cuda",
            retranscription_compute_type="float16",
            retranscription_cpu_threads=6,
            retranscription_prompt_text="Prefer names.",
            retranscription_prompt_chars=13,
            retranscription_prompt_words=2,
        )
        db.update_refinement_processing_context(
            transcript.id,
            refinement_time_ms=4_000,
            refinement_provider="lm_studio",
            refinement_model_id="qwen3.5-27b",
            refinement_resolved_device="cuda",
            refinement_compute_type="float16",
            refinement_cpu_threads=8,
            refinement_gpu_layers=99,
            refinement_use_thinking=False,
            refinement_prompt_text="Fix grammar.",
            refinement_prompt_chars=12,
            refinement_prompt_words=2,
            refinement_prompt_tokens=80,
            refinement_completion_tokens=40,
            refinement_total_tokens=120,
        )

        stats = compute_usage_stats(db)

        assert stats["avg_transcription_speed_x"] == 4.0
        assert stats["avg_retranscription_speed_x"] == 2.0
        assert stats["avg_refinement_tokens_per_second"] == 30.0
        assert stats["avg_refinement_prompt_tokens"] == 80
        assert stats["avg_refinement_completion_tokens"] == 40
        assert stats["transcripts_with_retranscription_time"] == 1
        assert stats["transcripts_with_refinement_tokens"] == 1
        assert stats["total_retranscriptions"] == 1
        assert stats["transcription_provider_counts"] == {"groq": 1}
        assert stats["transcription_model_counts"] == {"whisper-large-v3-turbo": 1}
        assert stats["retranscription_provider_counts"] == {"local_faster_whisper": 1}
        assert stats["retranscription_model_counts"] == {"large-v3": 1}
        assert stats["refinement_provider_counts"] == {"lm_studio": 1}
        assert stats["refinement_model_counts"] == {"qwen3.5-27b": 1}


class TestUserViewMetrics:
    def test_user_metrics_full_payload_values_are_mathematically_pinned(self, db):
        today = datetime.now().astimezone().replace(microsecond=0)
        yesterday = today - timedelta(days=1)
        today_key = today.strftime("%Y-%m-%d")
        yesterday_key = yesterday.strftime("%Y-%m-%d")

        _insert_transcript(
            db,
            created_at=today.isoformat(),
            raw_text="um um alpha beta alpha.",
            normalized_text="alpha beta.",
            duration_ms=8000,
            speech_duration_ms=5000,
            transcription_time_ms=2000,
            refinement_time_ms=4000,
        )
        _insert_transcript(
            db,
            created_at=yesterday.isoformat(),
            raw_text="you know gamma gamma",
            duration_ms=0,
            speech_duration_ms=0,
        )

        metrics = compute_user_view_metrics(db, typing_wpm=30, user_name="Drew")

        assert metrics == {
            "user_name": "Drew",
            "typing_wpm": 30,
            "count": 2,
            "total_words": 9,
            "total_recorded_seconds": 9.6,
            "total_speech_seconds": 6.6,
            "avg_seconds": 4.8,
            "avg_wpm": 82,
            "time_saved_seconds": 8.4,
            "total_silence_seconds": 3.0,
            "avg_silence_seconds": 3.0,
            "vocabulary_ratio": pytest.approx(0.6667),
            "filler_count": 3,
            "filler_breakdown": [
                {"label": "um", "count": 2},
                {"label": "you know", "count": 1},
            ],
            "current_streak": 2,
            "longest_streak": 2,
            "refined_count": 1,
            "fillers_removed": 2,
            "verbatim_avg_fk_grade": pytest.approx(4.5),
            "refined_avg_fk_grade": pytest.approx(8.8),
            "verbatim_fk_for_refined": pytest.approx(5.2),
            "fk_grade_delta": pytest.approx(3.6),
            "total_transcription_seconds": 2.0,
            "total_refinement_seconds": 4.0,
            "has_timing_data": True,
            "avg_transcription_speed_x": 4.0,
            "avg_refinement_wpm": 30,
            "refinement_time_saved_seconds": 4.0,
            "daily_word_buckets": [
                {"date": yesterday_key, "words": 4},
                {"date": today_key, "words": 5},
            ],
        }

    def test_user_metrics_estimate_missing_duration_per_transcript(self, db):
        words = " ".join(["word"] * 150)
        db.add_transcript(raw_text=words, duration_ms=60_000)
        db.add_transcript(raw_text=words, duration_ms=0)

        metrics = compute_user_view_metrics(db, typing_wpm=40)

        assert metrics["total_words"] == 300
        assert metrics["total_recorded_seconds"] == pytest.approx(120.0)
        assert metrics["avg_wpm"] == 150
        assert metrics["time_saved_seconds"] == pytest.approx(330.0)

    def test_user_metrics_estimate_silence_when_vad_missing(self, db):
        words = " ".join(["word"] * 150)
        db.add_transcript(raw_text=words, duration_ms=120_000, speech_duration_ms=0)

        metrics = compute_user_view_metrics(db, typing_wpm=40)

        assert metrics["total_speech_seconds"] == pytest.approx(60.0)
        assert metrics["total_silence_seconds"] == pytest.approx(60.0)
        assert metrics["avg_silence_seconds"] == pytest.approx(60.0)

    def test_user_metrics_use_matching_timing_samples(self, db):
        db.add_transcript(
            raw_text=" ".join(["word"] * 30),
            duration_ms=30_000,
            transcription_time_ms=10_000,
        )
        db.add_transcript(
            raw_text=" ".join(["word"] * 60),
            duration_ms=60_000,
            transcription_time_ms=0,
        )
        timed = db.add_transcript(raw_text="rough text", duration_ms=3000)
        db.update_normalized_text(timed.id, " ".join(["word"] * 50))
        db.update_refinement_time(timed.id, 30_000)
        untimed = db.add_transcript(raw_text="rough text", duration_ms=3000)
        db.update_normalized_text(untimed.id, " ".join(["word"] * 100))

        metrics = compute_user_view_metrics(db, typing_wpm=40)

        assert metrics["avg_transcription_speed_x"] == 3.0
        assert metrics["avg_refinement_wpm"] == 100
        assert metrics["refinement_time_saved_seconds"] == pytest.approx(120.0)

    def test_user_metrics_keep_speech_metrics_raw_after_refinement(self, db):
        transcript = db.add_transcript(raw_text="um um word", duration_ms=3000)
        db.update_normalized_text(transcript.id, "polished sentence")

        metrics = compute_user_view_metrics(db, typing_wpm=40)

        assert metrics["total_words"] == 3
        assert metrics["filler_count"] == 2
        assert metrics["daily_word_buckets"][-1]["words"] == 3


class TestSessionMetrics:
    def test_today_metrics_use_local_time_and_normalized_text(self, db):
        _insert_transcript(
            db,
            created_at=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
            raw_text="old text here",
            duration_ms=3000,
        )
        current = db.add_transcript(raw_text="um yeah so basically hello world", duration_ms=5000)
        db.update_normalized_text(current.id, "hello world")

        stats = compute_usage_stats(db)

        assert stats["today_count"] == 1
        assert stats["today_words"] == 2

    def test_streaks_and_active_days_use_local_dates(self, db):
        now_utc = datetime.now(timezone.utc)
        _insert_transcript(
            db,
            created_at=now_utc.isoformat(),
            raw_text="today entry",
            duration_ms=3000,
        )
        _insert_transcript(
            db,
            created_at=(now_utc - timedelta(days=1)).isoformat(),
            raw_text="yesterday entry",
            duration_ms=3000,
        )

        stats = compute_usage_stats(db)

        expected_days_active = 2 if datetime.now().astimezone().weekday() >= 1 else 1
        assert stats["current_streak"] == 2
        assert stats["longest_streak"] == 2
        assert stats["days_active_this_week"] == expected_days_active
