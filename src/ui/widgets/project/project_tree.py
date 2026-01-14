"""
ProjectTreeWidget - Tree widget for project navigation.

Displays projects as expandable items with nested transcripts.
Handles selection, context menus, and CRUD operations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QFont,
    QIcon,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QWidget,
)

from ui.constants import Colors, Dimensions, ProjectColors, Typography
from ui.widgets.dialogs import ConfirmationDialog, CreateProjectDialog, InputDialog
from ui.widgets.dialogs.error_dialog import show_error_dialog
from ui.widgets.project.project_delegate import ProjectDelegate
from ui.widgets.transcript_item import (
    ROLE_FULL_TEXT,
    ROLE_TIMESTAMP_ISO,
    ROLE_ENTRY_ID,
    create_transcript_item,
)

if TYPE_CHECKING:
    from history_manager import HistoryManager

logger = logging.getLogger(__name__)


class ProjectTreeWidget(QTreeWidget):
    """
    Tree widget for project navigation with nested transcripts.

    Structure:
    - Project 1
      - Transcript A
      - Transcript B
    - Project 2

    Signals:
        entrySelected(str, str): Emitted when a transcript child is clicked
        projectCreated(int, str): Emitted when a new project is created
        projectRenamed(int, str): Emitted when a project is renamed
        projectDeleted(int): Emitted when a project is deleted
        projectColorChanged(int, str): Emitted when a project color changes
    """

    # Signals
    entrySelected = pyqtSignal(str, str)  # text, timestamp
    entryAssignmentChanged = pyqtSignal()  # Emitted when entries are moved/assigned
    projectCreated = pyqtSignal(int, str)
    projectRenamed = pyqtSignal(int, str)
    projectDeleted = pyqtSignal(int)
    projectColorChanged = pyqtSignal(int, str)

    # Custom roles for item data
    ROLE_IS_PROJECT = Qt.ItemDataRole.UserRole + 10
    ROLE_PROJECT_ID = Qt.ItemDataRole.UserRole + 11
    ROLE_COLOR = Qt.ItemDataRole.UserRole + 12
    ROLE_COUNT = Qt.ItemDataRole.UserRole + 13

    def __init__(
        self,
        history_manager: HistoryManager | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._history_manager = history_manager

        self._setup_ui()
        self._setup_connections()

        self.setAccessibleName("Projects")
        self.setAccessibleDescription("List of Projects and their transcripts")

        if self._history_manager:
            self.load_projects()

    def _setup_ui(self) -> None:
        """Configure tree widget appearance."""
        self.setColumnCount(1)
        self.setHeaderHidden(True)

        header = self.header()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        # Disable branch decorations (removes blue square indicator)
        self.setRootIsDecorated(False)
        self.setIndentation(20)

        self.setUniformRowHeights(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # Enable Drag and Drop
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDropIndicatorShown(True)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Explicitly disable default selection painting to prevent "blue rectangle"
        # The delegate handles all background painting.
        # Styling moved to unified_stylesheet.py (QTreeView#projectGroupTree)

        # Custom delegate for accent bar rendering
        self.setItemDelegate(ProjectDelegate(self))

        # Use central stylesheet via object name
        self.setObjectName("projectTree")

    @property
    def selected_ids(self) -> tuple[int, ...]:
        """Return the IDs of selected transcripts."""
        ids = []
        for item in self.selectedItems():
            # Skip projects
            if item.data(0, self.ROLE_IS_PROJECT):
                continue
            
            entry_id = item.data(0, ROLE_ENTRY_ID)
            if entry_id is not None:
                ids.append(entry_id)
        return tuple(ids)

    def _setup_connections(self) -> None:
        """Connect internal signals."""
        self.itemClicked.connect(self._on_item_clicked)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def startDrag(self, supportedActions: Qt.DropAction) -> None:
        """Handle start of drag operation."""
        item = self.currentItem()
        if not item:
            return

        # Only allow dragging transcripts (items that are NOT projects)
        is_project = item.data(0, self.ROLE_IS_PROJECT)
        if is_project:
            return

        super().startDrag(supportedActions)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept drag only if it is a move action from self."""
        if event.source() == self:
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Validate drop target during drag."""
        if event.source() != self:
            event.ignore()
            return

        # Let the tree widget handle highlighting and auto-expansion
        super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drop action."""
        if event.source() != self:
            return

        target_item = self.itemAt(event.position().toPoint())
        if not target_item:
            return

        # 1. Identify Target Project
        target_project_id = None
        is_project = target_item.data(0, self.ROLE_IS_PROJECT)

        if is_project:
            target_project_id = target_item.data(0, self.ROLE_PROJECT_ID)
        else:
            # Dropped on a transcript -> move to that transcript's parent project
            parent = target_item.parent()
            if parent:
                target_project_id = parent.data(0, self.ROLE_PROJECT_ID)

        if target_project_id is None:
            return

        # 2. Identify Dragged Item
        dragged_item = self.currentItem()
        if not dragged_item:
            return

        # Ensure we aren't dropping onto the same project
        parent = dragged_item.parent()
        current_project_id = parent.data(0, self.ROLE_PROJECT_ID) if parent else None

        if current_project_id == target_project_id:
            event.ignore()
            return

        timestamp = dragged_item.data(0, ROLE_TIMESTAMP_ISO)
        if not timestamp:
            return

        # 3. Execute Move
        if self._history_manager:
            # Perform DB update
            self._move_to_project(timestamp, target_project_id)

            # NOTE: We do NOT call super().dropEvent(event)
            # calling super would try to physically move the QTreeWidgetItem,
            # but _move_to_project triggers a reload via singleShot(0, load_projects),
            # so we'd have a race condition or double-move visual glitch.
            # By consuming the event here, we let the DB update drive the UI refresh.
            event.accept()

    def set_history_manager(self, manager: HistoryManager) -> None:
        """Set the history manager and reload projects."""
        self._history_manager = manager
        self.load_projects()

    def load_projects(self) -> None:
        """Load Projects and their transcripts from history manager."""
        # Save expanded state recursively
        expanded_project_ids = set()

        def collect_expanded(item: QTreeWidgetItem) -> None:
            if item.isExpanded():
                project_id = item.data(0, self.ROLE_PROJECT_ID)
                if project_id is not None:
                    expanded_project_ids.add(project_id)
            for i in range(item.childCount()):
                collect_expanded(item.child(i))

        for i in range(self.topLevelItemCount()):
            collect_expanded(self.topLevelItem(i))

        self.clear()

        if not self._history_manager:
            return

        projects = self._history_manager.get_projects()

        # Maps for hierarchy building
        project_items: dict[int, QTreeWidgetItem] = {}
        project_data: dict[int, tuple] = {}

        # 1. Create all project items
        for row in projects:
            # Handle both 3-tuple (old) and 4-tuple (new) for safety during migration
            if len(row) == 4:
                project_id, name, color, parent_id = row
            else:
                project_id, name, color = row
                parent_id = None

            item = self._create_project_item(project_id, name, color)
            project_items[project_id] = item
            project_data[project_id] = (name, color, parent_id)

        # 2. Build Tree Hierarchy
        for project_id, item in project_items.items():
            parent_id = project_data[project_id][2]

            if parent_id is not None and parent_id in project_items:
                project_items[parent_id].addChild(item)
            else:
                self.addTopLevelItem(item)

            # Restore expansion
            if project_id in expanded_project_ids:
                item.setExpanded(True)

            # 3. Add Transcripts
            transcripts = self._history_manager.get_transcripts_by_project(project_id)
            for entry in transcripts:
                child_item = create_transcript_item(entry)
                # Transcripts are always leaf nodes in a group
                item.addChild(child_item)

            # Update label count
            self._update_project_label(item, project_data[project_id][0], len(transcripts))

    def _create_project_item(
        self, project_id: int, name: str, color: str | None
    ) -> QTreeWidgetItem:
        """Create a Project parent item."""
        item = QTreeWidgetItem([name])
        # Projects: enabled, expandable, not selectable
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)

        item.setData(0, self.ROLE_IS_PROJECT, True)
        item.setData(0, self.ROLE_PROJECT_ID, project_id)
        item.setData(0, self.ROLE_COLOR, color)
        item.setData(0, self.ROLE_COUNT, 0)

        item.setSizeHint(0, QSize(-1, Dimensions.PROJECT_ROW_HEIGHT))

        # Styling - project headers are larger than transcript rows
        font = QFont()
        font.setPointSize(Typography.PROJECT_NAME_SIZE)
        font.setWeight(QFont.Weight.DemiBold)
        item.setFont(0, font)
        # Use project color for text if available, otherwise primary color
        text_color = QColor(color) if color else QColor(Colors.TEXT_PRIMARY)
        item.setForeground(0, text_color)

        return item

    def _update_project_label(self, item: QTreeWidgetItem, name: str, count: int) -> None:
        """Update project label (count stored but not displayed)."""
        item.setText(0, name)
        item.setData(0, self.ROLE_COUNT, count)

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        """Handle item clicks: toggle expansion or select transcript."""
        try:
            is_project = item.data(0, self.ROLE_IS_PROJECT)

            if is_project:
                item.setExpanded(not item.isExpanded())
            else:
                # It's a transcript
                text = item.data(0, ROLE_FULL_TEXT)
                timestamp = item.data(0, ROLE_TIMESTAMP_ISO)
                if text and timestamp:
                    self.entrySelected.emit(text, timestamp)
        except Exception:
            logger.exception("Error handling item click")

    def _show_context_menu(self, position) -> None:
        """Show context menu for project management."""
        try:
            item = self.itemAt(position)
            if not item:
                return

            is_project = item.data(0, self.ROLE_IS_PROJECT)
            if is_project:
                self._show_project_context_menu(item, position)
            else:
                self._show_transcript_context_menu(item, position)
        except Exception:
            logger.exception("Error showing context menu")

    def _show_project_context_menu(self, item: QTreeWidgetItem, position) -> None:
        """Show context menu for project items."""
        project_id = item.data(0, self.ROLE_PROJECT_ID)
        project_name = item.text(0)
        current_color = item.data(0, self.ROLE_COLOR)

        menu = QMenu(self)

        rename_action = menu.addAction("Rename…")
        rename_action.triggered.connect(
            lambda checked: self._rename_project(project_id, project_name)
        )

        # New: Create Sub-Project
        # Limit nesting to 1 level (only top-level projects can have sub-projects)
        if item.parent() is None:
            create_sub_action = menu.addAction("Create Sub-Project…")
            create_sub_action.triggered.connect(
                lambda checked: self._create_sub_project_dialog(project_id)
            )

        color_menu = menu.addMenu("Change color")
        for color in ProjectColors.PALETTE:
            color_name = ProjectColors.COLOR_NAMES.get(color, "Unknown")
            color_action = color_menu.addAction(
                self._create_color_icon(color), color_name
            )
            color_action.setCheckable(True)
            color_action.setChecked(color == current_color)
            color_action.triggered.connect(
                lambda checked, c=color: self._change_color(project_id, c)
            )

        menu.addSeparator()

        delete_action = menu.addAction("Delete Project…")
        delete_action.triggered.connect(
            lambda checked: self._delete_project(project_id, project_name)
        )

        menu.exec(self.viewport().mapToGlobal(position))

    def _show_transcript_context_menu(self, item: QTreeWidgetItem, position) -> None:
        """Show context menu for transcript items within a project."""
        # Get all selected transcript items (filter out projects)
        selected_items = self._get_selected_transcript_items()
        if not selected_items:
            return

        # If clicked item is not in selection, treat as single item
        if item not in selected_items:
            selected_items = [item]

        count = len(selected_items)
        menu = QMenu(self)

        # Move to another project submenu
        if self._history_manager:
            projects = self._history_manager.get_projects()
            if projects:
                menu_label = (
                    "Move to project" if count == 1 else f"Move {count} items to project"
                )
                move_menu = menu.addMenu(menu_label)

                # Get current project(s) to exclude from menu
                current_project_ids = {
                    item.parent().data(0, self.ROLE_PROJECT_ID)
                    for item in selected_items
                    if item.parent()
                }

                for row in projects:
                    # Unpack safely to handle 3 or 4 elements
                    if len(row) == 4:
                        pid, pname, pcolor, _ = row
                    else:
                        pid, pname, pcolor = row

                    if pid not in current_project_ids:
                        action = move_menu.addAction(
                            self._create_color_icon(pcolor) if pcolor else QIcon(),
                            pname,
                        )
                        # Store items and project_id for bulk move
                        action.setData((selected_items, pid))
                        action.triggered.connect(self._handle_bulk_move_to_project)

        # Remove from project
        remove_label = (
            "Remove from project" if count == 1 else f"Remove {count} items from project"
        )
        remove_action = menu.addAction(remove_label)
        remove_action.triggered.connect(
            lambda checked, items=selected_items: self._remove_items_from_project(items)
        )

        menu.addSeparator()

        # Delete transcript
        delete_label = (
            "Delete transcript…" if count == 1 else f"Delete {count} transcripts…"
        )
        delete_action = menu.addAction(delete_label)
        delete_action.triggered.connect(
            lambda checked, items=selected_items: self._delete_transcripts(items)
        )

        menu.exec(self.viewport().mapToGlobal(position))

    def _get_selected_transcript_items(self) -> list[QTreeWidgetItem]:
        """Get all selected transcript items, filtering out project headers."""
        selected = self.selectedItems()
        transcripts = []
        for item in selected:
            is_project = item.data(0, self.ROLE_IS_PROJECT)
            if not is_project and item.data(0, ROLE_TIMESTAMP_ISO):
                transcripts.append(item)
        return transcripts

    def _handle_bulk_move_to_project(self) -> None:
        """Handle bulk move to project action triggered from context menu."""
        from PyQt6.QtGui import QAction

        action = self.sender()
        if not action or not isinstance(action, QAction):
            return

        data = action.data()
        if not data or not isinstance(data, tuple) or len(data) != 2:
            return

        items, project_id = data
        for item in items:
            timestamp = item.data(0, ROLE_TIMESTAMP_ISO)
            if timestamp:
                self._move_to_project(timestamp, project_id)

    def _handle_move_to_project(self) -> None:
        """Handle move to project action triggered from context menu."""
        from PyQt6.QtGui import QAction

        action = self.sender()
        if not action or not isinstance(action, QAction):
            return

        data = action.data()
        if not data or not isinstance(data, tuple) or len(data) != 2:
            return

        timestamp, project_id = data
        self._move_to_project(timestamp, project_id)

    def _move_to_project(self, timestamp: str, project_id: int) -> None:
        """Move a transcript to another Project."""
        try:
            if self._history_manager:
                self._history_manager.assign_transcript_to_project(
                    timestamp, project_id
                )
                QTimer.singleShot(0, self.load_projects)
                # Notify assignment changed
                self.entryAssignmentChanged.emit()
        except Exception as e:
            logger.exception("Error moving transcript to project")
            show_error_dialog(
                title="Move Error",
                message=f"Failed to move transcript: {e}",
                parent=self,
            )

    def _remove_items_from_project(self, items: list[QTreeWidgetItem]) -> None:
        """Remove multiple transcripts from their current Projects."""
        try:
            if self._history_manager:
                for item in items:
                    timestamp = item.data(0, ROLE_TIMESTAMP_ISO)
                    if timestamp:
                        self._history_manager.assign_transcript_to_project(
                            timestamp, None
                        )
                QTimer.singleShot(0, self.load_projects)
                # Notify assignment changed (moved to unassigned)
                self.entryAssignmentChanged.emit()
        except Exception:
            logger.exception("Error removing items from project")

    def _remove_from_project(self, timestamp: str) -> None:
        """Remove a transcript from its Project (set to None)."""
        try:
            if self._history_manager:
                self._history_manager.assign_transcript_to_project(timestamp, None)
                QTimer.singleShot(0, self.load_projects)
                # Notify that an assignment changed (item moved to unassigned)
                self.entryAssignmentChanged.emit()
        except Exception as e:
            logger.exception("Error removing transcript from project")
            show_error_dialog(
                title="Remove Error",
                message=f"Failed to remove transcript from project: {e}",
                parent=self,
            )

    def _delete_transcripts(self, items: list[QTreeWidgetItem]) -> None:
        """Delete multiple transcripts from history."""
        try:
            count = len(items)
            title = "Delete Transcript" if count == 1 else f"Delete {count} Transcripts"
            message = (
                "Are you sure you want to delete this transcript?\n\nThis action cannot be undone."
                if count == 1
                else f"Are you sure you want to delete {count} transcripts?\n\nThis action cannot be undone."
            )

            dialog = ConfirmationDialog(
                self,
                title,
                message,
                confirm_text="Delete",
                is_destructive=True,
            )

            if dialog.exec():
                if self._history_manager:
                    for item in items:
                        timestamp = item.data(0, ROLE_TIMESTAMP_ISO)
                        if timestamp:
                            self._history_manager.delete_entry(timestamp)
                    QTimer.singleShot(0, self.load_projects)
                    # Notify deletions
                    self.entryAssignmentChanged.emit()
        except Exception:
            logger.exception("Error deleting transcripts")

    def _delete_transcript(self, timestamp: str) -> None:
        """Delete a transcript after confirmation."""
        try:
            dialog = ConfirmationDialog(
                self,
                "Delete Transcript",
                "Are you sure you want to delete this transcript?\n\n"
                "This action cannot be undone.",
                confirm_text="Delete",
                is_destructive=True,
            )
            if dialog.exec():
                if self._history_manager:
                    self._history_manager.delete_entry(timestamp)
                    QTimer.singleShot(0, self.load_projects)
                    # Notify deletion
                    self.entryAssignmentChanged.emit()
        except Exception as e:
            logger.exception("Error deleting transcript")
            show_error_dialog(
                title="Delete Error",
                message=f"Failed to delete transcript: {e}",
                parent=self,
            )

    def _create_color_icon(self, color: str) -> QIcon:
        """Create a colored square icon for the menu."""
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(color))
        return QIcon(pixmap)

    def _rename_project(self, project_id: int, current_name: str) -> None:
        """Show dialog to rename project."""
        try:
            dialog = InputDialog(
                self, "Rename Project", "Enter new name:", current_name
            )
            if dialog.exec():
                new_name = dialog.get_text()
                if new_name and new_name != current_name:
                    if (
                        self._history_manager
                        and self._history_manager.rename_project(project_id, new_name)
                    ):
                        self.load_projects()
                        self.projectRenamed.emit(project_id, new_name)
        except Exception as e:
            logger.exception("Error renaming project")
            show_error_dialog(
                title="Rename Error",
                message=f"Failed to rename project: {e}",
                parent=self,
            )

    def _change_color(self, project_id: int, color: str) -> None:
        """Update project color in history manager."""
        try:
            if self._history_manager and self._history_manager.update_project_color(
                project_id, color
            ):
                self.load_projects()
                self.projectColorChanged.emit(project_id, color)
        except Exception:
            logger.exception("Error changing project color")

    def _delete_project(self, project_id: int, project_name: str) -> None:
        """Show confirmation dialog and delete project."""
        try:
            dialog = ConfirmationDialog(
                self,
                "Delete Project",
                f"Are you sure you want to delete '{project_name}'?\n\n"
                "Transcripts within this project will be moved to Unassigned.",
                confirm_text="Delete",
                is_destructive=True,
            )
            if dialog.exec():
                if self._history_manager and self._history_manager.delete_project(
                    project_id
                ):
                    self.load_projects()
                    self.projectDeleted.emit(project_id)
        except Exception as e:
            logger.exception("Error deleting project")
            show_error_dialog(
                title="Delete Error",
                message=f"Failed to delete project: {e}",
                parent=self,
            )

    def create_project(
        self, name: str, color: str | None = None, parent_id: int | None = None
    ) -> int | None:
        """Create a new Project via manager."""
        try:
            if not self._history_manager:
                return None

            if color is None:
                projects = self._history_manager.get_projects()
                existing_colors = []
                for p in projects:
                    if len(p) >= 3:
                        existing_colors.append(p[2])
                color = ProjectColors.get_next_color(existing_colors)

            project_id = self._history_manager.create_project(
                name, color, parent_id=parent_id
            )
            if project_id:
                self.load_projects()

                if parent_id:
                    iterator = QTreeWidgetItemIterator(self)
                    while iterator.value():
                        item = iterator.value()
                        if item.data(0, self.ROLE_PROJECT_ID) == parent_id:
                            item.setExpanded(True)
                            break
                        iterator += 1

                self.projectCreated.emit(project_id, name)

            return project_id
        except Exception as e:
            logger.exception("Error creating project")
            show_error_dialog(
                title="Create Error",
                message=f"Failed to create project: {e}",
                parent=self,
            )
            return None

    def _create_sub_project_dialog(self, parent_id: int) -> None:
        """Show dialog to create a sub-project."""
        dialog = CreateProjectDialog(self, title="Create Sub-Project")
        if dialog.exec():
            name, color = dialog.get_result()
            if name:
                self.create_project(name, color, parent_id=parent_id)

    def refresh_counts(self) -> None:
        """Refresh content."""
        self.load_projects()
