"""
Icon Rail Surface Owner.

Manages the persistent navigation rail, containing only navigation icons.
Enforces Invariants:
- 1.1 Single Ownership: Owns the rail widgets.
- 7.1 Purpose: Navigation only, no content.
- 7.2 Canonical Composition: Icons only, optional separators.
- 7.5 View Switch Blink Signal: Single blink on active view change.
"""

from __future__ import annotations

from typing import Final, TYPE_CHECKING

if TYPE_CHECKING:
    pass

from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QAbstractButton,
    QButtonGroup,
)

from ui.constants.view_ids import (
    VIEW_TRANSCRIBE,
    VIEW_RECENT,
    VIEW_PROJECTS,
    VIEW_SEARCH,
    VIEW_REFINE,
    VIEW_SETTINGS,
)
from ui.interaction.intents import InteractionIntent, NavigateIntent, IntentSource


# Rail constants
RAIL_WIDTH: Final = 64
BUTTON_SIZE: Final = 48


class RailButton(QPushButton):
    """
    Circular navigation button with blink capability.
    
    Enforces Invariant 7.4 (Active indication) via Checkable state.
    Enforces Invariant 7.5 (View Switch Blink) via blink() method.
    """
    
    def __init__(self, view_id: str, icon_char: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view_id = view_id
        self.setText(icon_char) 
        self.setToolTip(label)
        self.setCheckable(True)
        self.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        self.setObjectName("rail_button")
        
        # Ensure we don't have hardcoded styles here; relies on unified_stylesheet
        
    def blink(self) -> None:
        """Trigger a single visual blink."""
        # Set dynamic property for styling
        self.setProperty("blink", "active")
        self.style().polish(self)
        
        # Reset after 200ms (token candidate)
        QTimer.singleShot(200, self._reset_blink)

    def _reset_blink(self) -> None:
        self.setProperty("blink", "inactive")
        self.style().polish(self)


class IconRail(QWidget):
    """
    Vertical navigation rail.
    
    Signals:
        intent_emitted(InteractionIntent): Emitted when navigation is requested.
    """
    
    intent_emitted = pyqtSignal(InteractionIntent)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("icon_rail")
        self.setFixedWidth(RAIL_WIDTH)
        
        # Layout
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 8, 0, 8)
        self._layout.setSpacing(8)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        self._button_group.buttonClicked.connect(self._on_button_clicked)
        
        # Build Inventory (Strictly Icons)
        self._build_inventory()
        
        self._layout.addStretch()
        
        # Bottom Inventory (Global Affordances)
        self._build_footer()

    def _build_inventory(self) -> None:
        """Construct the rail buttons based on canonical view list."""
        # View defs: ID, IconChar (Placeholder), Tooltip
        views = [
            (VIEW_TRANSCRIBE, "T", "Transcribe"),
            (VIEW_RECENT, "H", "History"),
            (VIEW_PROJECTS, "P", "Projects"),
            (VIEW_SEARCH, "S", "Search"),
            (VIEW_REFINE, "R", "Refine"),
        ]
        
        for vid, char, label in views:
            btn = RailButton(vid, char, label)
            self._layout.addWidget(btn)
            self._button_group.addButton(btn)

    def _build_footer(self) -> None:
        """Add global affordances to the bottom of the rail."""
        # Settings
        # Using a gear unicode or simple text
        btn = RailButton(VIEW_SETTINGS, "⚙", "Settings")
        self._layout.addWidget(btn)
        self._button_group.addButton(btn)

    def set_active_view(self, view_id: str) -> None:
        """
        Update the visual state to reflect the active view.
        Triggers a blink on the target icon (Invariant 7.5).
        """
        found = False
        for button in self._button_group.buttons():
            if isinstance(button, RailButton) and button.view_id == view_id:
                if not button.isChecked():
                    button.setChecked(True)
                    button.blink()
                found = True
            elif button.isChecked():
                 pass
        
        if not found:
            # Deselect all if view is not on rail (e.g. Settings, Edit)
            temp = self._button_group.exclusive()
            self._button_group.setExclusive(False)
            for btn in self._button_group.buttons():
                btn.setChecked(False)
            self._button_group.setExclusive(temp)

    def _on_button_clicked(self, button: QAbstractButton) -> None:
        """Propagate intent."""
        if isinstance(button, RailButton):
            intent = NavigateIntent(
                source=IntentSource.ICON_RAIL,
                target_view_id=button.view_id
            )
            self.intent_emitted.emit(intent)
