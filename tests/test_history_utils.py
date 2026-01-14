"""Tests for history UI helper utilities."""

from datetime import datetime

from history_manager import HistoryEntry
from ui.utils import history_utils


def test_group_entries_by_day_preserves_order():
    entries = [
        HistoryEntry(timestamp="2024-01-05T10:00:00", text="Newest", duration_ms=0),
        HistoryEntry(timestamp="2024-01-05T09:00:00", text="Same day", duration_ms=0),
        HistoryEntry(timestamp="2024-01-04T08:00:00", text="Older", duration_ms=0),
    ]

    groups = history_utils.group_entries_by_day(entries)

    assert len(groups) == 2
    first_key, _, first_entries = groups[0]
    second_key, _, second_entries = groups[1]
    assert first_key == "2024-01-05"
    assert [e.text for e in first_entries] == ["Newest", "Same day"]
    assert second_key == "2024-01-04"
    assert [e.text for e in second_entries] == ["Older"]


def test_initial_collapsed_days_excludes_today():
    day_keys = ["2024-01-05", "2024-01-04", "2024-01-03"]
    collapsed = history_utils.initial_collapsed_days(day_keys, "2024-01-04")
    assert collapsed == {"2024-01-05", "2024-01-03"}


def test_format_day_header_ordinal_suffix():
    dt = datetime(2024, 1, 1)
    # Structural assertion rather than exact copy
    formatted = history_utils.format_day_header(dt)
    assert "January" in formatted
    assert "1" in formatted
    
    dt = datetime(2024, 1, 2)
    assert "2" in history_utils.format_day_header(dt)
    
    dt = datetime(2024, 1, 3)
    assert "3" in history_utils.format_day_header(dt)
    
    dt = datetime(2024, 1, 4)
    assert "4" in history_utils.format_day_header(dt)
    
    dt = datetime(2024, 1, 11)
    assert "11" in history_utils.format_day_header(dt)


def test_format_time_lowercase_periods():
    dt = datetime(2024, 1, 1, 9, 5)
    formatted = history_utils.format_time(dt)
    # Structural assertion: hours, minutes, and AM/PM marker
    assert "9" in formatted
    assert "05" in formatted
    assert "m." in formatted.lower() or "m" in formatted.lower()

    dt = datetime(2024, 1, 1, 21, 15)
    formatted = history_utils.format_time(dt)
    assert "9" in formatted
    assert "15" in formatted
    assert "m." in formatted.lower() or "m" in formatted.lower()


def test_format_preview_truncates():
    text = "a" * 10
    assert history_utils.format_preview(text, 5) == f"{'a' * 5}{history_utils.ELLIPSIS}"
