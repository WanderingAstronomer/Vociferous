"""
TreeHoverDelegate - Custom paint delegate for history tree items.

Single-column layout with unified row interaction:
- Day headers: Full-width, bold, accent color
- Transcript entries: Indented preview text, time shown right-aligned on same row
"""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QModelIndex, QRect, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QFontMetrics
from PyQt6.QtWidgets import (
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

import src.ui.constants.colors as c
from src.ui.constants import Typography
from src.ui.constants.dimensions import DAY_HEADER_ROW_HEIGHT, TRANSCRIPT_ROW_HEIGHT
from src.ui.models import TranscriptionModel
from src.ui.utils.history_utils import format_time_compact


class TreeHoverDelegate(QStyledItemDelegate):
    """
    Delegate for history tree view with single-column layout.

    Unified styling for each row:
    - Day headers: Full width, accent blue, bold
    - Entries: Left indent, preview text left, time right (same row)

    Each row is a single interactive surface with unified hover/selection.
    """

    # Layout constants
    ENTRY_INDENT = 16  # Left indent for entries under day headers
    TIME_WIDTH = 90  # Fixed width for time display on right (increased for padding)
    PADDING_H = 8  # Horizontal padding

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        """Paint the item with custom styling."""
        is_header = bool(index.data(TranscriptionModel.IsHeaderRole))

        painter.save()

        # Unified row background for selection/hover
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(c.GRAY_7))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            hover_color = QColor(c.GRAY_7 if is_header else c.GRAY_7)
            painter.fillRect(option.rect, hover_color)

        if is_header:
            self._paint_header(painter, option, index)
        else:
            self._paint_entry(painter, option, index)

        painter.restore()

    def _paint_header(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        """Paint a day header row spanning full width."""
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if not text:
            return

        # Get full row width from viewport
        tree_view = option.widget
        if tree_view and hasattr(tree_view, "viewport"):
            viewport_width = tree_view.viewport().width()
            rect = QRect(0, option.rect.top(), viewport_width, option.rect.height())
        else:
            rect = option.rect

        # Header font and color
        header_font = QFont(option.font)
        header_font.setPointSize(Typography.DAY_HEADER_SIZE)
        header_font.setWeight(QFont.Weight.Bold)
        painter.setFont(header_font)
        painter.setPen(QColor(c.BLUE_4))

        # Draw left-aligned with padding
        text_rect = rect.adjusted(self.PADDING_H, 0, -self.PADDING_H, 0)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)

    def _paint_entry(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        """
        Paint a transcript entry row in single-column layout.

        Layout: [indent][preview text...                    ][time]
        - Preview: Left-aligned, primary text color, elided if too long
        - Time: Right-aligned, accent blue color, fixed width
        """
        # Get full row width from viewport
        tree_view = option.widget
        if tree_view and hasattr(tree_view, "viewport"):
            viewport_width = tree_view.viewport().width()
            row_rect = QRect(0, option.rect.top(), viewport_width, option.rect.height())
        else:
            row_rect = option.rect

        # Get data
        preview_text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        timestamp = index.data(TranscriptionModel.TimestampRole) or ""
        project_color = index.data(TranscriptionModel.ColorRole)

        # Format time from timestamp
        time_text = ""
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                time_text = format_time_compact(dt)
            except (ValueError, TypeError):
                pass

        # Calculate rects
        # Project indicator: small bar on left edge (before indent)
        # Only draw if color exists
        indicator_width = 4
        indicator_rect = QRect()
        if project_color:
            indicator_rect = QRect(
                row_rect.left(),
                row_rect.top() + 4,  # top padding
                indicator_width,
                row_rect.height() - 8,  # bottom padding
            )

        # Preview area: from indent to (row width - time width - padding)
        preview_left = self.ENTRY_INDENT
        preview_right = row_rect.width() - self.TIME_WIDTH - self.PADDING_H
        preview_rect = QRect(
            preview_left,
            row_rect.top(),
            preview_right - preview_left,
            row_rect.height(),
        )

        # Time area: right side with fixed width
        time_rect = QRect(
            row_rect.width() - self.TIME_WIDTH - self.PADDING_H,
            row_rect.top(),
            self.TIME_WIDTH,
            row_rect.height(),
        )

        # Draw Project Indicator
        if project_color:
            painter.translate(0.5, 0.5)  # Anti-aliasing tweak
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(project_color))
            painter.drawRoundedRect(indicator_rect, 2, 2)
            painter.translate(-0.5, -0.5)

        # Draw preview text (left aligned, primary color)
        preview_font = QFont(option.font)
        preview_font.setPointSize(Typography.TRANSCRIPT_ITEM_SIZE)
        painter.setFont(preview_font)
        painter.setPen(QColor(c.GRAY_4))

        # Elide text if too long
        fm = painter.fontMetrics()
        elided_preview = self._elide_word_aware(fm, preview_text, preview_rect.width())
        painter.drawText(
            preview_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            elided_preview,
        )

        # Draw time (right aligned, accent blue)
        time_font = QFont(option.font)
        time_font.setPointSize(Typography.SMALL_SIZE)
        painter.setFont(time_font)
        painter.setPen(QColor(c.BLUE_4))
        painter.drawText(
            time_rect,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            time_text,
        )

    def _elide_word_aware(self, fm: QFontMetrics, text: str, width: int) -> str:
        """
        Elide text respecting word boundaries where possible.
        Refines standard Qt elision to avoid cutting words mid-stream.
        """
        # 1. Standard Qt Elision (efficient, accurate width calc)
        elided = fm.elidedText(text, Qt.TextElideMode.ElideRight, width)

        # If it fits or doesn't end in ellipsis, we're done
        # Note: Qt uses U+2026 (…) for ellipsis
        if elided == text or not elided.endswith("…"):
            return elided

        # 2. Check if we cut in the middle of a word
        # Remove ellipsis to check the cut point
        content = elided[:-1]

        # Safety: If implementation varies or text doesn't match, fallback
        if not text.startswith(content):
            return elided

        # Check character immediately following the cut
        if len(content) < len(text):
            next_char = text[len(content)]
            # If next char is NOT a space, we are likely mid-word
            if next_char != " " and not content.endswith(" "):
                # Find the nearest previous space
                last_space = content.rfind(" ")
                if last_space > 0:
                    # Cut at the space and re-add ellipsis
                    return content[:last_space] + "…"

        return elided

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        """Return size hint for items."""
        is_header = bool(index.data(TranscriptionModel.IsHeaderRole))

        # Use appropriate row height
        if is_header:
            return QSize(-1, DAY_HEADER_ROW_HEIGHT)
        else:
            return QSize(-1, TRANSCRIPT_ROW_HEIGHT)
