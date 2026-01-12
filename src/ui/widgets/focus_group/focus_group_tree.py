"""
FocusGroupTreeWidget - Tree widget for focus group navigation.

Displays focus groups as expandable items with nested transcripts.
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
    QPixmap
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

from ui.constants import Colors, Dimensions, FocusGroupColors, Typography
from ui.widgets.dialogs import ConfirmationDialog, InputDialog, CreateGroupDialog
from ui.widgets.dialogs.error_dialog import show_error_dialog
from ui.widgets.focus_group.focus_group_delegate import FocusGroupDelegate
from ui.widgets.transcript_item import (
    ROLE_FULL_TEXT,
    ROLE_TIMESTAMP_ISO,
    create_transcript_item,
)

if TYPE_CHECKING:
    from history_manager import HistoryManager

logger = logging.getLogger(__name__)


class FocusGroupTreeWidget(QTreeWidget):
    """
    Tree widget for Focus Group navigation with nested transcripts.

    Structure:
    - Group 1
      - Transcript A
      - Transcript B
    - Group 2

    Signals:
        entrySelected(str, str): Emitted when a transcript child is clicked
        groupCreated(int, str): Emitted when a new group is created
        groupRenamed(int, str): Emitted when a group is renamed
        groupDeleted(int): Emitted when a group is deleted
        groupColorChanged(int, str): Emitted when a group color changes
    """

    # Signals
    entrySelected = pyqtSignal(str, str)  # text, timestamp
    entryAssignmentChanged = pyqtSignal()  # Emitted when entries are moved/assigned
    groupCreated = pyqtSignal(int, str)
    groupRenamed = pyqtSignal(int, str)
    groupDeleted = pyqtSignal(int)
    groupColorChanged = pyqtSignal(int, str)

    # Custom roles for item data
    ROLE_IS_GROUP = Qt.ItemDataRole.UserRole + 10
    ROLE_GROUP_ID = Qt.ItemDataRole.UserRole + 11
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

        self.setAccessibleName("Focus Groups")
        self.setAccessibleDescription("List of focus groups and their transcripts")

        if self._history_manager:
            self.load_groups()

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
        self.setStyleSheet("""
            QTreeView {
                outline: 0;
                background-color: transparent;
                selection-background-color: transparent;
            }
            QTreeView::item:focus {
                border: none;
                outline: none;
            }
            QTreeView::item:selected {
                background-color: transparent;
                border: none;
            }
        """)

        # Custom delegate for accent bar rendering
        self.setItemDelegate(FocusGroupDelegate(self))

        # Use central stylesheet via object name
        self.setObjectName("focusGroupTree")

    def _setup_connections(self) -> None:
        """Connect internal signals."""
        self.itemClicked.connect(self._on_item_clicked)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def startDrag(self, supportedActions: Qt.DropAction) -> None:
        """Handle start of drag operation."""
        item = self.currentItem()
        if not item:
            return

        # Only allow dragging transcripts (items that are NOT groups)
        is_group = item.data(0, self.ROLE_IS_GROUP)
        if is_group:
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

        # 1. Identify Target Group
        target_group_id = None
        is_group = target_item.data(0, self.ROLE_IS_GROUP)

        if is_group:
            target_group_id = target_item.data(0, self.ROLE_GROUP_ID)
        else:
            # Dropped on a transcript -> move to that transcript's parent group
            parent = target_item.parent()
            if parent:
                target_group_id = parent.data(0, self.ROLE_GROUP_ID)

        if target_group_id is None:
            return

        # 2. Identify Dragged Item
        dragged_item = self.currentItem()
        if not dragged_item:
            return

        # Ensure we aren't dropping onto the same group
        parent = dragged_item.parent()
        current_group_id = parent.data(0, self.ROLE_GROUP_ID) if parent else None

        if current_group_id == target_group_id:
            event.ignore()
            return

        timestamp = dragged_item.data(0, ROLE_TIMESTAMP_ISO)
        if not timestamp:
            return

        # 3. Execute Move
        if self._history_manager:
            # Perform DB update
            self._move_to_group(timestamp, target_group_id)

            # NOTE: We do NOT call super().dropEvent(event)
            # calling super would try to physically move the QTreeWidgetItem,
            # but _move_to_group triggers a reload via singleShot(0, load_groups),
            # so we'd have a race condition or double-move visual glitch.
            # By consuming the event here, we let the DB update drive the UI refresh.
            event.accept()

    def set_history_manager(self, manager: HistoryManager) -> None:
        """Set the history manager and reload groups."""
        self._history_manager = manager
        self.load_groups()

    def load_groups(self) -> None:
        """Load focus groups and their transcripts from history manager."""
        # Save expanded state recursively
        expanded_group_ids = set()
        
        def collect_expanded(item: QTreeWidgetItem) -> None:
            if item.isExpanded():
                group_id = item.data(0, self.ROLE_GROUP_ID)
                if group_id is not None:
                    expanded_group_ids.add(group_id)
            for i in range(item.childCount()):
                collect_expanded(item.child(i))

        for i in range(self.topLevelItemCount()):
            collect_expanded(self.topLevelItem(i))

        self.clear()

        if not self._history_manager:
            return

        groups = self._history_manager.get_focus_groups()
        
        # Maps for hierarchy building
        group_items: dict[int, QTreeWidgetItem] = {}
        group_data: dict[int, tuple] = {}

        # 1. Create all group items
        for row in groups:
            # Handle both 3-tuple (old) and 4-tuple (new) for safety during migration
            if len(row) == 4:
                group_id, name, color, parent_id = row
            else:
                group_id, name, color = row
                parent_id = None
                
            item = self._create_group_item(group_id, name, color)
            group_items[group_id] = item
            group_data[group_id] = (name, color, parent_id)

        # 2. Build Tree Hierarchy
        for group_id, item in group_items.items():
            parent_id = group_data[group_id][2]
            
            if parent_id is not None and parent_id in group_items:
                group_items[parent_id].addChild(item)
            else:
                self.addTopLevelItem(item)

            # Restore expansion
            if group_id in expanded_group_ids:
                item.setExpanded(True)

            # 3. Add Transcripts
            transcripts = self._history_manager.get_transcripts_by_focus_group(group_id)
            for entry in transcripts:
                child_item = create_transcript_item(entry)
                # Transcripts are always leaf nodes in a group
                item.addChild(child_item)

            # Update label count
            self._update_group_label(item, group_data[group_id][0], len(transcripts))

    def _create_group_item(
        self, group_id: int, name: str, color: str | None
    ) -> QTreeWidgetItem:
        """Create a focus group parent item."""
        item = QTreeWidgetItem([name])
        # Groups: enabled, expandable, not selectable
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)

        item.setData(0, self.ROLE_IS_GROUP, True)
        item.setData(0, self.ROLE_GROUP_ID, group_id)
        item.setData(0, self.ROLE_COLOR, color)
        item.setData(0, self.ROLE_COUNT, 0)

        item.setSizeHint(0, QSize(-1, Dimensions.FOCUS_GROUP_ROW_HEIGHT))

        # Styling - group headers are larger than transcript rows
        font = QFont()
        font.setPointSize(Typography.FOCUS_GROUP_NAME_SIZE)
        font.setWeight(QFont.Weight.DemiBold)
        item.setFont(0, font)
        # Use group color for text if available, otherwise primary color
        text_color = QColor(color) if color else QColor(Colors.TEXT_PRIMARY)
        item.setForeground(0, text_color)

        return item

    def _update_group_label(self, item: QTreeWidgetItem, name: str, count: int) -> None:
        """Update group label (count stored but not displayed)."""
        item.setText(0, name)
        item.setData(0, self.ROLE_COUNT, count)

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        """Handle item clicks: toggle expansion or select transcript."""
        try:
            is_group = item.data(0, self.ROLE_IS_GROUP)

            if is_group:
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
        """Show context menu for group management."""
        try:
            item = self.itemAt(position)
            if not item:
                return

            is_group = item.data(0, self.ROLE_IS_GROUP)
            if is_group:
                self._show_group_context_menu(item, position)
            else:
                self._show_transcript_context_menu(item, position)
        except Exception:
            logger.exception("Error showing context menu")

    def _show_group_context_menu(self, item: QTreeWidgetItem, position) -> None:
        """Show context menu for group items."""
        group_id = item.data(0, self.ROLE_GROUP_ID)
        group_name = item.text(0) # Moved from column 1 to 0 in _create_group_item? No, _create_group_item sets text on 0.
        # Check _create_group_item: item = QTreeWidgetItem([name]). So it's col 0.
        # But wait, original code was: group_name = item.text(1).split("  (")[0]
        # Let's verify _create_group_item implementation.
        # I read it earlier: item = QTreeWidgetItem([name]). It uses one column?
        # Let's re-read _create_group_item to be sure.
        
        current_color = item.data(0, self.ROLE_COLOR)

        menu = QMenu(self)

        rename_action = menu.addAction("Rename…")
        rename_action.triggered.connect(
            lambda checked: self._rename_group(group_id, group_name)
        )
        
        # New: Create Subgroup
        # Limit nesting to 1 level (only top-level groups can have subgroups)
        if item.parent() is None:
            create_sub_action = menu.addAction("Create Subgroup…")
            create_sub_action.triggered.connect(
                lambda checked: self._create_subgroup_dialog(group_id)
            )

        color_menu = menu.addMenu("Change color")
        for color in FocusGroupColors.PALETTE:
            color_name = FocusGroupColors.COLOR_NAMES.get(color, "Unknown")
            color_action = color_menu.addAction(
                self._create_color_icon(color), color_name
            )
            color_action.setCheckable(True)
            color_action.setChecked(color == current_color)
            color_action.triggered.connect(
                lambda checked, c=color: self._change_color(group_id, c)
            )

        menu.addSeparator()

        delete_action = menu.addAction("Delete group…")
        delete_action.triggered.connect(
            lambda checked: self._delete_group(group_id, group_name)
        )

        menu.exec(self.viewport().mapToGlobal(position))

    def _show_transcript_context_menu(self, item: QTreeWidgetItem, position) -> None:
        """Show context menu for transcript items within a group."""
        # Get all selected transcript items (filter out groups)
        selected_items = self._get_selected_transcript_items()
        if not selected_items:
            return

        # If clicked item is not in selection, treat as single item
        if item not in selected_items:
            selected_items = [item]

        count = len(selected_items)
        menu = QMenu(self)

        # Move to another group submenu
        if self._history_manager:
            groups = self._history_manager.get_focus_groups()
            if groups:
                menu_label = "Move to group" if count == 1 else f"Move {count} items to group"
                move_menu = menu.addMenu(menu_label)
                
                # Get current group(s) to exclude from menu
                current_groups = {item.parent().data(0, self.ROLE_GROUP_ID) for item in selected_items if item.parent()}
                
                for row in groups:
                    # Unpack safely to handle 3 or 4 elements
                    if len(row) == 4:
                        gid, gname, gcolor, _ = row
                    else:
                        gid, gname, gcolor = row
                        
                    if gid not in current_groups:
                        action = move_menu.addAction(
                            self._create_color_icon(gcolor) if gcolor else QIcon(), 
                            gname
                        )
                        # Store items and group_id for bulk move
                        action.setData((selected_items, gid))
                        action.triggered.connect(self._handle_bulk_move_to_group)

        # Remove from group
        remove_label = "Remove from group" if count == 1 else f"Remove {count} items from group"
        remove_action = menu.addAction(remove_label)
        remove_action.triggered.connect(
            lambda checked, items=selected_items: self._remove_items_from_group(items)
        )

        menu.addSeparator()

        # Delete transcript
        delete_label = "Delete transcript…" if count == 1 else f"Delete {count} transcripts…"
        delete_action = menu.addAction(delete_label)
        delete_action.triggered.connect(
            lambda checked, items=selected_items: self._delete_transcripts(items)
        )

        menu.exec(self.viewport().mapToGlobal(position))

    def _get_selected_transcript_items(self) -> list[QTreeWidgetItem]:
        """Get all selected transcript items, filtering out group headers."""
        selected = self.selectedItems()
        transcripts = []
        for item in selected:
            is_group = item.data(0, self.ROLE_IS_GROUP)
            if not is_group and item.data(0, ROLE_TIMESTAMP_ISO):
                transcripts.append(item)
        return transcripts

    def _handle_bulk_move_to_group(self) -> None:
        """Handle bulk move to group action triggered from context menu."""
        from PyQt6.QtGui import QAction
        action = self.sender()
        if not action or not isinstance(action, QAction):
            return
        
        data = action.data()
        if not data or not isinstance(data, tuple) or len(data) != 2:
            return
        
        items, group_id = data
        for item in items:
            timestamp = item.data(0, ROLE_TIMESTAMP_ISO)
            if timestamp:
                self._move_to_group(timestamp, group_id)

    def _handle_move_to_group(self) -> None:
        """Handle move to group action triggered from context menu."""
        from PyQt6.QtGui import QAction
        action = self.sender()
        if not action or not isinstance(action, QAction):
            return
        
        data = action.data()
        if not data or not isinstance(data, tuple) or len(data) != 2:
            return
        
        timestamp, group_id = data
        self._move_to_group(timestamp, group_id)

    def _move_to_group(self, timestamp: str, group_id: int) -> None:
        """Move a transcript to another focus group."""
        try:
            if self._history_manager:
                self._history_manager.assign_transcript_to_focus_group(timestamp, group_id)
                QTimer.singleShot(0, self.load_groups)
                # Notify assignment changed
                self.entryAssignmentChanged.emit()
        except Exception as e:
            logger.exception("Error moving transcript to group")
            show_error_dialog(
                title="Move Error",
                message=f"Failed to move transcript: {e}",
                parent=self,
            )

    def _remove_items_from_group(self, items: list[QTreeWidgetItem]) -> None:
        """Remove multiple transcripts from their current focus groups."""
        try:
            if self._history_manager:
                for item in items:
                    timestamp = item.data(0, ROLE_TIMESTAMP_ISO)
                    if timestamp:
                        self._history_manager.assign_transcript_to_focus_group(
                            timestamp, None
                        )
                QTimer.singleShot(0, self.load_groups)
                # Notify assignment changed (moved to ungrouped)
                self.entryAssignmentChanged.emit()
        except Exception:
            logger.exception("Error removing items from group")

    def _remove_from_group(self, timestamp: str) -> None:
        """Remove a transcript from its focus group (set to None)."""
        try:
            if self._history_manager:
                self._history_manager.assign_transcript_to_focus_group(timestamp, None)
                QTimer.singleShot(0, self.load_groups)
                # Notify that an assignment changed (item moved to ungrouped)
                self.entryAssignmentChanged.emit()
        except Exception as e:
            logger.exception("Error removing transcript from group")
            show_error_dialog(
                title="Remove Error",
                message=f"Failed to remove transcript from group: {e}",
                parent=self,
            )

    def _delete_transcripts(self, items: list[QTreeWidgetItem]) -> None:
        """Delete multiple transcripts from history."""
        try:
            count = len(items)
            title = "Delete Transcript" if count == 1 else f"Delete {count} Transcripts"
            message = "Are you sure you want to delete this transcript?\n\nThis action cannot be undone." if count == 1 else f"Are you sure you want to delete {count} transcripts?\n\nThis action cannot be undone."
            
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
                    QTimer.singleShot(0, self.load_groups)
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
                    QTimer.singleShot(0, self.load_groups)
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

    def _rename_group(self, group_id: int, current_name: str) -> None:
        """Show dialog to rename group."""
        try:
            dialog = InputDialog(
                self, "Rename Focus Group", "Enter new name:", current_name
            )
            if dialog.exec():
                new_name = dialog.get_text()
                if new_name and new_name != current_name:
                    if self._history_manager and self._history_manager.rename_focus_group(
                        group_id, new_name
                    ):
                        self.load_groups()
                        self.groupRenamed.emit(group_id, new_name)
        except Exception as e:
            logger.exception("Error renaming group")
            show_error_dialog(
                title="Rename Error",
                message=f"Failed to rename group: {e}",
                parent=self,
            )

    def _change_color(self, group_id: int, color: str) -> None:
        """Update group color in history manager."""
        try:
            if self._history_manager and self._history_manager.update_focus_group_color(
                group_id, color
            ):
                self.load_groups()
                self.groupColorChanged.emit(group_id, color)
        except Exception:
            logger.exception("Error changing group color")

    def _delete_group(self, group_id: int, group_name: str) -> None:
        """Show confirmation dialog and delete group."""
        try:
            dialog = ConfirmationDialog(
                self,
                "Delete Focus Group",
                f"Are you sure you want to delete '{group_name}'?\n\n"
                "Transcripts within this group will be moved to Ungrouped.",
                confirm_text="Delete",
                is_destructive=True,
            )
            if dialog.exec():
                if self._history_manager and self._history_manager.delete_focus_group(
                    group_id
                ):
                    self.load_groups()
                    self.groupDeleted.emit(group_id)
        except Exception as e:
            logger.exception("Error deleting group")
            show_error_dialog(
                title="Delete Error",
                message=f"Failed to delete group: {e}",
                parent=self,
            )

    def create_group(self, name: str, color: str | None = None, parent_id: int | None = None) -> int | None:
        """Create a new focus group via manager."""
        try:
            if not self._history_manager:
                return None

            if color is None:
                groups = self._history_manager.get_focus_groups()
                existing_colors = []
                for g in groups:
                     if len(g) >= 3:
                         existing_colors.append(g[2])
                color = FocusGroupColors.get_next_color(existing_colors)

            group_id = self._history_manager.create_focus_group(name, color, parent_id=parent_id)
            if group_id:
                self.load_groups()
                
                if parent_id:
                    iterator = QTreeWidgetItemIterator(self)
                    while iterator.value():
                        item = iterator.value()
                        if item.data(0, self.ROLE_GROUP_ID) == parent_id:
                            item.setExpanded(True)
                            break
                        iterator += 1
                
                self.groupCreated.emit(group_id, name)

            return group_id
        except Exception as e:
            logger.exception("Error creating group")
            show_error_dialog(
                title="Create Error",
                message=f"Failed to create group: {e}",
                parent=self,
            )
            return None

    def _create_subgroup_dialog(self, parent_id: int) -> None:
        """Show dialog to create a subgroup."""
        dialog = CreateGroupDialog(self, title="Create Subgroup")
        # dialog.setWindowTitle("Create Subgroup")  # Handled by constructor
        if dialog.exec():
            name, color = dialog.get_result()
            if name:
                self.create_group(name, color, parent_id=parent_id)

    def refresh_counts(self) -> None:
        """Refresh content."""
        self.load_groups()
