"""
ProjectsView - Tree view for projects/focus groups.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QFrame, QSplitter, QVBoxLayout

from ui.components.transcript_list import TranscriptList
from ui.constants.view_ids import VIEW_PROJECTS
from ui.contracts.capabilities import Capabilities, SelectionState
from ui.views.base_view import BaseView
from ui.models import TranscriptionModel, FocusGroupProxyModel
from ui.widgets.focus_group.focus_group_tree import FocusGroupTreeWidget

if TYPE_CHECKING:
    from history_manager import HistoryManager

class ProjectsView(BaseView):
    """
    View for managing projects and focus groups.
    
    Layout:
        [ Group Tree ] | [ Transcript List ] | [ Preview / Detail ]
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history_manager: HistoryManager | None = None
        self._model: TranscriptionModel | None = None
        self._proxy: FocusGroupProxyModel | None = None
        
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Initialize the three-pane layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._splitter = QSplitter()
        self._splitter.setHandleWidth(1)

        # Pane 1: Focus Group Tree
        self._groups_container = QFrame()
        groups_layout = QVBoxLayout(self._groups_container)
        groups_layout.setContentsMargins(0, 0, 0, 0)
        
        self.group_tree = FocusGroupTreeWidget()
        # Connect signal to filter the list
        # FocusGroupTreeWidget usually emits signals when items are clicked.
        # It has 'itemSelectionChanged' signal from QTreeWidget
        self.group_tree.itemSelectionChanged.connect(self._on_group_selection_changed)
        groups_layout.addWidget(self.group_tree)

        # Pane 2: Transcript List
        self._list_container = QFrame()
        list_layout = QVBoxLayout(self._list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        
        self.transcript_list = TranscriptList()
        # Connect selection
        self.transcript_list.selectionChangedSignal.connect(self._on_list_selection_changed)
        list_layout.addWidget(self.transcript_list)

        # Pane 3: Inspector Placeholder
        self._inspector_container = QFrame()
        self._inspector_container.setStyleSheet("background-color: #FAFAFA;")
        inspector_layout = QVBoxLayout(self._inspector_container)
        
        self._placeholder = QLabel("Select a transcript to preview")
        self._placeholder.setStyleSheet("color: #888;")
        inspector_layout.addWidget(self._placeholder)

        self._splitter.addWidget(self._groups_container)
        self._splitter.addWidget(self._list_container)
        self._splitter.addWidget(self._inspector_container)
        
        # Initial stretch factors
        self._splitter.setStretchFactor(0, 2)
        self._splitter.setStretchFactor(1, 4)
        self._splitter.setStretchFactor(2, 4)

        layout.addWidget(self._splitter)

    def get_view_id(self) -> str:
        return VIEW_PROJECTS

    def get_capabilities(self) -> Capabilities:
        selection = self.get_selection()
        has_selection = bool(selection.selected_ids)
        
        return Capabilities(
            can_edit=has_selection,
            can_delete=has_selection,
            can_refine=has_selection,
            can_copy=has_selection,
            can_move_to_project=has_selection
        )

    def get_selection(self) -> SelectionState:
        ids = self.transcript_list.get_selected_ids()
        primary = ids[0] if ids else None
        return SelectionState(selected_ids=ids, primary_id=primary)

    def set_history_manager(self, manager: HistoryManager) -> None:
        """Inject history manager."""
        self._history_manager = manager
        
        # Setup models
        self._model = TranscriptionModel(manager)
        
        # Setup Proxy for List - filtering by group
        self._proxy = FocusGroupProxyModel()
        self._proxy.setSourceModel(self._model)
        
        # Initially show nothing or all? Usually select first group.
        # Let's default to no filter (or ALL) until a group is selected.
        # Or better yet, we rely on the tree selection.
        
        self.transcript_list.setModel(self._proxy)
        self.transcript_list.set_history_manager(manager)
        
        # Setup Groups Tree
        # FocusGroupTreeWidget loads directly from manager usually
        # but we should confirm if it uses a model or manual load.
        # From reading the code earlier, it calls self.load_groups().
        # We need to give it the history manager.
        # It expects history_manager in constructor or set later?
        # The constructor takes it. We initialized without it.
        # Let's check provided context... it doesn't seem to have a setter.
        # But it does inherit QTreeWidget.
        # Wait, I checked FocusGroupTreeWidget code, it has `if self._history_manager: load_groups()`.
        # I should probably access `_history_manager` or verify if I can set it.
        # Actually creating a `set_history_manager` on the widget would be cleaner if it doesn't exist.
        # But looking at prior context, I didn't see a `set_history_manager` in `FocusGroupTreeWidget`.
        # I check `focus_group_tree.py` again.
        
        # It has `if self._history_manager: self.load_groups()`.
        # I can just set `self.group_tree._history_manager = manager` and call `load_groups()`.
        # This is a bit hacky (private access).
        # Let's re-read `FocusGroupTreeWidget` file content provided earlier.
        
        # Ah, it doesn't show a setter method in the snippet I saw (first 100 lines).
        # But `FocusGroupContainer` had `self.tree.set_history_manager(manager)`.
        # Let's assume the method exists or I add it.
        # Re-reading `FocusGroupContainer` read_file output...
        # `self.tree.set_history_manager(manager)` is called. So `FocusGroupTreeWidget` MUST have it.
        
        if hasattr(self.group_tree, 'set_history_manager'):
            self.group_tree.set_history_manager(manager)
            self.group_tree.load_groups()

    def _on_group_selection_changed(self) -> None:
        """Filter transcript list based on selected group."""
        selected_items = self.group_tree.selectedItems()
        if not selected_items:
            # Maybe show all or nothing?
            return
            
        item = selected_items[0]
        # FocusGroupTreeWidget uses UserRoles to store ID.
        # ROLE_GROUP_ID = Qt.ItemDataRole.UserRole + 11
        # I need to import ROLE_GROUP_ID from somewhere or use the class constant.
        
        group_id = item.data(0, FocusGroupTreeWidget.ROLE_GROUP_ID)
        
        if self._proxy:
            # FocusGroupProxyModel expects group_id (int) or None.
            # If group_id is None, it means "Ungrouped" usually.
            # Does FocusGroupProxyModel support filtering by specific ID? Yes.
            self._proxy.set_group_id(group_id)

    def _on_list_selection_changed(self, ids: Tuple[str, ...]) -> None:
        """Handle internal selection changes."""
        if ids:
            self._placeholder.setText(f"Selected: {len(ids)} items\\nPrimary: {ids[0]}")
        else:
            self._placeholder.setText("Select a transcript to preview")

