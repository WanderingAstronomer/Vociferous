"""
SidebarWidget - Main sidebar component with tabbed navigation.

Tab Views:
- Focus Groups: Project/archive folders with nesting
- Transcripts: Recent 7 days of history
- Search: Full-text search across all history

Uses shared TranscriptionModel as single source of truth for all views.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.constants import Colors, Spacing, Typography
from ui.models import TranscriptionModel
from ui.widgets.focus_group import FocusGroupContainer

from ui.components.sidebar.resize_grip import SidebarResizeGrip
from ui.components.sidebar.search_panel import SearchPanel
from ui.components.sidebar.sidebar_tab_bar import SidebarTabBar
from ui.components.sidebar.transcript_tree import TranscriptTreeView

if TYPE_CHECKING:
    from history_manager import HistoryEntry, HistoryManager


class SidebarWidget(QWidget):
    """
    Main sidebar widget with tabbed navigation.
    
    Tabs:
        0 - Focus Groups: Project organization
        1 - Transcripts: Recent 7 days 
        2 - Search: Full-text search
    
    Signals:
        entrySelected(str, str): Emitted when entry is selected (text, timestamp)
        resizeRequested(int): Emitted when resize grip is dragged
        collapseRequested(): Emitted when sidebar collapse is requested
        expandRequested(int): Emitted when sidebar expand is requested
    """

    entrySelected = pyqtSignal(str, str)  # text, timestamp
    resizeRequested = pyqtSignal(int)  # new width
    collapseRequested = pyqtSignal()
    expandRequested = pyqtSignal(int)  # target width

    def __init__(
        self,
        history_manager: HistoryManager | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setAutoFillBackground(True)
        self._history_manager = history_manager
        
        # Create shared model (single source of truth)
        self._model: TranscriptionModel | None = None
        if history_manager:
            self._model = TranscriptionModel(history_manager)

        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self) -> None:
        """Create sidebar layout with tabs and stacked views."""
        # Main horizontal layout: content + resize grip
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Content container
        self.content = QWidget()
        self.content.setObjectName("sidebarContent")
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(
            Spacing.SIDEBAR_SIDE,
            Spacing.SIDEBAR_TOP,
            0,  # No right margin (grip handles that)
            Spacing.SIDEBAR_BOTTOM,
        )
        content_layout.setSpacing(0)

        # Tab bar at top
        self._tab_bar = SidebarTabBar()
        content_layout.addWidget(self._tab_bar)

        # Stacked widget for tab content
        self._stack = QStackedWidget()
        self._stack.setObjectName("sidebarStack")
        
        # Page 0: Focus Groups
        self._groups_page = self._create_groups_page()
        self._stack.addWidget(self._groups_page)
        
        # Page 1: Transcripts (Recent)
        self._transcripts_page = self._create_transcripts_page()
        self._stack.addWidget(self._transcripts_page)
        
        # Page 2: Search
        self._search_page = SearchPanel(self._history_manager)
        self._search_page.entrySelected.connect(self.entrySelected)
        self._stack.addWidget(self._search_page)
        
        content_layout.addWidget(self._stack, 1)
        
        outer_layout.addWidget(self.content, 1)

        # Resize grip on right edge
        self._resize_grip = SidebarResizeGrip(self)
        outer_layout.addWidget(self._resize_grip, 0)
        
    def _create_groups_page(self) -> QWidget:
        """Create the Focus Groups tab content."""
        page = QWidget()
        page.setObjectName("groupsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, Spacing.MINOR_GAP, Spacing.SIDEBAR_SIDE, 0)
        layout.setSpacing(Spacing.MINOR_GAP)
        
        # "Create New Focus Group" button with dashed border styling
        self._create_group_btn = QPushButton("+ Create New Focus Group")
        self._create_group_btn.setObjectName("createGroupBtn")
        self._create_group_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._create_group_btn.clicked.connect(self._on_create_group_clicked)
        self._create_group_btn.setStyleSheet(f"""
            QPushButton#createGroupBtn {{
                background-color: {Colors.BG_TERTIARY};
                color: {Colors.TEXT_SECONDARY};
                border: 2px dashed {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                padding: 16px;
                font-size: {Typography.SMALL_SIZE}pt;
                font-weight: 500;
            }}
            QPushButton#createGroupBtn:hover {{
                border-color: {Colors.PRIMARY};
                color: {Colors.TEXT_PRIMARY};
                background-color: {Colors.HOVER_BG_ITEM};
            }}
            QPushButton#createGroupBtn:pressed {{
                background-color: {Colors.BG_SECONDARY};
            }}
        """)
        layout.addWidget(self._create_group_btn)
        
        # Focus Groups tree (no collapsible wrapper)
        self.focus_groups = FocusGroupContainer(self._history_manager)
        self.focus_groups.entrySelected.connect(self.entrySelected)
        
        if self._model:
            self._model.entryDeleted.connect(lambda _: self.focus_groups.load_groups())
            self._model.entryAdded.connect(lambda _: self.focus_groups.load_groups())
            self._model.entryUpdated.connect(lambda _: self.focus_groups.load_groups())
        
        self.focus_groups.groupDeleted.connect(self._on_group_deleted)
        self.focus_groups.groupRenamed.connect(self._on_group_metadata_changed)
        self.focus_groups.groupColorChanged.connect(self._on_group_metadata_changed)
        self.focus_groups.groupCreated.connect(self._on_group_metadata_changed)
        
        layout.addWidget(self.focus_groups, 1)
        
        return page
    
    def _create_transcripts_page(self) -> QWidget:
        """Create the Transcripts (Recent) tab content."""
        page = QWidget()
        page.setObjectName("transcriptsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, Spacing.MINOR_GAP, Spacing.SIDEBAR_SIDE, 0)
        layout.setSpacing(0)
        
        # Transcript tree directly (no collapsible wrapper - tab indicates content)
        self.transcript_list = TranscriptTreeView()
        if self._model:
            self.transcript_list.set_source_model(self._model)
        if self._history_manager:
            self.transcript_list.set_history_manager(self._history_manager)
        
        self.transcript_list.entrySelected.connect(self.entrySelected)
        self.transcript_list.entryGroupChanged.connect(self._on_entry_group_changed)
        
        layout.addWidget(self.transcript_list, 1)
        
        return page
    
    def _setup_connections(self) -> None:
        """Connect signals."""
        # Tab switching
        self._tab_bar.tabChanged.connect(self._on_tab_changed)
        
        # Resize grip
        self._resize_grip.resized.connect(self.resizeRequested)
        self._resize_grip.collapseRequested.connect(self.collapseRequested)
        self._resize_grip.expandRequested.connect(self.expandRequested)
    
    def _on_tab_changed(self, tab_id: int) -> None:
        """Handle tab switch."""
        self._stack.setCurrentIndex(tab_id)
        
        # Focus search input when switching to search tab
        if tab_id == SidebarTabBar.TAB_SEARCH:
            self._search_page.focus_search()
    
    def _on_create_group_clicked(self) -> None:
        """Handle create group button click."""
        self.focus_groups.create_new_group()

    def _on_group_metadata_changed(self, *args) -> None:
        """Refresh group color metadata."""
        if self._model:
            self._model.refresh_group_colors()

    def _on_group_deleted(self, *args) -> None:
        """Reload model when group is deleted."""
        if self._model:
            self._model.refresh_from_manager()

    def _on_entry_group_changed(self, *args) -> None:
        """Refresh focus group tree when entries move."""
        self.focus_groups.load_groups()

    # === Public API ===
    
    def get_model(self) -> TranscriptionModel | None:
        """Get the shared transcription model."""
        return self._model

    def get_collapse_state(self) -> dict[str, bool]:
        """Return collapsed state for persistence."""
        return {
            "current_tab": self._tab_bar.current_tab(),
        }

    def set_collapse_state(self, state: dict) -> None:
        """Restore collapsed state from settings."""
        if not isinstance(state, dict):
            return
            
        # Restore current tab (default to Groups)
        current_tab = state.get("current_tab", 0)
        if isinstance(current_tab, int) and 0 <= current_tab <= 2:
            self._tab_bar.set_tab(current_tab)

    def set_history_manager(self, manager: HistoryManager) -> None:
        """Set history manager for all components."""
        self._history_manager = manager

        if not self._model:
            self._model = TranscriptionModel(manager)
            if hasattr(self, "transcript_list"):
                self.transcript_list.set_source_model(self._model)

        self.focus_groups.set_history_manager(manager)
        self.transcript_list.set_history_manager(manager)
        self._search_page.set_history_manager(manager)

    def focus_transcript_list(self) -> None:
        """Set keyboard focus to the transcript list."""
        self._tab_bar.set_tab(SidebarTabBar.TAB_TRANSCRIPTS)
        self.transcript_list.setFocus()

    def add_entry(self, entry: HistoryEntry) -> None:
        """Add a new transcript entry to the model."""
        if self._model:
            self._model.add_entry(entry)

    def entry_count(self) -> int:
        """Return count of ungrouped transcripts."""
        return self.transcript_list.entry_count()

    def load_history(self) -> None:
        """Reload model and focus groups."""
        if self._model:
            self._model.refresh_from_manager()
        self.focus_groups.load_groups()
        
    def current_tab(self) -> int:
        """Return current active tab index."""
        return self._tab_bar.current_tab()
    
    def set_tab(self, tab_id: int) -> None:
        """Switch to specified tab."""
        self._tab_bar.set_tab(tab_id)

    # Legacy compatibility - keeping old method names
    def toggle(self) -> None:
        """Request sidebar collapse/expand."""
        self.collapseRequested.emit()
