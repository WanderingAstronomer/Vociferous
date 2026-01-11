"""
FocusGroupDelegate - Custom paint delegate for focus group items.

Handles painting of:
- Focus group header rows with color markers
- Transcript child rows with hover/selection states
"""

from __future__ import annotations

from PyQt6.QtCore import QModelIndex, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import (
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from ui.constants import Colors, Typography


class FocusGroupDelegate(QStyledItemDelegate):
    """
    Custom delegate for Focus Group items.

    Paints full-width colored bars with white text.
    Only applies to top-level Focus Group items.
    """

    # Role constants - must match FocusGroupTreeWidget
    ROLE_IS_GROUP = Qt.ItemDataRole.UserRole + 10
    ROLE_COLOR = Qt.ItemDataRole.UserRole + 12

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        """Paint the item with custom styling."""
        is_group = index.data(self.ROLE_IS_GROUP)

        if is_group:
            self._paint_group_item(painter, option, index)
        else:
            self._paint_transcript_item(painter, option, index)

    def _paint_group_item(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        """Paint a focus group header row."""
        color = index.data(self.ROLE_COLOR)

        # Column 0 is visually on the RIGHT (due to header reordering)
        # We don't need to paint anything there for group headers - just make it transparent
        if index.column() == 0:
            # Transparent - don't paint anything
            return

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
        text = index.data(0) or ""
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

        # Text (primary), padded
        text_rect = rect.adjusted(6 + marker_w + 10, 0, -12, 0)
        painter.setPen(QColor(Colors.TEXT_PRIMARY))
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
        super().paint(painter, option, index)

    def _paint_transcript_item(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        """Paint a transcript child row with parent group's color and indent."""
        # Get parent group's color
        parent_index = index.parent()
        group_color = parent_index.data(self.ROLE_COLOR) if parent_index.isValid() else None
        
        # Paint row-wide background states (hover/selection override group color tint)
        # This ensures both columns highlight together when hovering over either one
        if option.state & QStyle.StateFlag.State_Selected:
            # Selection state - paint across entire row
            if group_color:
                color = QColor(group_color)
                color.setAlpha(80)
                painter.fillRect(option.rect, color)
            else:
                painter.fillRect(option.rect, QColor(Colors.HOVER_BG_SECTION))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            # Hover state - paint across entire row
            if group_color:
                color = QColor(group_color)
                color.setAlpha(50)
                painter.fillRect(option.rect, color)
            else:
                painter.fillRect(option.rect, QColor(Colors.HOVER_BG_ITEM))
        elif index.column() == 1 and group_color:
            # Only column 1 (preview) gets subtle group color tint when not hovered/selected
            color = QColor(group_color)
            color.setAlpha(25)
            painter.fillRect(option.rect, color)

        # Remove selection highlight for default painting
        new_option = QStyleOptionViewItem(option)
        new_option.state &= ~QStyle.StateFlag.State_Selected
        
        # Add left indent for preview column (column 1, visually left)
        if index.column() == 1:
            new_option.rect = new_option.rect.adjusted(16, 0, 0, 0)
        
        super().paint(painter, new_option, index)
