"""
TreeHoverDelegate - Custom paint delegate for history tree items.

Handles:
- Day headers with collapsible sections
- Transcript entries using the UNIFIED transcript painter
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
from ui.widgets.transcript_item import paint_transcript_entry


class TreeHoverDelegate(QStyledItemDelegate):
    """
    Delegate for history tree view.

    Paints:
    - Day headers with collapsible styling
    - Transcript entries using unified paint_transcript_entry
    """

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        """Paint the item with custom styling."""
        is_header = bool(index.data(TranscriptionModel.IsHeaderRole))

        if is_header:
            self._paint_header(painter, option, index)
        else:
            self._paint_entry(painter, option, index)

    def _paint_header(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        """Paint a day header row."""
        # Background for selection/hover
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(Colors.HOVER_BG_SECTION))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, QColor(Colors.HOVER_BG_DAY))

        # Customize option before standard paint
        new_option = QStyleOptionViewItem(option)
        new_option.state &= ~QStyle.StateFlag.State_Selected

        header_font = QFont(option.font)
        header_font.setPointSize(Typography.DAY_HEADER_SIZE)
        header_font.setWeight(QFont.Weight.Normal)
        new_option.font = header_font
        new_option.palette.setColor(
            new_option.palette.ColorRole.Text, QColor(Colors.TEXT_SECONDARY)
        )
        new_option.displayAlignment = (
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        super().paint(painter, new_option, index)

    def _paint_entry(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        """Paint a transcript entry row using the unified painter."""
        # Get the data from the model
        # Column 0 = time, Column 1 = preview (logical columns)
        model = index.model()
        if model is None:
            return

        # Get both columns' data
        time_index = model.index(index.row(), 0, index.parent())
        preview_index = model.index(index.row(), 1, index.parent())
        
        time_text = str(time_index.data(Qt.ItemDataRole.DisplayRole) or "")
        preview_text = str(preview_index.data(Qt.ItemDataRole.DisplayRole) or "")

        # For column 0 (time column), we only paint when it's the "full row"
        # But since we're painting the whole entry ourselves, we need to handle
        # this carefully. We paint the full entry on the first column only.
        if index.column() == 0:
            # Calculate the full row rect spanning both columns
            # Get the rect for column 1 to determine full width
            view = option.widget
            if view and hasattr(view, 'visualRect'):
                col1_rect = view.visualRect(preview_index)
                full_rect = option.rect.united(col1_rect)
            else:
                full_rect = option.rect
            
            # Create a modified option with the full rect
            full_option = QStyleOptionViewItem(option)
            full_option.rect = full_rect
            
            # Use the unified painter
            paint_transcript_entry(
                painter,
                full_option,
                preview_text=preview_text,
                time_text=time_text,
                draw_background=True,
            )
        # Column 1 - don't paint (we already painted full row on column 0)
        # This prevents double-painting
