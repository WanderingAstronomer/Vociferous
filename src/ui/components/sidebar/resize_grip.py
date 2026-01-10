"""
SidebarResizeGrip - Draggable edge for resizing sidebar.

Shows a subtle vertical line on hover, allows dragging to resize.
Replaces the chevron-based collapse/expand system.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QMouseEvent, QPainter, QPaintEvent
from PyQt6.QtWidgets import QWidget

from ui.constants import Colors, Dimensions


class SidebarResizeGrip(QWidget):
    """
    Draggable resize grip on sidebar right edge.
    
    Features:
    - Invisible by default, shows subtle line on hover
    - Draggable to resize sidebar width
    - Snaps to collapse when dragged below minimum threshold
    
    Signals:
        resized(int): Emitted during drag with new width
        collapseRequested(): Emitted when dragged below collapse threshold
        expandRequested(int): Emitted when clicked while collapsed
    """
    
    resized = pyqtSignal(int)
    collapseRequested = pyqtSignal()
    expandRequested = pyqtSignal(int)  # target width
    
    # Layout constants
    GRIP_WIDTH = 8  # Hit area width
    LINE_WIDTH = 3  # Visible line width on hover
    
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebarResizeGrip")
        self.setFixedWidth(self.GRIP_WIDTH)
        self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
        self.setMouseTracking(True)
        
        self._dragging = False
        self._drag_start_x = 0
        self._drag_start_width = 0
        self._hovered = False
        

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the resize grip (visible on hover or drag)."""
        if not self._hovered and not self._dragging:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw subtle vertical line
        line_color = QColor(Colors.PRIMARY if self._dragging else Colors.TEXT_TERTIARY)
        line_color.setAlpha(180 if self._dragging else 100)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(line_color)
        
        # Center the line in the grip area
        line_x = (self.width() - self.LINE_WIDTH) // 2
        painter.drawRoundedRect(
            line_x, 4,
            self.LINE_WIDTH, self.height() - 8,
            1, 1
        )
        
    def enterEvent(self, event) -> None:
        """Show grip line on mouse enter."""
        self._hovered = True
        self.update()
        
    def leaveEvent(self, event) -> None:
        """Hide grip line on mouse leave."""
        self._hovered = False
        if not self._dragging:
            self.update()
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Start drag operation."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_x = event.globalPosition().x()
            
            # Get current sidebar width from parent
            sidebar = self.parent()
            if sidebar:
                self._drag_start_width = sidebar.width()
            
            self.update()
            event.accept()
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle drag to resize."""
        if not self._dragging:
            return
            
        delta_x = event.globalPosition().x() - self._drag_start_x
        new_width = int(self._drag_start_width + delta_x)
        
        # Get window width for percentage-based bounds
        parent = self.parent()
        window_width = parent.parent().width() if parent and parent.parent() else 1000
        
        # Use centralized clamping logic for consistency
        new_width = Dimensions.clamp_sidebar_width(new_width, window_width)
        
        self.resized.emit(new_width)
        event.accept()
    
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """End drag operation."""
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self.update()
            event.accept()
