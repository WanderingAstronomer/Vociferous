"""
Workspace Panel - Styled container for workspace content area.

Custom-painted frame with rounded corners and state-dependent borders.
Used as the main visual container in the workspace to hold workspace content
(recording, transcribing, viewing, editing states).
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QWidget

from src.ui.constants import CONTENT_PANEL_RADIUS
import src.ui.constants.colors as c


class WorkspacePanel(QFrame):
    """Styled visual container for workspace content.

    Paints its own rounded background + dynamic border based on state.
    This fixes Qt stylesheet border clipping with border-radius when
    hosting scrolling content.

    Styling controlled via dynamic properties:
    - recording=true: transparent background, no border
    - editing=true: 3px blue border (emphasis)
    - default: 1px blue border (standard)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def sizeHint(self) -> QSize:
        """Return the preferred size for this widget."""
        return QSize(400, 200)

    def minimumSizeHint(self) -> QSize:
        """Return the minimum size required for this widget."""
        return QSize(200, 100)

    def paintEvent(self, event) -> None:
        """Custom paint for rounded corners with proper border rendering."""
        recording = bool(self.property("recording"))
        editing = bool(self.property("editing"))

        if recording:
            # Transparent during recording/waveform visualization
            return

        border_width = 3 if editing else 1
        bg_color = QColor(c.CONTENT_BACKGROUND)
        border_color = QColor(c.CONTENT_BORDER)

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
