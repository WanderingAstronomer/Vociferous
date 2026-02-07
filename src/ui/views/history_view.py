"""
HistoryView - Read-only navigation of past transcripts.
"""
# Force update: 2026-01-14

from __future__ import annotations

from typing import TYPE_CHECKING


from PyQt6.QtCore import pyqtSlot, pyqtSignal, Qt
from PyQt6.QtWidgets import QHBoxLayout, QFrame, QVBoxLayout, QWidget, QLabel

from src.database.signal_bridge import DatabaseSignalBridge
from src.database.events import ChangeAction, EntityChange
from src.ui.components.shared import HistoryList, ContentPanel
from src.ui.constants.view_ids import VIEW_HISTORY
from src.ui.contracts.capabilities import Capabilities, SelectionState, ActionId
from src.ui.views.base_view import BaseView
from src.ui.models import TranscriptionModel, ProjectProxyModel
import src.ui.constants.colors as c
from src.ui.constants import Spacing, Typography

if TYPE_CHECKING:
    from src.database.history_manager import HistoryManager, HistoryEntry


class HistoryView(BaseView):
    """
    View for browsing transcript history.

    Layout:
        [ History List ] | [ Content Panel ]
    """

    edit_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(list)  # Unified multi-delete
    refine_requested = pyqtSignal(int)
    data_changed = pyqtSignal()  # For propagating changes to MainWindow

    def cleanup(self) -> None:
        """Disconnect global signals."""
        try:
            DatabaseSignalBridge().data_changed.disconnect(self._handle_data_changed)
        except (TypeError, RuntimeError):
            pass
        super().cleanup()

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
        self.content_panel.clear()

    def add_entry(self, entry: HistoryEntry) -> None:
        """Add a single entry to the model (more efficient than refresh)."""
        if self._model:
            self._model.add_entry(entry)

    def _setup_ui(self) -> None:
        """Initialize the master-detail layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Title Bar
        title_bar = self._create_title_bar()
        main_layout.addWidget(title_bar)

        # Content Container
        content_container = QWidget()
        layout = QHBoxLayout(content_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)  # Minimal gap between panes

        # Left Pane: History List
        self._list_container = QFrame()
        self._list_container.setObjectName("historyListPane")
        self._list_container.setFrameShape(QFrame.Shape.NoFrame)
        list_layout = QVBoxLayout(self._list_container)
        # No top margin needed - title bar provides spacing
        list_layout.setContentsMargins(0, 0, 0, 0)

        self.history_list = HistoryList()
        # Signals: selectionChanged emits tuple[int, ...]
        self.history_list.selection_changed.connect(self._on_selection_changed)
        self.history_list.history_content_changed.connect(self.data_changed.emit)
        list_layout.addWidget(self.history_list)

        # Right Pane: Content Panel
        self._content_container = QFrame()
        self._content_container.setObjectName("contentPanelContainer")
        self._content_container.setFrameShape(QFrame.Shape.NoFrame)

        self._setup_content_panel()

        # Add to main layout (no splitter for crisp appearance)
        layout.addWidget(self._list_container, 4)
        layout.addWidget(self._content_container, 6)

        # Add content container to main layout
        main_layout.addWidget(content_container, 1)

    def _setup_content_panel(self) -> None:
        """Build the detail display surface."""
        layout = QVBoxLayout(self._content_container)
        # Margins: top=30, left=20, right=10, bottom=10
        layout.setContentsMargins(20, 30, 10, 10)

        self.content_panel = ContentPanel()
        layout.addWidget(self.content_panel)

    def _create_title_bar(self) -> QWidget:
        """Create title bar with label."""
        title_bar = QWidget()
        title_bar.setObjectName("viewTitleBar")
        title_bar.setFixedHeight(80)

        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(Spacing.MAJOR_GAP, 0, Spacing.MAJOR_GAP, 0)

        title = QLabel("History")
        title.setObjectName("viewTitle")
        title.setStyleSheet(
            f"font-size: {Typography.FONT_SIZE_XXL}px; font-weight: bold; color: {c.BLUE_4}; border: none;"
        )
        layout.addWidget(title, 0, Qt.AlignmentFlag.AlignCenter)

        return title_bar

    @pyqtSlot(tuple)
    def _on_selection_changed(self, selected_ids: tuple[int, ...]) -> None:
        """Handle selection update from list."""
        # Notify BaseView -> ActionDock
        self.capabilities_changed.emit()

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
        if not selection.has_selection:
            return

        transcript_id = selection.primary_id

        if action_id == ActionId.EDIT:
            if transcript_id is not None:
                self.edit_requested.emit(transcript_id)

        elif action_id == ActionId.DELETE:
            self.delete_requested.emit(list(selection.selected_ids))

        elif action_id == ActionId.REFINE:
            if transcript_id is not None:
                self.refine_requested.emit(transcript_id)

        elif action_id == ActionId.COPY:
            if transcript_id is not None and self._history_manager:
                entry = self._history_manager.get_entry(transcript_id)
                if entry:
                    from src.ui.utils.clipboard_utils import copy_text

                    copy_text(entry.text)

    def get_view_id(self) -> str:
        return VIEW_HISTORY

    def get_capabilities(self) -> Capabilities:
        """Return capabilities based on current selection."""
        from src.core.config_manager import ConfigManager

        selection = self.get_selection()
        count = len(selection.selected_ids)
        has_selection = count > 0
        refinement_enabled = ConfigManager.get_config_value("refinement", "enabled")

        return Capabilities(
            can_edit=count == 1,
            can_delete=has_selection,
            can_refine=count == 1 and refinement_enabled,
            can_copy=count == 1,
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

        # Connect to surgical database updates
        DatabaseSignalBridge().data_changed.connect(self._handle_data_changed)

    @pyqtSlot(EntityChange)
    def _handle_data_changed(self, change: EntityChange) -> None:
        """Handle incoming surgical updates from the database."""
        if not self._model:
            return

        if change.entity_type == "transcription":
            self._model.handle_database_change(change)

            # If the currently displayed entry was deleted, clear the panel
            selection = self.get_selection()
            if (
                change.action == ChangeAction.DELETED
                and selection.primary_id in change.ids
            ):
                self.content_panel.clear()

            # If the currently displayed entry was updated, reload it
            elif (
                change.action == ChangeAction.UPDATED
                and selection.primary_id in change.ids
                and self._history_manager
            ):
                entry = self._history_manager.get_entry(selection.primary_id)
                if entry:
                    self.content_panel.set_entry(entry)

        elif change.entity_type == "project":
            # Project color or metadata changed — refresh color indicators
            self._model.refresh_project_colors()
