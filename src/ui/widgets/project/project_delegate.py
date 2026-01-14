"""
ProjectDelegate - Custom paint delegate for Project items.

Handles painting of:
- Project header rows with color markers
- Transcript child rows with hover/selection states
"""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QModelIndex, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import (
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from ui.constants import Colors, Typography
from ui.utils.history_utils import format_time_compact
from ui.widgets.transcript_item import (
    ROLE_FULL_TEXT,
    ROLE_TIMESTAMP_ISO,
    paint_transcript_entry,
)


class ProjectDelegate(QStyledItemDelegate):
    """
    Custom delegate for Project items.

    Paints full-width colored bars with white text.
    Only applies to top-level Project items.
    """

    # Role constants - must match ProjectTreeWidget
    ROLE_IS_GROUP = Qt.ItemDataRole.UserRole + 10
    ROLE_COLOR = Qt.ItemDataRole.UserRole + 12

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        """Paint the item with custom styling."""
        # Calculate indentation offset
        indent_width = 20  # Default fallback
        if hasattr(option.widget, "indentation"):
            indent_width = option.widget.indentation()

        depth = 0
        parent = index.parent()
        while parent.isValid():
            depth += 1
            parent = parent.parent()

        indent_offset = depth * indent_width

        # Create adjusted option with offset rect
        # We modify the rect to start AFTER the indentation
        # This ensures backgrounds and content are properly indented
        adj_option = QStyleOptionViewItem(option)
        adj_option.rect.setLeft(adj_option.rect.left() + indent_offset)

        is_group = index.data(self.ROLE_IS_GROUP)

        if is_group:
            self._paint_group_item(painter, adj_option, index)
        else:
            self._paint_transcript_item(painter, adj_option, index)

    def _paint_group_item(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        """Paint a Project header row."""
        color = index.data(self.ROLE_COLOR)

        if color:
            self._paint_colored_group_header(painter, option, index, color)
        else:
            self._paint_default_group_header(painter, option, index)

    def _paint_colored_group_header(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
        color: str,
    ) -> None:
        """Paint a group header with color marker."""
        text = index.data(0) or ""  # Column 0 has name now
        font = QFont(option.font)
        font.setPointSize(Typography.FOCUS_GROUP_NAME_SIZE)
        font.setWeight(QFont.Weight.DemiBold)

        painter.save()
        painter.setFont(font)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(option.rect)

        # Header background
        painter.setBrush(QColor(Colors.BG_HEADER))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 4, 4)

        # Small color marker (left)
        marker_w = 10
        marker_rect = rect.adjusted(6, 6, -(rect.width() - (6 + marker_w)), -6)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(marker_rect, 3, 3)

        # Text, padded
        text_rect = rect.adjusted(6 + marker_w + 10, 0, -12, 0)

        # Subgroups (nested groups) use secondary text color
        text_color = QColor(Colors.TEXT_PRIMARY)
        if index.parent().isValid():
            text_color = QColor(Colors.TEXT_SECONDARY)

        painter.setPen(text_color)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            text,
        )

        painter.restore()

    def _paint_default_group_header(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        """Paint a group header without color."""
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(Colors.HOVER_BG_SECTION))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, QColor(Colors.HOVER_BG_SECTION))
        else:
            painter.fillRect(option.rect, QColor(Colors.BG_TERTIARY))

        # Manually draw text since we might be bypassing super().paint
        text = index.data(0) or ""
        painter.save()
        painter.setPen(QColor(Colors.TEXT_PRIMARY))
        # Add basic padding
        text_rect = QRectF(option.rect).adjusted(8, 0, -8, 0)
        painter.drawText(
            text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text
        )
        painter.restore()

    def _paint_transcript_item(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        """Paint a transcript child row with parent group's color and indent."""
        # Get parent group's color
        parent_index = index.parent()
        group_color = (
            parent_index.data(self.ROLE_COLOR) if parent_index.isValid() else None
        )

        # Use simple hover/selection background (subtle)
        # We removed the "bright solid rectangular blue square" effect by using standard hover colors
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(Colors.HOVER_BG_SECTION))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, QColor(Colors.HOVER_BG_ITEM))
        elif group_color:
            # Very subtle tint for static state if group has color
            color = QColor(group_color)
            color.setAlpha(15)
            painter.fillRect(option.rect, color)

        # Draw "blue circular dot" selection indicator
        if option.state & QStyle.StateFlag.State_Selected:
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)

            # Use group color if available, else standard accent
            dot_color = (
                QColor(group_color) if group_color else QColor(Colors.ACCENT_PRIMARY)
            )
            painter.setBrush(dot_color)

            # Position dot on the left side
            dot_size = 6
            # 8px left padding match
            dot_x = option.rect.left() + 4
            dot_y = option.rect.center().y() - (dot_size / 2)

            painter.drawEllipse(QRectF(dot_x, dot_y, dot_size, dot_size))
            painter.restore()

        # Get data
        preview_text = index.data(ROLE_FULL_TEXT) or index.data(0) or ""
        timestamp = index.data(ROLE_TIMESTAMP_ISO)
        time_text = ""
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                time_text = format_time_compact(dt)
            except (ValueError, TypeError):
                pass

        # Create modified option with more padding for the dot if selected
        text_option = QStyleOptionViewItem(option)
        if option.state & QStyle.StateFlag.State_Selected:
            text_option.rect.setLeft(text_option.rect.left() + 12)

        # Delegate to unified painter (draw_background=False since we handled tints)
        paint_transcript_entry(
            painter, text_option, preview_text, time_text, draw_background=False
        )
