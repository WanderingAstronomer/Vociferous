"""
FocusGroupTreeWidget - Tree widget for focus group navigation.

Displays focus groups as expandable items with nested transcripts.
Handles selection, context menus, and CRUD operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from ui.constants import Colors, Dimensions, FocusGroupColors, Typography
from ui.widgets.dialogs import ConfirmationDialog, InputDialog
from ui.widgets.focus_group.focus_group_delegate import FocusGroupDelegate
from ui.widgets.transcript_item import (
    ROLE_FULL_TEXT,
    ROLE_TIMESTAMP_ISO,
    create_transcript_item,
)

if TYPE_CHECKING:
    from history_manager import HistoryManager


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
        self.setColumnCount(2)
        self.setHeaderHidden(True)

        header = self.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        # Visual order: preview first (left), time second (right)
        header.moveSection(1, 0)

        # Disable branch decorations (removes blue square indicator)
        self.setRootIsDecorated(False)
        self.setIndentation(20)

        self.setUniformRowHeights(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Custom delegate for accent bar rendering
        self.setItemDelegate(FocusGroupDelegate(self))

        # Use central stylesheet via object name
        self.setObjectName("focusGroupTree")

    def _setup_connections(self) -> None:
        """Connect internal signals."""
        self.itemClicked.connect(self._on_item_clicked)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def set_history_manager(self, manager: HistoryManager) -> None:
        """Set the history manager and reload groups."""
        self._history_manager = manager
        self.load_groups()

    def load_groups(self) -> None:
        """Load focus groups and their transcripts from history manager."""
        # Save expanded state before clearing
        expanded_group_ids = set()
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if item and item.isExpanded():
                group_id = item.data(0, self.ROLE_GROUP_ID)
                if group_id is not None:
                    expanded_group_ids.add(group_id)

        self.clear()

        if not self._history_manager:
            return

        groups = self._history_manager.get_focus_groups()

        for group_id, name, color in groups:
            # Create Group Item
            group_item = self._create_group_item(group_id, name, color)
            self.addTopLevelItem(group_item)

            # Fetch and add children
            transcripts = self._history_manager.get_transcripts_by_focus_group(group_id)
            for entry in transcripts:
                child_item = create_transcript_item(entry)
                group_item.addChild(child_item)

            # Restore expanded state (or start collapsed if new)
            group_item.setExpanded(group_id in expanded_group_ids)

            # Update count based on loaded children
            count = len(transcripts)
            self._update_group_label(group_item, name, count)

    def _create_group_item(
        self, group_id: int, name: str, color: str | None
    ) -> QTreeWidgetItem:
        """Create a focus group parent item."""
        item = QTreeWidgetItem(["", name])
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
        item.setFont(1, font)
        # Use group color for text if available, otherwise primary color
        text_color = QColor(color) if color else QColor(Colors.TEXT_PRIMARY)
        item.setForeground(1, text_color)

        return item

    def _update_group_label(self, item: QTreeWidgetItem, name: str, count: int) -> None:
        """Update group label (count stored but not displayed)."""
        item.setText(1, name)
        item.setData(0, self.ROLE_COUNT, count)

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        """Handle item clicks: toggle expansion or select transcript."""
        is_group = item.data(0, self.ROLE_IS_GROUP)

        if is_group:
            item.setExpanded(not item.isExpanded())
        else:
            # It's a transcript
            text = item.data(0, ROLE_FULL_TEXT)
            timestamp = item.data(0, ROLE_TIMESTAMP_ISO)
            if text and timestamp:
                self.entrySelected.emit(text, timestamp)

    def _show_context_menu(self, position) -> None:
        """Show context menu for group management."""
        item = self.itemAt(position)
        if not item:
            return

        is_group = item.data(0, self.ROLE_IS_GROUP)
        if is_group:
            self._show_group_context_menu(item, position)
        else:
            self._show_transcript_context_menu(item, position)

    def _show_group_context_menu(self, item: QTreeWidgetItem, position) -> None:
        """Show context menu for group items."""
        group_id = item.data(0, self.ROLE_GROUP_ID)
        group_name = item.text(1).split("  (")[0]
        current_color = item.data(0, self.ROLE_COLOR)

        menu = QMenu(self)

        rename_action = menu.addAction("Rename…")
        rename_action.triggered.connect(
            lambda: self._rename_group(group_id, group_name)
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
            lambda: self._delete_group(group_id, group_name)
        )

        menu.exec(self.viewport().mapToGlobal(position))

    def _show_transcript_context_menu(self, item: QTreeWidgetItem, position) -> None:
        """Show context menu for transcript items within a group."""
        timestamp = item.data(0, ROLE_TIMESTAMP_ISO)
        if not timestamp:
            return

        parent = item.parent()
        current_group_id = parent.data(0, self.ROLE_GROUP_ID) if parent else None

        menu = QMenu(self)

        # Move to another group submenu
        if self._history_manager:
            groups = self._history_manager.get_focus_groups()
            if groups:
                move_menu = menu.addMenu("Move to group")
                for gid, gname, gcolor in groups:
                    if gid != current_group_id:
                        action = move_menu.addAction(
                            self._create_color_icon(gcolor) if gcolor else QIcon(), 
                            gname
                        )
                        # Store both timestamp and group_id as tuple in action data
                        action.setData((timestamp, gid))
                        action.triggered.connect(self._handle_move_to_group)

        # Remove from group
        remove_action = menu.addAction("Remove from group")
        remove_action.triggered.connect(
            lambda: self._remove_from_group(timestamp)
        )

        menu.addSeparator()

        # Delete transcript
        delete_action = menu.addAction("Delete transcript…")
        delete_action.triggered.connect(
            lambda: self._delete_transcript(timestamp)
        )

        menu.exec(self.viewport().mapToGlobal(position))

    def _handle_move_to_group(self) -> None:
        """Handle move to group action triggered from context menu."""
        action = self.sender()
        if not action:
            return
        
        data = action.data()
        if not data or not isinstance(data, tuple) or len(data) != 2:
            return
        
        timestamp, group_id = data
        self._move_to_group(timestamp, group_id)

    def _move_to_group(self, timestamp: str, group_id: int) -> None:
        """Move a transcript to another focus group."""
        if self._history_manager:
            self._history_manager.assign_transcript_to_focus_group(timestamp, group_id)
            QTimer.singleShot(0, self.load_groups)

    def _remove_from_group(self, timestamp: str) -> None:
        """Remove a transcript from its focus group (set to None)."""
        if self._history_manager:
            self._history_manager.assign_transcript_to_focus_group(timestamp, None)
            QTimer.singleShot(0, self.load_groups)

    def _delete_transcript(self, timestamp: str) -> None:
        """Delete a transcript after confirmation."""
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

    def _create_color_icon(self, color: str) -> QIcon:
        """Create a colored square icon for the menu."""
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(color))
        return QIcon(pixmap)

    def _rename_group(self, group_id: int, current_name: str) -> None:
        """Show dialog to rename group."""
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

    def _change_color(self, group_id: int, color: str) -> None:
        """Update group color in history manager."""
        if self._history_manager and self._history_manager.update_focus_group_color(
            group_id, color
        ):
            self.load_groups()
            self.groupColorChanged.emit(group_id, color)

    def _delete_group(self, group_id: int, group_name: str) -> None:
        """Show confirmation dialog and delete group."""
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

    def create_group(self, name: str, color: str | None = None) -> int | None:
        """Create a new focus group via manager."""
        if not self._history_manager:
            return None

        if color is None:
            groups = self._history_manager.get_focus_groups()
            existing_colors = [g[2] for g in groups]
            color = FocusGroupColors.get_next_color(existing_colors)

        group_id = self._history_manager.create_focus_group(name, color)
        if group_id:
            self.load_groups()
            self.groupCreated.emit(group_id, name)

        return group_id

    def refresh_counts(self) -> None:
        """Refresh content."""
        self.load_groups()
