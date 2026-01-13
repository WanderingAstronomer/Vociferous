"""
Icon Rail Component.

A vertical sidebar representing the navigation rail.
Emits signals when the user requests a view change.
"""

from __future__ import annotations

from typing import cast

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QAbstractButton,
    QButtonGroup,
    QSpacerItem,
    QSizePolicy,
)


class IconRail(QWidget):
    """
    Vertical navigation rail.
    
    Signals:
        view_changed(str): Emitted when a navigation button is clicked. 
                           Carries the target view_id.
    """
    
    view_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        self._button_group.buttonClicked.connect(self._on_button_clicked)
        
        # Navigation Buttons
        from ui.constants.view_ids import (
            VIEW_TRANSCRIBE,
            VIEW_RECENT,
            VIEW_PROJECTS,
            VIEW_SEARCH,
        )
        
        self._add_nav_button(VIEW_TRANSCRIBE, "Transcribe")
        self._add_nav_button(VIEW_RECENT, "History")
        self._add_nav_button(VIEW_PROJECTS, "Projects")
        self._add_nav_button(VIEW_SEARCH, "Search")
        # Settings not yet implemented as a view
        # self._add_nav_button(VIEW_SETTINGS, "Settings")
        
        self._layout.addSpacerItem(
            QSpacerItem(
                20, 
                40, 
                QSizePolicy.Policy.Minimum, 
                QSizePolicy.Policy.Expanding
            )
        )

    def set_active_view(self, view_id: str) -> None:
        """Update the checked state of the rail to match external state changes."""
        for button in self._button_group.buttons():
            # We store view_id in the object name or property?
            # Or we iterate and match logic.
            # For simplicity, using objectName as view_id storage for now.
            if button.objectName() == view_id:
                button.setChecked(True)
                return
    
    def _add_nav_button(self, view_id: str, label: str) -> None:
        """Helper to create nav buttons."""
        btn = QPushButton(label[0]) # Icon placeholder (first letter)
        btn.setObjectName(view_id)
        btn.setToolTip(label)
        btn.setCheckable(True)
        btn.setFixedSize(40, 40)
        
        self._layout.addWidget(btn)
        self._button_group.addButton(btn)

    def _on_button_clicked(self, button: QAbstractButton) -> None:
        """Handle internal clicks and emit signal."""
        view_id = button.objectName()
        self.view_changed.emit(view_id)
