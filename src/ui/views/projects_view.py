"""
ProjectsView - Tree view for projects/Projects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QHBoxLayout, QFrame, QVBoxLayout

from src.database.signal_bridge import DatabaseSignalBridge
from src.database.events import ChangeAction, EntityChange
from src.ui.components.shared import ContentPanel
from src.ui.constants.view_ids import VIEW_PROJECTS
from src.ui.contracts.capabilities import ActionId, Capabilities, SelectionState
from src.ui.views.base_view import BaseView
from src.ui.models import TranscriptionModel, ProjectProxyModel
from src.ui.widgets.project.project_tree import ProjectTreeWidget

if TYPE_CHECKING:
    from src.database.history_manager import HistoryManager


class ProjectsView(BaseView):
    """
    View for managing projects.

    Layout:
        [ Project Tree ] | [ Content Panel ]
    """

    edit_requested = pyqtSignal(int)
    refine_requested = pyqtSignal(int)
    data_changed = pyqtSignal()  # Emitted when data is modified (deleted, moved, etc)

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
        self._connect_signals()

    def refresh(self) -> None:
        """Reload the view data."""
        if hasattr(self, "project_tree") and hasattr(
            self.project_tree, "load_projects"
        ):
            self.project_tree.load_projects()
        self.content_panel.clear()

    def _setup_ui(self) -> None:
        """Initialize the layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Pane 1: Project Tree (Master)
        self._projects_container = QFrame()
        self._projects_container.setObjectName("projectsPane")
        projects_layout = QVBoxLayout(self._projects_container)
        # Top margin matches icon rail (28px) for visual alignment
        projects_layout.setContentsMargins(0, 28, 0, 0)

        self.project_tree = ProjectTreeWidget()
        projects_layout.addWidget(self.project_tree)

        # Pane 2: Content Panel (Detail)
        self._content_container = QFrame()
        self._content_container.setObjectName("contentPanelContainer")
        content_layout = QVBoxLayout(self._content_container)
        # Margins: top=30, left=20, right=10, bottom=10
        content_layout.setContentsMargins(20, 30, 10, 10)

        self.content_panel = ContentPanel()
        content_layout.addWidget(self.content_panel)

        # Add to layout
        layout.addWidget(self._projects_container, 4)
        layout.addWidget(self._content_container, 6)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.project_tree.entry_selected.connect(self._on_entry_selected)
        self.project_tree.itemSelectionChanged.connect(self._on_selection_changed)

        # Propagate data changes
        self.project_tree.entry_assignment_changed.connect(self.data_changed.emit)
        self.project_tree.project_deleted.connect(lambda _: self.data_changed.emit())
        self.project_tree.project_created.connect(
            lambda _, __: self.data_changed.emit()
        )
        self.project_tree.project_renamed.connect(
            lambda _, __: self.data_changed.emit()
        )

    def get_view_id(self) -> str:
        return VIEW_PROJECTS

    def get_capabilities(self) -> Capabilities:
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
            can_create_project=True,
        )

    def get_selection(self) -> SelectionState:
        if not hasattr(self, "project_tree") or not self.project_tree:
            return SelectionState()

        ids = self.project_tree.selected_ids
        if not ids:
            return SelectionState()

        return SelectionState(selected_ids=ids, primary_id=ids[0])

    def set_history_manager(self, manager: HistoryManager) -> None:
        """Inject history manager."""
        self._history_manager = manager
        if hasattr(self.project_tree, "set_history_manager"):
            self.project_tree.set_history_manager(manager)
        if hasattr(self.project_tree, "load_projects"):
            self.project_tree.load_projects()

        # Connect to database updates
        DatabaseSignalBridge().data_changed.connect(self._handle_data_changed)

    @pyqtSlot(EntityChange)
    def _handle_data_changed(self, change: EntityChange) -> None:
        """Handle incoming surgical updates from the database."""
        if change.entity_type in ("project", "transcription"):
            # ProjectsView does a bulk reload of the tree for now
            # as tree surgery is complex.
            if hasattr(self.project_tree, "load_projects"):
                self.project_tree.load_projects()

            # Handle content panel updates
            if change.entity_type == "transcription":
                selection = self.get_selection()
                if (
                    change.action == ChangeAction.DELETED
                    and selection.primary_id in change.ids
                ):
                    self.content_panel.clear()
                elif (
                    change.action == ChangeAction.UPDATED
                    and selection.primary_id in change.ids
                    and self._history_manager
                ):
                    entry = self._history_manager.get_entry(selection.primary_id)
                    if entry:
                        self.content_panel.set_entry(entry)

    def _on_entry_selected(self, text: str, timestamp: str) -> None:
        """Handle execution of a transcript selection from tree signal."""
        # Update content panel
        if self._history_manager and timestamp:
            t_id = self._history_manager.get_id_by_timestamp(timestamp)
            if t_id:
                entry = self._history_manager.get_entry(t_id)
                self.content_panel.set_entry(entry)

        self.capabilities_changed.emit()

    def _on_selection_changed(self) -> None:
        """Handle generic selection change (e.g. clicking a project or transcript)."""
        # Start by notifying change
        self.capabilities_changed.emit()

        # Content update logic
        sel = self.get_selection()
        if sel.primary_id:
            if self._history_manager:
                entry = self._history_manager.get_entry(sel.primary_id)
                self.content_panel.set_entry(entry)
        else:
            self.content_panel.clear()

    def dispatch_action(self, action_id: ActionId) -> None:
        if action_id == ActionId.CREATE_PROJECT:
            if hasattr(self.project_tree, "create_new_project"):
                self.project_tree.create_new_project()
            return

        selection = self.get_selection()
        if not selection.has_selection or not selection.primary_id:
            return

        transcript_id = selection.primary_id

        if action_id == ActionId.EDIT:
            self.edit_requested.emit(transcript_id)
        elif action_id == ActionId.REFINE:
            self.refine_requested.emit(transcript_id)
        elif action_id == ActionId.DELETE:
            if hasattr(self.project_tree, "delete_selected"):
                self.project_tree.delete_selected()
        elif action_id == ActionId.MOVE_TO_PROJECT:
            if hasattr(self.project_tree, "move_selected_to_project"):
                self.project_tree.move_selected_to_project()
        elif action_id == ActionId.COPY:
            if self._history_manager:
                entry = self._history_manager.get_entry(transcript_id)
                if entry:
                    from src.ui.utils.clipboard_utils import copy_text

                    copy_text(entry.text)
