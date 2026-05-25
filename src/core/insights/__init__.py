"""Analytics insight content helpers: formatting + highlight builders.

The ``InsightManager`` in ``src.core.insight_manager`` orchestrates caching,
scheduling, and SLM invocation. This subpackage holds the pure content
layer: stateless formatters and stats-to-prompt highlight builders.
"""

from src.core.insights.formatting import (
    combine_text,
    fmt_duration,
    fmt_float,
    highlight_block,
    parse_generated_insight,
    split_legacy_text,
    stats_fingerprint,
    strip_json_fence,
    today_key,
)
from src.core.insights.highlights import (
    build_daily_highlights,
    build_long_term_highlights,
    build_refinement_impact_highlight,
)

__all__ = [
    "build_daily_highlights",
    "build_long_term_highlights",
    "build_refinement_impact_highlight",
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
