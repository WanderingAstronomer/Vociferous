"""History UI utility functions for grouping and formatting."""

from datetime import datetime

ELLIPSIS = "…"


def group_entries_by_day(entries: list) -> list[tuple[str, datetime, list]]:
    """
    Group history entries by day.

    Args:
        entries: List of HistoryEntry objects

    Returns:
        List of tuples: (day_key, day_datetime, entries_for_day)
    """
    from collections import defaultdict

    groups = defaultdict(list)

    for entry in entries:
        dt = datetime.fromisoformat(entry.timestamp)
        day_key = dt.strftime("%Y-%m-%d")
        groups[day_key].append(entry)

    result = []
    for day_key in sorted(groups.keys(), reverse=True):
        dt = datetime.fromisoformat(f"{day_key}T00:00:00")
        result.append((day_key, dt, groups[day_key]))

    return result


def format_day_header(dt: datetime, include_year: bool = False) -> str:
    """
    Format a date as 'Month DDth' with ordinal suffix.

    Args:
        dt: Datetime object
        include_year: If True, append year like "January 1st, 2024"

    Returns:
        Formatted string like "January 1st" or "January 1st, 2024"
    """
    day = dt.day
    if 10 <= day % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")

    result = dt.strftime(f"%B {day}{suffix}")
    if include_year:
        result += dt.strftime(", %Y")

    return result


def format_time(dt: datetime) -> str:
    """
    Format time as '9:05 a.m.' style (lowercase with periods).

    Args:
        dt: Datetime object

    Returns:
        Formatted time string
    """
    hour = dt.hour
    minute = dt.minute
    period = "a.m." if hour < 12 else "p.m."
    display_hour = hour if hour <= 12 else hour - 12
    if display_hour == 0:
        display_hour = 12

    return f"{display_hour}:{minute:02d} {period}"


def format_time_compact(timestamp: str | datetime) -> str:
    """
    Format ISO timestamp as compact time string.

    Args:
        timestamp: ISO format timestamp string or datetime object

    Returns:
        Formatted time like "9:05 a.m."
    """
    if isinstance(timestamp, str):
        dt = datetime.fromisoformat(timestamp)
    else:
        dt = timestamp
    return format_time(dt)


def format_preview(text: str, max_length: int = 50) -> str:
    """
    Truncate text with ellipsis if too long, respecting word boundaries.

    Args:
        text: Text to format
        max_length: Maximum length before truncation

    Returns:
        Truncated text with ellipsis if needed
    """
    if len(text) <= max_length:
        return text

    # Truncate to limit
    truncated = text[:max_length]

    # Try to find the last space to avoid cutting words
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]

    return truncated + ELLIPSIS
