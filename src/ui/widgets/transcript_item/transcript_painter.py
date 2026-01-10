"""
Unified transcript entry painting.

This module provides the SINGLE SOURCE OF TRUTH for how transcript entries
are visually rendered. Both FocusGroupDelegate and TreeHoverDelegate use
this to ensure consistent appearance across the entire application.

Visual specification:
- Preview text: LEFT aligned, primary text color
- Timestamp: RIGHT aligned, blue accent color
- Selection: Gray background (HOVER_BG_SECTION)
- Hover: Subtle gray background (HOVER_BG_ITEM)
"""

from __future__ import annotations

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PyQt6.QtWidgets import QStyle, QStyleOptionViewItem

from ui.constants import Colors, Typography


def paint_transcript_entry_background(
    painter: QPainter,
    option: QStyleOptionViewItem,
) -> None:
    """
    Paint the background for a transcript entry (selection/hover states).
    
    Args:
        painter: The QPainter to use.
        option: The style option with state flags.
    """
    if option.state & QStyle.StateFlag.State_Selected:
        painter.fillRect(option.rect, QColor(Colors.HOVER_BG_SECTION))
    elif option.state & QStyle.StateFlag.State_MouseOver:
        painter.fillRect(option.rect, QColor(Colors.HOVER_BG_ITEM))


def paint_transcript_entry(
    painter: QPainter,
    option: QStyleOptionViewItem,
    preview_text: str,
    time_text: str,
    draw_background: bool = True,
) -> None:
    """
    Paint a complete transcript entry row.
    
    This is the SINGLE SOURCE OF TRUTH for transcript entry rendering.
    Both Focus Groups and Ungrouped Transcripts use this function.
    
    Layout:
        [Preview text (left-aligned)]  ...gap...  [Time (right-aligned, blue)]
    
    Args:
        painter: The QPainter to use.
        option: The style option with rect, state, font info.
        preview_text: The transcript preview text.
        time_text: The formatted timestamp string.
        draw_background: Whether to paint selection/hover background.
    """
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    
    rect = option.rect
    padding_h = 8  # Horizontal padding
    gap = 12  # Gap between preview and time
    
    # Draw background if requested
    if draw_background:
        paint_transcript_entry_background(painter, option)
    
    # === TIME COLUMN (right side, blue) ===
    time_font = QFont(option.font)
    time_font.setPointSize(Typography.DAY_HEADER_SIZE)
    time_font.setWeight(QFont.Weight.Normal)
    
    time_metrics = QFontMetrics(time_font)
    time_width = time_metrics.horizontalAdvance(time_text)
    
    time_rect = QRect(
        rect.right() - padding_h - time_width,
        rect.top(),
        time_width,
        rect.height()
    )
    
    painter.setFont(time_font)
    painter.setPen(QColor(Colors.ACCENT_BLUE))
    painter.drawText(
        time_rect,
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        time_text
    )
    
    # === PREVIEW COLUMN (left side, primary text) ===
    preview_font = QFont(option.font)
    preview_font.setPointSize(Typography.TRANSCRIPT_ITEM_SIZE)
    preview_font.setWeight(QFont.Weight.Normal)
    
    preview_rect = QRect(
        rect.left() + padding_h,
        rect.top(),
        rect.width() - padding_h - time_width - gap - padding_h,
        rect.height()
    )
    
    painter.setFont(preview_font)
    painter.setPen(QColor(Colors.TEXT_PRIMARY))
    
    # Elide preview text if too long
    preview_metrics = QFontMetrics(preview_font)
    elided_preview = preview_metrics.elidedText(
        preview_text,
        Qt.TextElideMode.ElideRight,
        preview_rect.width()
    )
    
    painter.drawText(
        preview_rect,
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        elided_preview
    )
    
    painter.restore()


def get_transcript_entry_option(option: QStyleOptionViewItem) -> QStyleOptionViewItem:
    """
    Create a modified option with selection state removed.
    
    This prevents Qt's default selection painting from interfering.
    
    Args:
        option: The original style option.
        
    Returns:
        A new option with State_Selected removed.
    """
    new_option = QStyleOptionViewItem(option)
    new_option.state &= ~QStyle.StateFlag.State_Selected
    return new_option
