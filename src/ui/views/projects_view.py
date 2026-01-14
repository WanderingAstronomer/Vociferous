"""
ProjectsView - Tree view for projects/focus groups.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

from PyQt6.QtWidgets import QHBoxLayout, QFrame, QSplitter, QVBoxLayout

from ui.components.transcript_list import TranscriptList
from ui.components.transcript_inspector import TranscriptInspector
from ui.constants import Colors
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
        """Initialize the master-detail layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        pane_style = (
            f"background-color: {Colors.SURFACE}; "
            f"border: 1px solid {Colors.BORDER_DEFAULT};"
        )

        # Pane 1: Focus Group Tree (Master)
        self._groups_container = QFrame()
        self._groups_container.setStyleSheet(pane_style)
        groups_layout = QVBoxLayout(self._groups_container)
        groups_layout.setContentsMargins(0, 0, 0, 0)
        
        self.group_tree = FocusGroupTreeWidget()
        self.group_tree.entrySelected.connect(self._on_entry_selected)
        self.group_tree.itemSelectionChanged.connect(self._on_selection_changed)
        groups_layout.addWidget(self.group_tree)

        # Pane 2: Inspector (Detail)
        self._inspector_container = QFrame()
        self._inspector_container.setStyleSheet(pane_style)
        inspector_layout = QVBoxLayout(self._inspector_container)
        inspector_layout.setContentsMargins(0, 0, 0, 0)
        
        self.inspector = TranscriptInspector()
        inspector_layout.addWidget(self.inspector)

        # Add to layout
        layout.addWidget(self._groups_container, 4)
        layout.addWidget(self._inspector_container, 6)

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
        if not hasattr(self, 'group_tree') or not self.group_tree:
             return SelectionState()
             
        items = self.group_tree.selectedItems()
        if not items:
            return SelectionState()
            
        item = items[0]
        # Check if it is a transcript item (not a group)
        is_group = item.data(0, FocusGroupTreeWidget.ROLE_IS_GROUP)
        if is_group:
            return SelectionState()
            
        # Get timestamp
        from ui.widgets.transcript_item import ROLE_TIMESTAMP_ISO
        timestamp = item.data(0, ROLE_TIMESTAMP_ISO)
        
        if timestamp and self._history_manager:
            t_id = self._history_manager.get_id_by_timestamp(timestamp)
            if t_id is not None:
                return SelectionState(selected_ids=(t_id,), primary_id=t_id)
        
        return SelectionState()

    def set_history_manager(self, manager: HistoryManager) -> None:
        """Inject history manager."""
        self._history_manager = manager
        if hasattr(self.group_tree, 'set_history_manager'):
            self.group_tree.set_history_manager(manager)
        if hasattr(self.group_tree, 'load_groups'):
            self.group_tree.load_groups()

    def _on_entry_selected(self, text: str, timestamp: str) -> None:
        """Handle execution of a transcript selection from tree signal."""
        # Update inspector
        if self._history_manager and timestamp:
             t_id = self._history_manager.get_id_by_timestamp(timestamp)
             if t_id:
                 entry = self._history_manager.get_entry(t_id)
                 self.inspector.set_entry(entry)
        
        self.capabilitiesChanged.emit()

    def _on_selection_changed(self) -> None:
        """Handle generic selection change (e.g. clicking a group or transcript)."""
        # Start by notifying change
        self.capabilitiesChanged.emit()
        
        # Inspector update logic
        sel = self.get_selection()
        if sel.primary_id:
            if self._history_manager:
                 entry = self._history_manager.get_entry(sel.primary_id)
                 self.inspector.set_entry(entry)
        else:
            self.inspector.clear()

    def dispatch_action(self, action_id: ActionId) -> None:
        selection = self.get_selection()
        if not selection.has_selection or not selection.primary_id:
            return

        transcript_id = selection.primary_id

        if action_id == ActionId.EDIT:
            self.editRequested.emit(transcript_id)
        elif action_id == ActionId.REFINE:
            self.refineRequested.emit(transcript_id)
        elif action_id == ActionId.COPY:
             if self._history_manager:
                entry = self._history_manager.get_entry(transcript_id)
                if entry:
                    from ui.utils.clipboard_utils import copy_text
                    copy_text(entry.text)
