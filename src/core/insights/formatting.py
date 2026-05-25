"""Pure formatting helpers for analytics insight rendering.

These helpers do not touch the cache or the SLM. They live in their own
module so the prompt construction layer (``highlights``) can compose them
without dragging in the orchestration concerns held by ``InsightManager``.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any


def today_key() -> str:
    """Return today's date as an ``YYYY-MM-DD`` string in the local timezone."""
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def stats_fingerprint(stats: dict[str, Any]) -> str:
    """Stable sha256 of a stats dict for staleness comparison."""
    encoded = json.dumps(stats, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def combine_text(daily_text: str, lifetime_text: str) -> str:
    """Join a daily + lifetime paragraph with a blank line between them."""
    return "\n\n".join(part for part in (daily_text.strip(), lifetime_text.strip()) if part)


def split_legacy_text(text: str, *, has_daily: bool) -> tuple[str, str]:
    """Split a legacy two-paragraph insight into ``(daily, lifetime)``."""
    parts = [part.strip() for part in text.split("\n\n") if part.strip()]
    if not parts:
        return "", ""
    if not has_daily:
        return "", "\n\n".join(parts)
    return parts[0], "\n\n".join(parts[1:])


def strip_json_fence(raw: str) -> str:
    """Extract JSON object from raw response, ignoring conversational filler."""
    text = raw.strip()
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0)
    return text


def fmt_duration(seconds: float) -> str:
    """Human-readable duration for prompt context."""
    if seconds < 60:
        return f"{round(seconds)}s"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    remaining_minutes = minutes % 60
    return f"{hours}h {remaining_minutes}m" if remaining_minutes else f"{hours}h"


def fmt_float(value: Any, decimals: int = 1) -> str:
    """Format numeric values consistently for prompt highlights."""
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return f"{0.0:.{decimals}f}"


def highlight_block(lines: list[str]) -> str:
    """Render curated highlight lines for the analytics prompt."""
    if not lines:
        return "- none"
    return "\n".join(f"- {line}" for line in lines)


def parse_generated_insight(raw: str, *, has_daily: bool) -> tuple[str, str]:
    """Parse the SLM's structured-or-legacy output into ``(daily, lifetime)``."""
    clean = strip_json_fence(raw)
    try:
        parsed = json.loads(clean)
    except json.JSONDecodeError:
        daily_text, lifetime_text = split_legacy_text(clean, has_daily=has_daily)
    else:
        if not isinstance(parsed, dict):
            return "", ""
        daily_text = str(parsed.get("daily") or parsed.get("daily_text") or "").strip()
        lifetime_text = str(parsed.get("lifetime") or parsed.get("lifetime_text") or "").strip()

    if not has_daily:
        lifetime_text = lifetime_text or daily_text
        daily_text = ""
    return daily_text.strip(), lifetime_text.strip()


__all__ = [
    "combine_text",
    "fmt_duration",
    "fmt_float",
    "highlight_block",
    "parse_generated_insight",
    "split_legacy_text",
    "stats_fingerprint",
    "strip_json_fence",
    "today_key",
]
