"""
HistoryView - Read-only navigation of past transcripts.
"""
# Force update: 2026-01-14

from __future__ import annotations

from typing import TYPE_CHECKING


from PyQt6.QtCore import pyqtSlot, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout, 
    QFrame, 
    QVBoxLayout
)

from ui.components.history_list import HistoryList
from ui.components.content_panel import ContentPanel
from ui.constants import Colors
from ui.constants.view_ids import VIEW_HISTORY
from ui.contracts.capabilities import Capabilities, SelectionState, ActionId
from ui.views.base_view import BaseView
from ui.models import TranscriptionModel, ProjectProxyModel

if TYPE_CHECKING:
    from history_manager import HistoryManager

class HistoryView(BaseView):
    """
    View for browsing transcript history.
    
    Layout:
        [ History List ] | [ Content Panel ]
    """

    editRequested = pyqtSignal(int)
    refineRequested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history_manager: HistoryManager | None = None
        self._model: TranscriptionModel | None = None
        self._proxy: ProjectProxyModel | None = None
        
        self._setup_ui()

    def refresh(self) -> None:
        """Reload the model state."""
        if self._model:
            self._model.refresh_from_manager()

    def _setup_ui(self) -> None:
        """Initialize the master-detail layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        pane_style = (
            f"background-color: {Colors.SURFACE}; "
            f"border: 1px solid {Colors.BORDER_DEFAULT};"
        )

        # Left Pane: History List
        self._list_container = QFrame()
        self._list_container.setStyleSheet(pane_style)
        list_layout = QVBoxLayout(self._list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        
        self.history_list = HistoryList()
        # Signals: selectionChangedSignal emits tuple[int, ...]
        self.history_list.selectionChangedSignal.connect(self._on_selection_changed)
        list_layout.addWidget(self.history_list)

        # Right Pane: Content Panel
        self._content_container = QFrame()
        self._content_container.setStyleSheet(pane_style)
        
        self._setup_content_panel()

        # Add to main layout (no splitter)
        layout.addWidget(self._list_container, 4)
        layout.addWidget(self._content_container, 6)
        
    def _setup_content_panel(self) -> None:
        """Build the detail display surface."""
        layout = QVBoxLayout(self._content_container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.content_panel = ContentPanel()
        layout.addWidget(self.content_panel)

    @pyqtSlot(tuple)
    def _on_selection_changed(self, selected_ids: tuple[int, ...]) -> None:
        """Handle selection update from list."""
        # Notify BaseView -> ActionDock
        self.capabilitiesChanged.emit()

        if not selected_ids:
            self.content_panel.clear()
            return

        # Single selection support for now
        try:
            primary_id = selected_ids[0]
            self._display_entry(primary_id)
        except (ValueError, IndexError):
            pass

    def _display_entry(self, entry_id: int) -> None:
        """Fetch and display entry details."""
        if not self._history_manager:
            return
            
        entry = self._history_manager.get_entry(entry_id)
        self.content_panel.set_entry(entry)

    def dispatch_action(self, action_id: ActionId) -> None:
        """Handle actions from ActionDock."""
        selection = self.get_selection()
        if not selection.has_selection or selection.primary_id is None:
            return
        
        transcript_id = selection.primary_id

        if action_id == ActionId.EDIT:
            self.editRequested.emit(transcript_id)
            
        elif action_id == ActionId.REFINE:
            self.refineRequested.emit(transcript_id)
            
        elif action_id == ActionId.COPY:
            entry = self._history_manager.get_entry(transcript_id)
            if entry:
                from ui.utils.clipboard_utils import copy_text
                copy_text(entry.text)

    def get_view_id(self) -> str:
        return VIEW_HISTORY

    def get_capabilities(self) -> Capabilities:
        """Return capabilities based on current selection."""
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
        """Return current selection from the list."""
        ids = self.history_list.get_selected_ids()
        primary = ids[0] if ids else None
        return SelectionState(selected_ids=ids, primary_id=primary)

    def set_history_manager(self, manager: HistoryManager) -> None:
        """Inject history manager and setup models."""
        self._history_manager = manager
        
        # Create models
        self._model = TranscriptionModel(manager)
        
        self.history_list.setModel(self._model)
        self.history_list.set_history_manager(manager)
