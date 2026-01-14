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

from pathlib import Path
from typing import Final, TYPE_CHECKING

if TYPE_CHECKING:
    pass

from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QAbstractButton,
    QButtonGroup,
    QFrame,
)

from ui.constants.view_ids import (
    VIEW_TRANSCRIBE,
    VIEW_HISTORY,
    VIEW_PROJECTS,
    VIEW_SEARCH,
    VIEW_REFINE,
    VIEW_SETTINGS,
    VIEW_USER,
)
from ui.interaction.intents import InteractionIntent, NavigateIntent, IntentSource
from utils import ConfigManager


# Rail constants
RAIL_WIDTH: Final = 64
BUTTON_SIZE: Final = 48
ICONS_DIR: Final = Path(__file__).parents[3] / "icons"


class RailButton(QPushButton):
    """
    Circular navigation button with blink capability.
    
    Enforces Invariant 7.4 (Active indication) via Checkable state.
    Enforces Invariant 7.5 (View Switch Blink) via blink() method.
    """
    
    blinkFinished = pyqtSignal()
    
    def __init__(self, view_id: str, icon_name: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view_id = view_id
        
        icon_path = ICONS_DIR / f"{icon_name}.svg"
        self.setIcon(QIcon(str(icon_path)))
        self.setIconSize(QSize(24, 24))
        
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
        self.blinkFinished.emit()


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
        # View defs: ID, IconName, Tooltip
        views = [
            (VIEW_TRANSCRIBE, "rail_icon-transcribe_view", "Transcribe"),
            (VIEW_HISTORY, "rail_icon-history_view", "History"),
            (VIEW_PROJECTS, "rail_icon-projects_view", "Projects"),
            (VIEW_SEARCH, "rail_icon-search_view", "Search"),
        ]
        
        # Conditionally add Refine view based on config
        refinement_enabled = ConfigManager.get_config_value("refinement", "enabled")
        if refinement_enabled:
            views.append((VIEW_REFINE, "rail_icon-refine_view", "Refine"))
        
        for vid, icon_name, label in views:
            btn = RailButton(vid, icon_name, label)
            self._layout.addWidget(btn)
            self._button_group.addButton(btn)

    def _build_footer(self) -> None:
        """Add global affordances to the bottom of the rail (User and Settings)."""
        # Visual separator before bottom cluster
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setObjectName("rail_separator")
        separator.setFixedHeight(1)
        self._layout.addWidget(separator)
        
        # User (above Settings)
        user_btn = RailButton(VIEW_USER, "rail_icon-profile_view", "User")
        self._layout.addWidget(user_btn)
        self._button_group.addButton(user_btn)
        
        # Settings
        settings_btn = RailButton(VIEW_SETTINGS, "rail_icon-settings_view", "Settings")
        self._layout.addWidget(settings_btn)
        self._button_group.addButton(settings_btn)

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

    def get_active_view_id(self) -> str | None:
        """Retrieve the currently active view ID, or None if no rail item is active."""
        btn = self._button_group.checkedButton()
        if isinstance(btn, RailButton):
            return btn.view_id
        return None

    def _on_button_clicked(self, button: QAbstractButton) -> None:
        """Propagate intent."""
        if isinstance(button, RailButton):
            intent = NavigateIntent(
                source=IntentSource.ICON_RAIL,
                target_view_id=button.view_id
            )
            self.intent_emitted.emit(intent)
