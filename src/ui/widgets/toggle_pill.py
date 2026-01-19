"""
TogglePill - Multi-select pill button for choices.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QPushButton


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
        self.setMinimumWidth(120)
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Connect clicked signal directly to emit custom toggled signal
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self, checked: bool):
        """Handle click and emit toggled signal."""
        self.toggled.emit(checked)
