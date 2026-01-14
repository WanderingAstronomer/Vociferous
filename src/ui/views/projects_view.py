"""
ProjectsView - Tree view for projects/Projects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QFrame, QVBoxLayout

from ui.components.content_panel import ContentPanel
from ui.constants import Colors
from ui.constants.view_ids import VIEW_PROJECTS
from ui.contracts.capabilities import ActionId, Capabilities, SelectionState
from ui.views.base_view import BaseView
from ui.models import TranscriptionModel, ProjectProxyModel
from ui.widgets.project.project_tree import ProjectTreeWidget

if TYPE_CHECKING:
    from history_manager import HistoryManager


class ProjectsView(BaseView):
    """
    View for managing projects.

    Layout:
        [ Project Tree ] | [ Content Panel ]
    """

    editRequested = pyqtSignal(int)
    refineRequested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history_manager: HistoryManager | None = None
        self._model: TranscriptionModel | None = None
        self._proxy: ProjectProxyModel | None = None

        self._setup_ui()
        self._connect_signals()

    def refresh(self) -> None:
        """Reload the view data."""
        if hasattr(self, "project_tree") and hasattr(self.project_tree, "load_projects"):
            self.project_tree.load_projects()

    def _setup_ui(self) -> None:
        """Initialize the layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        pane_style = (
            f"background-color: {Colors.SURFACE}; "
            f"border: 1px solid {Colors.BORDER_DEFAULT};"
        )

        # Pane 1: Project Tree (Master)
        self._projects_container = QFrame()
        self._projects_container.setStyleSheet(pane_style)
        projects_layout = QVBoxLayout(self._projects_container)
        projects_layout.setContentsMargins(0, 0, 0, 0)

        self.project_tree = ProjectTreeWidget()
        projects_layout.addWidget(self.project_tree)

        # Pane 2: Content Panel (Detail)
        self._content_container = QFrame()
        self._content_container.setStyleSheet(pane_style)
        content_layout = QVBoxLayout(self._content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self.content_panel = ContentPanel()
        content_layout.addWidget(self.content_panel)

        # Add to layout
        layout.addWidget(self._projects_container, 4)
        layout.addWidget(self._content_container, 6)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.project_tree.entrySelected.connect(self._on_entry_selected)
        self.project_tree.itemSelectionChanged.connect(self._on_selection_changed)

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

    def _on_entry_selected(self, text: str, timestamp: str) -> None:
        """Handle execution of a transcript selection from tree signal."""
        # Update content panel
        if self._history_manager and timestamp:
            t_id = self._history_manager.get_id_by_timestamp(timestamp)
            if t_id:
                entry = self._history_manager.get_entry(t_id)
                self.content_panel.set_entry(entry)

        self.capabilitiesChanged.emit()

    def _on_selection_changed(self) -> None:
        """Handle generic selection change (e.g. clicking a project or transcript)."""
        # Start by notifying change
        self.capabilitiesChanged.emit()

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
            self.editRequested.emit(transcript_id)
        elif action_id == ActionId.REFINE:
            self.refineRequested.emit(transcript_id)
        elif action_id == ActionId.COPY:
            if self._history_manager:
                entry = self._history_manager.get_entry(transcript_id)
                if entry:
                    from ui.utils.clipboard_utils import copy_text

                    copy_text(entry.text)
