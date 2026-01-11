"""
SidebarTabBar - Tab switcher for sidebar views.

Provides segmented control with three tabs:
- Focus Groups (projects/archives)
- Transcripts (recent 7 days)
- Search (magnifying glass icon)
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from ui.constants import Colors, Spacing, Typography


class SidebarTabBar(QWidget):
    """
    Segmented control for switching between sidebar views.
    
    Tabs:
        0 - Focus Groups
        1 - Transcripts (Recent)
        2 - Search
    
    Signals:
        tabChanged(int): Emitted when active tab changes
    """
    
    tabChanged = pyqtSignal(int)
    
    # Tab indices
    TAB_GROUPS = 0
    TAB_TRANSCRIPTS = 1
    TAB_SEARCH = 2
    
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebarTabBar")
        self._buttons: list[QPushButton] = []
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        
        self._setup_ui()
        self._apply_styles()
        
    def _setup_ui(self) -> None:
        """Create tab bar layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, Spacing.MINOR_GAP)
        layout.setSpacing(0)
        
        # Focus Groups tab
        groups_btn = self._create_tab_button("Focus Groups", self.TAB_GROUPS)
        layout.addWidget(groups_btn, 1)
        
        # Transcripts tab
        transcripts_btn = self._create_tab_button("Recent", self.TAB_TRANSCRIPTS)
        transcripts_btn.setChecked(True)  # Default active
        layout.addWidget(transcripts_btn, 1)
        
        # Search tab (icon only)
        search_btn = self._create_search_button()
        layout.addWidget(search_btn, 0)
        
    def _create_tab_button(self, text: str, tab_id: int) -> QPushButton:
        """Create a text tab button."""
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setObjectName(f"sidebarTab_{tab_id}")
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.setFixedHeight(44)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        self._button_group.addButton(btn, tab_id)
        self._buttons.append(btn)
        btn.clicked.connect(lambda: self._on_tab_clicked(tab_id))
        
        return btn
    
    def _create_search_button(self) -> QPushButton:
        """Create the search icon button."""
        btn = QPushButton()
        btn.setCheckable(True)
        btn.setObjectName("sidebarTabSearch")
        btn.setFixedSize(52, 44)  # Match height of other tabs
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        # Try to load search icon, fallback to text
        icon_path = Path(__file__).parent.parent.parent.parent.parent / "icons" / "search.svg"
        if icon_path.exists():
            btn.setIcon(QIcon(str(icon_path)))
            btn.setIconSize(QSize(48, 48))
        else:
            btn.setText("🔍")
        
        self._button_group.addButton(btn, self.TAB_SEARCH)
        self._buttons.append(btn)
        btn.clicked.connect(lambda: self._on_tab_clicked(self.TAB_SEARCH))
        
        return btn
    
    def _on_tab_clicked(self, tab_id: int) -> None:
        """Handle tab button click."""
        self.tabChanged.emit(tab_id)
    
    def _apply_styles(self) -> None:
        """Apply segmented control styling."""
        self.setStyleSheet(f"""
            #sidebarTabBar {{
                background: transparent;
            }}
            
            #sidebarTabBar QPushButton {{
                background: {Colors.SURFACE_ALT};
                color: {Colors.TEXT_SECONDARY};
                border: none;
                font-size: {Typography.BODY_SIZE}pt;
                font-weight: 700;
                padding: 10px 24px;
                white-space: normal;
            }}
            
            #sidebarTabBar QPushButton:first-child {{
                border-top-left-radius: 6px;
                border-bottom-left-radius: 6px;
            }}
            
            #sidebarTabBar QPushButton:hover {{
                background: {Colors.SURFACE};
                color: {Colors.TEXT_PRIMARY};
            }}
            
            #sidebarTabBar QPushButton:checked {{
                background: {Colors.PRIMARY};
                color: {Colors.TEXT_ON_PRIMARY};
            }}
            
            #sidebarTabBar #sidebarTabSearch:checked {{
                background: {Colors.BACKGROUND};
                color: {Colors.TEXT_SECONDARY};
            }}
            
            #sidebarTabSearch {{
                background: transparent;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                padding: 8px;
            }}
        """)
    
    def current_tab(self) -> int:
        """Return currently active tab index."""
        return self._button_group.checkedId()
    
    def set_tab(self, tab_id: int) -> None:
        """Programmatically switch to a tab."""
        btn = self._button_group.button(tab_id)
        if btn:
            btn.setChecked(True)
            self.tabChanged.emit(tab_id)
