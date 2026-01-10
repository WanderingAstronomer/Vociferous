"""UI utility functions."""

from .clipboard_utils import copy_text
from .history_utils import (
    format_day_header,
    format_preview,
    format_time,
    format_time_compact,
    group_entries_by_day,
    initial_collapsed_days,
)
from .keycode_mapping import (
    KEY_DISPLAY_NAMES,
    REVERSE_KEY_MAP,
    qt_key_to_evdev,
)

__all__ = [
    "copy_text",
    "format_day_header",
    "format_preview",
    "format_time",
    "format_time_compact",
    "group_entries_by_day",
    "initial_collapsed_days",
    "KEY_DISPLAY_NAMES",
    "REVERSE_KEY_MAP",
    "qt_key_to_evdev",
]
