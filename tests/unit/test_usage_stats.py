"""Unit tests for the backend analytics contract in usage_stats.compute_usage_stats()."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.core.usage_stats import compute_usage_stats
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
            "transcripts_with_transcription_time",
            "transcripts_with_refinement_time",
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
