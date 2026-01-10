"""Custom-painted content panel to fix QScrollArea border clipping."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QWidget

from ui.constants import CONTENT_PANEL_RADIUS, Colors


class ContentPanel(QFrame):
    """Panel that paints its own rounded background + border.

    This fixes Qt stylesheet border clipping with border-radius when
    hosting a QScrollArea that scrolls to the bottom.

    Styling is controlled via dynamic properties:
    - recording=true: transparent, no border
    - editing=true: 3px blue border
    - default: 1px blue border
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # Styles are applied at app level via generate_unified_stylesheet()

    def sizeHint(self) -> QSize:
        """Return the preferred size for this widget."""
        return QSize(400, 300)

    def minimumSizeHint(self) -> QSize:
        """Return the minimum size required for this widget."""
        return QSize(200, 100)

    def paintEvent(self, event) -> None:
        """Custom paint for rounded corners with proper border rendering."""
        recording = bool(self.property("recording"))
        editing = bool(self.property("editing"))

        if recording:
            # Transparent panel during waveform
            return

        border_width = 3 if editing else 1
        bg_color = QColor(Colors.BG_TERTIARY)
        border_color = QColor(Colors.ACCENT_BLUE)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Center stroke on half-pixel for crisp borders
        half = border_width / 2.0
        rect = QRectF(self.rect()).adjusted(half, half, -half, -half)
        radius = float(CONTENT_PANEL_RADIUS)

        # Fill background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_color)
        painter.drawRoundedRect(rect, radius, radius)

        # Draw border
        pen = QPen(border_color, border_width)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, radius, radius)
