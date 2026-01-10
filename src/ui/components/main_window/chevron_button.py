"""
ChevronButton - SVG icon button for sidebar collapse/expand.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QPushButton


class ChevronButton(QPushButton):
    """Button using SVG icon for collapse/expand."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pointing_left = True

        # Resolve icon path relative to project root
        icons_dir = Path(__file__).resolve().parents[4] / "icons"
        self._icon_path = icons_dir / "collapse.svg"

        self._update_icon()

    def set_direction_left(self, pointing_left: bool) -> None:
        """Set chevron direction: True for left (<), False for right (>)."""
        if self._pointing_left != pointing_left:
            self._pointing_left = pointing_left
            self._update_icon()

    def _update_icon(self) -> None:
        """Update icon based on direction."""
        if not self._icon_path.exists():
            return

        icon = QIcon(str(self._icon_path))

        if not self._pointing_left:
            # Mirror horizontally for right-pointing
            pixmap = icon.pixmap(48, 48)
            img = pixmap.toImage().mirrored(True, False)
            icon = QIcon(QPixmap.fromImage(img))

        self.setIcon(icon)
        self.setIconSize(QSize(32, 32))
