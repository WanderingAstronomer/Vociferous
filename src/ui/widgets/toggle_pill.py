"""
TogglePill - Multi-select pill button for choices.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QPushButton, QSizePolicy


class TogglePill(QPushButton):
    """
    A toggleable pill-shaped button for multi-select interfaces.

    Signals:
        toggled(bool): Emitted when toggle state changes.
    """

    toggled = pyqtSignal(bool)

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        # Use expanding size policy to allow layout to grow when needed
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self.setMinimumWidth(200)  # Larger minimum to accommodate text growth
        self.setMinimumHeight(48)  # Use minimum instead of fixed to allow flex
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Add padding to inner label for better text breathing room
        self.setStyleSheet("padding: 8px 20px;")
        # Connect clicked signal directly to emit custom toggled signal
        self.clicked.connect(self._on_clicked)
        # Trigger layout recalc when check state changes (font-weight change)
        self.toggled.connect(self._on_toggled_state)

    def _on_clicked(self, checked: bool):
        """Handle click and emit toggled signal."""
        self.toggled.emit(checked)

    def _on_toggled_state(self, checked: bool):
        """Notify parent layout of size change when checked state changes."""
        # Font weight changes (:checked CSS), so tell layout to recalculate
        self.updateGeometry()
        if self.parent():
            # Invalidate parent layout so it reflows with new size hint
            if hasattr(self.parent(), "invalidate"):
                self.parent().invalidate()
