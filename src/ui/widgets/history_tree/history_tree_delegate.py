"""
TreeHoverDelegate - Custom paint delegate for history tree items.

Handles:
- Day headers with secondary text styling
- Transcript entries with UNIFIED styling:
  - Preview: LEFT, primary text color
  - Timestamp: RIGHT, BLUE accent color (matching Focus Groups)
"""

from __future__ import annotations

from PyQt6.QtCore import QModelIndex, Qt
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import (
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from ui.constants import Colors, Typography
from ui.models import TranscriptionModel


class TreeHoverDelegate(QStyledItemDelegate):
    """
    Delegate for history tree view.

    Uses UNIFIED styling for transcript entries to match Focus Groups:
    - Preview text: Left aligned, primary color
    - Timestamp: Right aligned, BLUE accent color
    """

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        """Paint the item with custom styling."""
        is_header = bool(index.data(TranscriptionModel.IsHeaderRole))

        # Subtle selection background
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(Colors.HOVER_BG_SECTION))

        # Hover background (different for headers vs entries)
        if option.state & QStyle.StateFlag.State_MouseOver:
            hover_color = QColor(
                Colors.HOVER_BG_DAY if is_header else Colors.HOVER_BG_ITEM
            )
            painter.fillRect(option.rect, hover_color)

        # Customize option before standard paint
        new_option = QStyleOptionViewItem(option)
        new_option.state &= ~QStyle.StateFlag.State_Selected

        if is_header:
            self._paint_header(painter, new_option, index)
        else:
            self._paint_entry(painter, new_option, index)

    def _paint_header(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        """Paint a day header row spanning full width."""
        # Only paint once per row (in column 0)
        if index.column() != 0:
            return
        
        # Get text from column 0 (where model stores it)
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if not text:
            return
        
        # Get the tree view to calculate full row width
        tree_view = option.widget
        if not tree_view:
            return
        
        # Calculate full row rect spanning both columns
        viewport_width = tree_view.viewport().width()
        full_row_rect = option.rect
        full_row_rect.setLeft(0)
        full_row_rect.setWidth(viewport_width)
        
        # Paint the header text across the full width
        painter.save()
        header_font = QFont(option.font)
        header_font.setPointSize(Typography.DAY_HEADER_SIZE)
        header_font.setWeight(QFont.Weight.Bold)
        painter.setFont(header_font)
        painter.setPen(QColor(Colors.ACCENT_BLUE))
        
        # Draw left-aligned with padding across full width
        text_rect = full_row_rect.adjusted(8, 0, -8, 0)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            text
        )
        painter.restore()

    def _paint_entry(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        """
        Paint a transcript entry row.
        
        UNIFIED STYLING (matches Focus Groups):
        - Column 0 (time): Blue accent color, right-aligned
        - Column 1 (preview): Primary text color, left-aligned
        """
        if index.column() == 0:
            # TIME column - BLUE color, right-aligned
            time_font = QFont(option.font)
            time_font.setPointSize(Typography.DAY_HEADER_SIZE)
            time_font.setWeight(QFont.Weight.Normal)
            option.font = time_font
            # USE ACCENT_BLUE - same as Focus Groups factory!
            option.palette.setColor(
                option.palette.ColorRole.Text, QColor(Colors.ACCENT_BLUE)
            )
            option.displayAlignment = (
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
        elif index.column() == 1:
            # PREVIEW column - primary text color, left-aligned with indent
            preview_font = QFont(option.font)
            preview_font.setPointSize(Typography.TRANSCRIPT_ITEM_SIZE)
            preview_font.setWeight(QFont.Weight.Normal)
            option.font = preview_font
            option.palette.setColor(
                option.palette.ColorRole.Text, QColor(Colors.TEXT_PRIMARY)
            )
            option.displayAlignment = (
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            # Add left indent for transcript entries
            option.rect = option.rect.adjusted(16, 0, 0, 0)

        super().paint(painter, option, index)
