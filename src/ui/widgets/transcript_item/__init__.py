"""Transcript item factory and unified painting."""

from .transcript_item import (
    ROLE_DAY_KEY,
    ROLE_FULL_TEXT,
    ROLE_GROUP_ID,
    ROLE_IS_HEADER,
    ROLE_TIMESTAMP_ISO,
    create_transcript_item,
)
from .transcript_painter import (
    paint_transcript_entry,
    paint_transcript_entry_background,
    get_transcript_entry_option,
)

__all__ = [
    "ROLE_DAY_KEY",
    "ROLE_FULL_TEXT",
    "ROLE_GROUP_ID",
    "ROLE_IS_HEADER",
    "ROLE_TIMESTAMP_ISO",
    "create_transcript_item",
    "paint_transcript_entry",
    "paint_transcript_entry_background",
    "get_transcript_entry_option",
]
