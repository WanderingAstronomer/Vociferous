"""
HistoryTreeView - Tree view for day-grouped transcriptions.

Uses Model/View pattern with TranscriptionModel as data source.
Provides selection, deletion, focus group assignment, and file watching.
"""

from __future__ import annotations

import logging
from contextlib import suppress
from typing import TYPE_CHECKING

from PyQt6.QtCore import (
    QAbstractItemModel,
    QFileSystemWatcher,
    QModelIndex,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHeaderView,
    QMenu,
    QTreeView,
)

from ui.models import FocusGroupProxyModel, TranscriptionModel
from ui.utils.clipboard_utils import copy_text
from ui.utils.error_handler import safe_callback
from ui.widgets.dialogs.custom_dialog import ConfirmationDialog
from ui.widgets.dialogs.error_dialog import show_error_dialog
from ui.widgets.history_tree.history_tree_delegate import TreeHoverDelegate

if TYPE_CHECKING:
    from history_manager import HistoryManager

logger = logging.getLogger(__name__)


class HistoryTreeView(QTreeView):
    """
    Tree view for history grouped by day with entry rows.

    Uses Model/View pattern:
    - TranscriptionModel or proxy model as data source
    - Delegate for custom rendering
    - No widget-owned data storage

    Signals:
        entrySelected(str, str): Emitted when entry is clicked (text, timestamp)
        entryDoubleClicked(str): Emitted when entry is double-clicked (text)
        countChanged(int): Emitted when visible entry count changes
        entryGroupChanged(str, object): Emitted when focus group changes
    """

    entrySelected = pyqtSignal(str, str)  # text, timestamp
    entryDoubleClicked = pyqtSignal(str)  # text (for copy)
    countChanged = pyqtSignal(int)
    entryGroupChanged = pyqtSignal(str, object)  # timestamp, group_id

    def __init__(
        self,
        model: TranscriptionModel | FocusGroupProxyModel | None = None,
        parent=None,
        *,
        enter_copies: bool = False,
    ) -> None:
        super().__init__(parent)
        self._model: QAbstractItemModel | None = model
        self._enter_copies = enter_copies
        self._history_manager: HistoryManager | None = None
        self._expanded_day_keys: set[str] = set()  # Track expanded day headers

        # File watcher for external changes
        self._file_watcher = QFileSystemWatcher(self)
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._reload_from_file)

        self._setup_ui()
        self._setup_connections()

        if self._model:
            self.setModel(self._model)

        self.setAccessibleName("Transcription History")
        self.setAccessibleDescription(
            "List of recent transcriptions grouped by day. Click headers to collapse."
        )

    def _setup_ui(self) -> None:
        """Configure tree view appearance."""
        self.setHeaderHidden(True)
        # Note: Header column config (resize modes, visual order) is applied
        # in _configure_header() after model is set

        # Flat hierarchy visually (no arrows, no indent)
        self.setRootIsDecorated(False)
        self.setIndentation(0)
        self.setItemsExpandable(True)
        self.setExpandsOnDoubleClick(False)

        self.setUniformRowHeights(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Use custom delegate for tiered hover colors
        self._delegate = TreeHoverDelegate(self)
        self.setItemDelegate(self._delegate)

    def _setup_connections(self) -> None:
        """Connect internal signals."""
        self.clicked.connect(self._on_item_clicked)
        self.doubleClicked.connect(self._on_item_double_clicked)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def set_history_manager(self, manager: HistoryManager) -> None:
        """Set the history manager for file watching and operations."""
        self._history_manager = manager
        self._reset_file_watch()

    def setModel(self, model: QAbstractItemModel | None) -> None:
        """Override to track model changes and connect signals."""
        super().setModel(model)

        # Defer header configuration to next event loop iteration
        # This ensures the header has processed the model's columnCount
        QTimer.singleShot(0, self._configure_header)
        QTimer.singleShot(0, self._restore_expansion_state)

        if not isinstance(model, (TranscriptionModel, FocusGroupProxyModel)):
            return

        # Connect to source model for data changes
        source: QAbstractItemModel | None = model
        if isinstance(model, FocusGroupProxyModel):
            source = model.sourceModel()

        if isinstance(source, TranscriptionModel):
            source.entryAdded.connect(self._on_model_changed)
            source.entryDeleted.connect(self._on_model_changed)
            source.entryUpdated.connect(self._on_model_changed)

            # Note: We listen to reset signals on the direct model (self.model())
            # to ensure we capture state relative to what the view sees (e.g. Proxy)
            # model.modelAboutToBeReset/modelReset are connected below

        # Connect to the direct model for reset handling
        # This ensures we handle proxy resets correctly
        if model:
            model.modelAboutToBeReset.connect(self._save_expansion_state)
            model.modelReset.connect(self._restore_expansion_state)

        self._emit_count()

    def _configure_header(self) -> None:
        """Configure header for single-column layout.

        Called after model is set via QTimer.singleShot to ensure
        the header has processed the model's columnCount.
        """
        header = self.header()
        col_count = header.count()

        if col_count >= 1:
            # Single column stretches to fill all available width
            header.setStretchLastSection(True)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

    def entry_count(self) -> int:
        """Return number of visible entries (excluding headers)."""
        if not self.model():
            return 0

        count = 0
        model = self.model()

        for day_row in range(model.rowCount()):
            day_index = model.index(day_row, 0)
            count += model.rowCount(day_index)

        return count

    def _on_item_clicked(self, index: QModelIndex) -> None:
        """Handle single click."""
        if not index.isValid():
            return

        is_header = index.data(TranscriptionModel.IsHeaderRole)
        if is_header:
            # Toggle expansion - convert any column index to column 0 for the row
            row_index = self.model().index(index.row(), 0, index.parent())
            new_expanded = not self.isExpanded(row_index)
            self.setExpanded(row_index, new_expanded)

            # Track expansion state by day key
            day_key = index.data(TranscriptionModel.DayKeyRole)
            if day_key:
                if new_expanded:
                    self._expanded_day_keys.add(day_key)
                else:
                    self._expanded_day_keys.discard(day_key)
            return

        text = index.data(TranscriptionModel.FullTextRole) or ""
        timestamp = index.data(TranscriptionModel.TimestampRole) or ""
        self.entrySelected.emit(text, timestamp)

    def _on_item_double_clicked(self, index: QModelIndex) -> None:
        """Handle double-click to copy."""
        if not index.isValid():
            return

        is_header = index.data(TranscriptionModel.IsHeaderRole)
        if is_header:
            return

        text = index.data(TranscriptionModel.FullTextRole) or ""
        self._copy_entry(index, text)
        self.entryDoubleClicked.emit(text)

    def _show_context_menu(self, position) -> None:
        """Show context menu for entries."""
        index = self.indexAt(position)
        if not index.isValid():
            return

        is_header = index.data(TranscriptionModel.IsHeaderRole)
        if is_header:
            return

        # Get all selected entries (filter out headers)
        selected_indices = self._get_selected_entry_indices()
        if not selected_indices:
            return

        # If clicked item is not in selection, treat as single item
        if index not in selected_indices:
            selected_indices = [index]

        count = len(selected_indices)
        menu = QMenu(self)

        # Copy action (only for single selection)
        if count == 1:
            text = selected_indices[0].data(TranscriptionModel.FullTextRole) or ""
            copy_action = menu.addAction("Copy")
            copy_action.triggered.connect(
                safe_callback(
                    lambda checked: self._copy_entry(selected_indices[0], text),
                    "copy_entry",
                )
            )

        # Focus group assignment
        if self._history_manager:
            menu.addSeparator()

            # Get group IDs for selected items
            group_ids = {
                idx.data(TranscriptionModel.GroupIDRole) for idx in selected_indices
            }
            current_group_id = group_ids.pop() if len(group_ids) == 1 else None
            focus_groups = self._history_manager.get_focus_groups()

            if focus_groups:
                menu_label = (
                    "Assign to Group"
                    if count == 1
                    else f"Assign {count} Items to Group"
                )
                assign_menu = menu.addMenu(menu_label)

                # Build hierarchy map
                # groups: list of (id, name, color, parent_id)
                roots = []
                children_map: dict[int | None, list[tuple]] = {}

                for row in focus_groups:
                    # Handle flexible tuple unpacking for migration safety
                    if len(row) == 4:
                        gid, name, color, pid = row
                    else:
                        gid, name, color = row
                        pid = None

                    if pid is None:
                        roots.append((gid, name, color))
                    else:
                        if pid not in children_map:
                            children_map[pid] = []
                        children_map[pid].append((gid, name, color))

                # Helper to create action
                def add_group_action(menu_obj, g_id, g_name, g_color, indent=0):
                    # Visual indentation for subgroups
                    # Use a subtle indicator for hierarchy
                    prefix = "↳ " if indent > 0 else ""
                    display_name = prefix + g_name

                    # Create icon
                    icon = QIcon()
                    if g_color:
                        pixmap = QPixmap(12, 12)
                        pixmap.fill(QColor(g_color))
                        icon = QIcon(pixmap)

                    action = menu_obj.addAction(icon, display_name)
                    is_current = g_id == current_group_id
                    action.setCheckable(True)
                    action.setChecked(is_current)

                    # Always connect, checkable state handles UI feedback
                    action.triggered.connect(
                        safe_callback(
                            lambda checked,
                            gid=g_id,
                            indices=selected_indices: self._assign_items_to_group(
                                indices, gid
                            ),
                            "assign_to_group",
                        )
                    )

                # Render menu items in order
                for gid, name, color in roots:
                    add_group_action(assign_menu, gid, name, color, indent=0)

                    # Add children if any
                    if gid in children_map:
                        for child_gid, child_name, child_color in children_map[gid]:
                            add_group_action(
                                assign_menu,
                                child_gid,
                                child_name,
                                child_color,
                                indent=1,
                            )

                assign_menu.addSeparator()
                ungroup_label = (
                    "Remove from Group"
                    if count == 1
                    else f"Remove {count} Items from Group"
                )
                ungroup_action = assign_menu.addAction(ungroup_label)
                # Enable if any selected item has a group
                ungroup_action.setEnabled(
                    any(
                        idx.data(TranscriptionModel.GroupIDRole) is not None
                        for idx in selected_indices
                    )
                )
                ungroup_action.triggered.connect(
                    safe_callback(
                        lambda checked,
                        indices=selected_indices: self._assign_items_to_group(
                            indices, None
                        ),
                        "ungroup",
                    )
                )

                menu.addSeparator()

        # Delete action
        delete_label = "Delete Entry" if count == 1 else f"Delete {count} Entries"
        delete_action = menu.addAction(delete_label)
        delete_action.triggered.connect(
            safe_callback(
                lambda checked, indices=selected_indices: self._delete_entries(indices),
                "delete_entries",
            )
        )

        menu.exec(self.viewport().mapToGlobal(position))

    def _get_selected_entry_indices(self) -> list[QModelIndex]:
        """Get all selected entry indices, filtering out day headers."""
        selected = self.selectedIndexes()
        entries = []
        for index in selected:
            if index.isValid() and not index.data(TranscriptionModel.IsHeaderRole):
                timestamp = index.data(TranscriptionModel.TimestampRole)
                if timestamp and index not in entries:
                    entries.append(index)
        return entries

    def _assign_items_to_group(
        self, indices: list[QModelIndex], group_id: int | None
    ) -> None:
        """Assign multiple transcripts to a focus group."""
        for index in indices:
            timestamp = index.data(TranscriptionModel.TimestampRole)
            if timestamp:
                self._assign_to_group(timestamp, group_id)

    def _assign_to_group(self, timestamp: str, group_id: int | None) -> None:
        """Assign transcript to a focus group."""
        try:
            if not self._history_manager or not timestamp:
                return

            if self._history_manager.assign_transcript_to_focus_group(
                timestamp, group_id
            ):
                source_model = self._get_source_model()
                if source_model:
                    source_model.update_entry_group(timestamp, group_id)

                self.entryGroupChanged.emit(timestamp, group_id)
                self._emit_count()

                # Force viewport update to ensure proper geometry (fixes ghost hits)
                self.updateGeometry()
                self.viewport().update()
        except Exception as e:
            logger.exception("Error assigning to group")
            show_error_dialog(
                title="Assignment Error",
                message=f"Failed to assign transcript to group: {e}",
                parent=self,
            )

    def _get_source_model(self) -> TranscriptionModel | None:
        """Get the underlying TranscriptionModel."""
        model = self.model()
        if isinstance(model, FocusGroupProxyModel):
            source = model.sourceModel()
            return source if isinstance(source, TranscriptionModel) else None
        if isinstance(model, TranscriptionModel):
            return model
        return None

    def _copy_entry(self, index: QModelIndex, text: str) -> None:
        """Copy entry text to clipboard."""
        if text:
            copy_text(text)

    def _delete_entries(self, indices: list[QModelIndex]) -> None:
        """Delete multiple entries from the model and storage."""
        try:
            if not indices:
                return

            count = len(indices)
            # Confirm deletion
            title = "Delete Transcript" if count == 1 else f"Delete {count} Transcripts"
            message = (
                "Are you sure you want to delete this transcript?"
                if count == 1
                else f"Are you sure you want to delete {count} transcripts?"
            )
            dialog = ConfirmationDialog(
                self,
                title=title,
                message=message,
                confirm_text="Delete",
                cancel_text="Cancel",
                is_destructive=True,
            )

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            # Delete all selected entries
            source_model = self._get_source_model()
            for index in indices:
                timestamp = index.data(TranscriptionModel.TimestampRole)
                if timestamp and self._history_manager:
                    self._history_manager.delete_entry(timestamp)
                    if source_model:
                        source_model.delete_entry(timestamp)

            self._emit_count()
            self.updateGeometry()
            self.viewport().update()

        except Exception as e:
            logger.exception("Error deleting entries")
            show_error_dialog(
                title="Delete Error",
                message=f"Failed to delete entries: {e}",
                parent=self,
            )

    def _delete_entry(self, index: QModelIndex) -> None:
        """Delete an entry from the model and storage."""
        try:
            if not index.isValid():
                return

            is_header = index.data(TranscriptionModel.IsHeaderRole)
            if is_header:
                return

            timestamp = index.data(TranscriptionModel.TimestampRole)
            if not timestamp:
                return

            # Use bulk delete for consistency
            self._delete_entries([index])
            return

            # Old single-delete code preserved for keyboard shortcuts
            # Confirm deletion
            dialog = ConfirmationDialog(
                self,
                title="Delete Transcript",
                message="Are you sure you want to delete this transcript?",
                confirm_text="Delete",
                cancel_text="Cancel",
                is_destructive=True,
            )

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            candidate_index = self._find_adjacent_entry(index)

            deleted = True
            if self._history_manager:
                deleted = self._history_manager.delete_entry(timestamp)
            if not deleted:
                return

            source_model = self._get_source_model()
            if source_model:
                source_model.delete_entry(timestamp)

            if candidate_index.isValid():
                self.setCurrentIndex(candidate_index)
                self._on_item_clicked(candidate_index)
            else:
                self.entrySelected.emit("", "")

            self._emit_count()

            # Force viewport update to ensure proper geometry after deletion
            self.updateGeometry()
            self.viewport().update()
        except Exception as e:
            logger.exception("Error deleting entry")
            show_error_dialog(
                title="Delete Error",
                message=f"Failed to delete entry: {e}",
                parent=self,
            )

    def _find_adjacent_entry(self, index: QModelIndex) -> QModelIndex:
        """Find the nearest entry above or below."""
        model = self.model()
        if not model:
            return QModelIndex()

        # Try item above
        above = self.indexAbove(index)
        while above.isValid() and above.data(TranscriptionModel.IsHeaderRole):
            above = self.indexAbove(above)
        if above.isValid():
            return above

        # Try item below
        below = self.indexBelow(index)
        while below.isValid() and below.data(TranscriptionModel.IsHeaderRole):
            below = self.indexBelow(below)
        if below.isValid():
            return below

        return QModelIndex()

    def _on_model_changed(self, *args) -> None:
        """React to model data changes."""
        self._emit_count()

    def _emit_count(self) -> None:
        """Emit current entry count."""
        self.countChanged.emit(self.entry_count())

    def _reset_file_watch(self) -> None:
        """Reset file watcher to current history file."""
        if not self._history_manager:
            return

        path = getattr(self._history_manager, "history_file", None)
        if not path:
            return

        with suppress(Exception):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)

        with suppress(TypeError):
            self._file_watcher.fileChanged.disconnect(self._on_file_changed)

        existing_paths = self._file_watcher.files()
        if existing_paths:
            self._file_watcher.removePaths(existing_paths)
        self._file_watcher.addPath(str(path))
        self._file_watcher.fileChanged.connect(self._on_file_changed)

    def _on_file_changed(self, _) -> None:
        """Debounce file change reload."""
        self._debounce_timer.start(200)

    def _reload_from_file(self) -> None:
        """Reload model after external change."""
        self._reset_file_watch()

    def _save_expansion_state(self) -> None:
        """Save which day headers are expanded before model reset."""
        if not self.model():
            return

        model = self.model()

        # If model is empty (e.g. initial load or glitch), don't wipe out existing saved state
        # This acts as a persistence buffer so state survives transient empty reloads
        if model.rowCount() == 0:
            return

        self._expanded_day_keys.clear()

        for day_row in range(model.rowCount()):
            day_index = model.index(day_row, 0)
            if self.isExpanded(day_index):
                day_key = day_index.data(TranscriptionModel.DayKeyRole)
                if day_key:
                    self._expanded_day_keys.add(day_key)

    def _restore_expansion_state(self) -> None:
        """Restore expansion state after model reset."""
        if not self.model():
            return

        model = self.model()
        row_count = model.rowCount()

        # Handle empty model - nothing to expand
        if row_count == 0:
            self._expanded_day_keys.clear()
            return

        # On first load (empty _expanded_day_keys), initialize with today if it exists
        if not self._expanded_day_keys:
            from datetime import date

            today_key = date.today().isoformat()

            # Check if today exists in the model
            has_today = False
            for day_row in range(row_count):
                day_index = model.index(day_row, 0)
                day_key = day_index.data(TranscriptionModel.DayKeyRole)
                if day_key == today_key:
                    has_today = True
                    break

            # Only add today to expanded set if it actually exists
            if has_today:
                self._expanded_day_keys = {today_key}
            else:
                # No today, start with everything collapsed
                self._expanded_day_keys = set()

        for day_row in range(row_count):
            day_index = model.index(day_row, 0)
            day_key = day_index.data(TranscriptionModel.DayKeyRole)

            # Expand only if in the expanded set
            should_expand = day_key in self._expanded_day_keys
            self.setExpanded(day_index, should_expand)

        # Force viewport update to ensure proper geometry after model reset
        self.updateGeometry()
        self.viewport().update()

    def keyPressEvent(self, event) -> None:
        """Handle keyboard navigation and actions."""
        index = self.currentIndex()
        if not index.isValid():
            super().keyPressEvent(event)
            return

        is_header = index.data(TranscriptionModel.IsHeaderRole)

        match event.key():
            case Qt.Key.Key_Return | Qt.Key.Key_Enter:
                if not is_header:
                    if self._enter_copies:
                        text = index.data(TranscriptionModel.FullTextRole) or ""
                        self._copy_entry(index, text)
                    else:
                        self._on_item_clicked(index)
            case Qt.Key.Key_Delete:
                if not is_header:
                    self._delete_entry(index)
                    event.accept()
                    return
            case _:
                super().keyPressEvent(event)

    def cleanup(self) -> None:
        """Clean up resources before destruction."""
        try:
            # Stop debounce timer
            if self._debounce_timer.isActive():
                self._debounce_timer.stop()

            # Remove file watcher paths
            existing_paths = self._file_watcher.files()
            if existing_paths:
                self._file_watcher.removePaths(existing_paths)

            # Disconnect signals
            with suppress(TypeError):
                self._debounce_timer.timeout.disconnect(self._reload_from_file)
            with suppress(TypeError):
                self._file_watcher.fileChanged.disconnect(self._on_file_changed)
        except Exception:
            pass

    def __del__(self) -> None:
        """Destructor to ensure cleanup."""
        try:
            self.cleanup()
        except Exception:
            pass


# Compatibility alias
HistoryTreeWidget = HistoryTreeView
