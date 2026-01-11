"""
Shared factory for creating transcript tree items.
Ensures consistent rendering between HistoryTreeWidget and FocusGroupTreeWidget.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QTreeWidgetItem

from ui.constants import Colors, Typography
from ui.utils.history_utils import (
    format_day_header,
    format_preview,
    format_time,
    format_time_compact,
)

if TYPE_CHECKING:
    from history_manager import HistoryEntry

# Item Data Roles (Must match usages in widgets)
ROLE_DAY_KEY = Qt.ItemDataRole.UserRole + 1
ROLE_TIMESTAMP_ISO = Qt.ItemDataRole.UserRole + 2
ROLE_FULL_TEXT = Qt.ItemDataRole.UserRole + 3
ROLE_GROUP_ID = Qt.ItemDataRole.UserRole + 4
ROLE_IS_HEADER = Qt.ItemDataRole.UserRole + 5


def create_transcript_item(
    entry: HistoryEntry, preview_length: int = 100
) -> QTreeWidgetItem:
    """
    Create a standard transcript tree item.

    Args:
        entry: The history entry to display.
        preview_length: Maximum chars for preview text.

    Returns:
        QTreeWidgetItem configured with text, data, and styling.
    """
    # dt = datetime.fromisoformat(entry.timestamp)
    # time_str = format_time_compact(dt)
    preview = format_preview(entry.text, preview_length)

    item = QTreeWidgetItem([preview])
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)

    # Store Data
    item.setData(0, ROLE_TIMESTAMP_ISO, entry.timestamp)
    item.setData(0, ROLE_FULL_TEXT, entry.text)
    # item.setData(1, ROLE_FULL_TEXT, entry.text) # No longer needed
    item.setData(0, ROLE_GROUP_ID, entry.focus_group_id)
    item.setData(0, ROLE_IS_HEADER, False)

    # Alignment
    item.setTextAlignment(
        0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )

    # Styling
    preview_font = QFont()
    preview_font.setPointSize(Typography.TRANSCRIPT_ITEM_SIZE)
    item.setFont(0, preview_font)
    item.setForeground(0, QColor(Colors.TEXT_PRIMARY))

    # Set tooltip (Disabled requested by user choice)
    # dt = datetime.fromisoformat(entry.timestamp)
    # full_date = format_day_header(dt, include_year=True)
    # full_time = format_time(dt)
    # item.setToolTip(0, f"{full_date} at {full_time}\n\n{entry.text}")

    return item
