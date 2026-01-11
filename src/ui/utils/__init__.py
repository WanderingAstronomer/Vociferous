"""UI utility functions."""

from .clipboard_utils import copy_text
from .error_handler import (
    ErrorLogger,
    get_error_logger,
    install_exception_hook,
    safe_callback,
    safe_slot,
    safe_slot_silent,
)
from .history_utils import (
    format_day_header,
    format_preview,
    format_time,
    format_time_compact,
    group_entries_by_day,
)
from .keycode_mapping import (
    KEY_DISPLAY_NAMES,
    REVERSE_KEY_MAP,
)

__all__ = [
    "copy_text",
    "ErrorLogger",
    "format_day_header",
    "format_preview",
    "format_time",
    "format_time_compact",
    "get_error_logger",
    "group_entries_by_day",
    "install_exception_hook",
    "safe_callback",
    "safe_slot",
    "safe_slot_silent",
    "KEY_DISPLAY_NAMES",
    "REVERSE_KEY_MAP",
]
