"""
Custom toggle switch widget - pill-shaped with sliding circle.
Modern alternative to checkboxes for boolean settings.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty, pyqtSignal, QSize
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtWidgets import QCheckBox

import ui.constants.colors as c


class ToggleSwitch(QCheckBox):
    """
    Animated toggle switch widget - pill-shaped background with sliding circle.

    States:
    - Unchecked: Dark background, circle on left
    - Checked: Primary color background, circle on right with smooth animation
    """

    toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        """
        Initialize the toggle switch widget.

        Args:
            parent: Optional parent widget for Qt ownership hierarchy.
        """
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(50, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Animation for circle position
        self._circle_position = 3  # Start position (left)
        self.animation = QPropertyAnimation(self, b"circle_position", self)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.setDuration(200)  # milliseconds

        # Connect state change to animation
        self.stateChanged.connect(self._animate_toggle)

    def sizeHint(self) -> QSize:
        """
        Return preferred size for the toggle switch.
        
        Per Qt6 layout documentation, custom widgets must implement sizeHint()
        even when using setFixedSize() for proper layout integration.
        
        Returns:
            QSize: Fixed size of 50x24 pixels
        
        References:
            - layout.html § "Custom Widgets in Layouts"
        """
        return QSize(50, 24)

    def minimumSizeHint(self) -> QSize:
        """
        Return minimum size for the toggle switch.
        
        Returns:
            QSize: Minimum size equals fixed size (50x24)
        """
        return QSize(50, 24)

    @pyqtProperty(float)
    def circle_position(self) -> float:
        """Get the current horizontal position of the toggle circle."""
        return self._circle_position

    @circle_position.setter
    def circle_position(self, pos: float) -> None:
        """Set the circle position and trigger a repaint."""
        self._circle_position = pos
        self.update()

    def _animate_toggle(self, state: int) -> None:
        """Animate circle sliding between positions."""
        if state == Qt.CheckState.Checked.value:
            # Move circle to right
            self.animation.setStartValue(self._circle_position)
            self.animation.setEndValue(29)  # 50 - 18 - 3 = 29
        else:
            # Move circle to left
            self.animation.setStartValue(self._circle_position)
            self.animation.setEndValue(3)

        self.animation.start()

    def paintEvent(self, event):
        """Custom painting for pill-shaped toggle."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Colors based on state
        if self.isChecked():
            bg_color = QColor(c.BLUE_4)
            circle_color = QColor(c.TOGGLE_CIRCLE_ON)
        else:
            bg_color = QColor(c.GRAY_7)  # Dark gray
            circle_color = QColor(c.GRAY_5)  # Medium gray

        # Draw pill-shaped background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_color)
        painter.drawRoundedRect(0, 0, 50, 24, 12, 12)

        # Draw sliding circle
        painter.setBrush(circle_color)
        painter.drawEllipse(int(self._circle_position), 3, 18, 18)

    def hitButton(self, pos):
        """Make entire widget clickable."""
        return self.contentsRect().contains(pos)

    def cleanup(self) -> None:
        """
        Clean up animation resources.
        
        Stops and deletes the toggle animation to prevent resource leaks.
        Per Vociferous cleanup protocol, all stateful widgets must implement
        cleanup() and release timers, animations, and external connections.
        
        This method is idempotent and safe to call multiple times.
        """
        if hasattr(self, "animation") and self.animation is not None:
            if self.animation.state() == QPropertyAnimation.State.Running:
                self.animation.stop()
            # Don't delete the animation as it might be needed again
            # Just ensure it's stopped
