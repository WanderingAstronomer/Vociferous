"""
HistoryView - Read-only navigation of past transcripts.
"""
# Force update: 2026-01-14

from __future__ import annotations

from typing import TYPE_CHECKING


from PyQt6.QtCore import pyqtSlot, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QFrame, QVBoxLayout

from ui.components.shared import HistoryList, ContentPanel
from ui.constants.view_ids import VIEW_HISTORY
from ui.contracts.capabilities import Capabilities, SelectionState, ActionId
from ui.views.base_view import BaseView
from ui.models import TranscriptionModel, ProjectProxyModel

if TYPE_CHECKING:
    from database.history_manager import HistoryManager


class HistoryView(BaseView):
    """
    View for browsing transcript history.

    Layout:
        [ History List ] | [ Content Panel ]
    """

    editRequested = pyqtSignal(int)
    deleteRequested = pyqtSignal(int)
    refineRequested = pyqtSignal(int)
    dataChanged = pyqtSignal()  # For propagating changes to MainWindow

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
        layout.setSpacing(1)  # Minimal gap between panes

        # Left Pane: History List
        self._list_container = QFrame()
        self._list_container.setObjectName("historyListPane")
        self._list_container.setFrameShape(QFrame.Shape.NoFrame)
        list_layout = QVBoxLayout(self._list_container)
        # Top margin matches icon rail (28px) for visual alignment
        list_layout.setContentsMargins(0, 28, 0, 0)

        self.history_list = HistoryList()
        # Signals: selectionChanged emits tuple[int, ...]
        self.history_list.selectionChanged.connect(self._on_selection_changed)
        self.history_list.historyContentChanged.connect(self.dataChanged.emit)
        list_layout.addWidget(self.history_list)

        # Right Pane: Content Panel
        self._content_container = QFrame()
        self._content_container.setObjectName("contentPanelContainer")
        self._content_container.setFrameShape(QFrame.Shape.NoFrame)

        self._setup_content_panel()

        # Add to main layout (no splitter for crisp appearance)
        layout.addWidget(self._list_container, 4)
        layout.addWidget(self._content_container, 6)

    def _setup_content_panel(self) -> None:
        """Build the detail display surface."""
        layout = QVBoxLayout(self._content_container)
        # Margins: top=30, left=20, right=10, bottom=10
        layout.setContentsMargins(20, 30, 10, 10)

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

        elif action_id == ActionId.DELETE:
            self.deleteRequested.emit(transcript_id)

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
        from core.config_manager import ConfigManager

        selection = self.get_selection()
        has_selection = bool(selection.selected_ids)
        refinement_enabled = ConfigManager.get_config_value("refinement", "enabled")

        return Capabilities(
            can_edit=has_selection,
            can_delete=has_selection,
            can_refine=has_selection and refinement_enabled,
            can_copy=has_selection,
            can_move_to_project=has_selection,
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
