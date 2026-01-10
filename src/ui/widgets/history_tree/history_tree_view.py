"""
HistoryTreeView - Tree view for day-grouped transcriptions.

Uses Model/View pattern with TranscriptionModel as data source.
Provides selection, deletion, focus group assignment, and file watching.
"""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING

from PyQt6.QtCore import QAbstractItemModel, QFileSystemWatcher, QModelIndex, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QTreeView,
)

from ui.models import FocusGroupProxyModel, TranscriptionModel
from ui.utils.clipboard_utils import copy_text
from ui.widgets.history_tree.history_tree_delegate import TreeHoverDelegate

if TYPE_CHECKING:
    from history_manager import HistoryManager


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
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
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

        self._emit_count()

    def _configure_header(self) -> None:
        """Configure header column sizing and visual order.
        
        Called after model is set via QTimer.singleShot to ensure
        the header has processed the model's columnCount.
        """
        header = self.header()
        col_count = header.count()
        
        if col_count >= 2:
            # IMPORTANT: Must disable stretchLastSection BEFORE setting resize modes
            # otherwise Qt will override our stretch setting
            header.setStretchLastSection(False)
            
            # Swap visual order FIRST: column 1 (preview) appears at visual position 0 (left)
            # column 0 (time) appears at visual position 1 (right)
            header.moveSection(1, 0)
            
            # Now set resize modes (these apply to LOGICAL columns)
            # Column 1 (preview, now visually LEFT) = Stretch to fill remaining space
            # Column 0 (time, now visually RIGHT) = Fixed width for timestamp
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(0, 120)  # Increased width for day headers and times

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
            self.setExpanded(row_index, not self.isExpanded(row_index))
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

        menu = QMenu(self)
        timestamp = index.data(TranscriptionModel.TimestampRole)
        text = index.data(TranscriptionModel.FullTextRole) or ""

        # Copy action
        copy_action = menu.addAction("Copy")
        copy_action.triggered.connect(lambda: self._copy_entry(index, text))

        # Focus group assignment
        if self._history_manager:
            menu.addSeparator()

            current_group_id = index.data(TranscriptionModel.GroupIDRole)
            focus_groups = self._history_manager.get_focus_groups()

            if focus_groups:
                assign_menu = menu.addMenu("Assign to Group")

                for group_id, name, _ in focus_groups:
                    action = assign_menu.addAction(name)
                    is_current = group_id == current_group_id
                    action.setCheckable(True)
                    action.setChecked(is_current)
                    action.triggered.connect(
                        lambda checked,
                        gid=group_id,
                        ts=timestamp: self._assign_to_group(ts, gid)
                    )

                assign_menu.addSeparator()
                ungroup_action = assign_menu.addAction("Remove from Group")
                ungroup_action.setEnabled(current_group_id is not None)
                ungroup_action.triggered.connect(
                    lambda: self._assign_to_group(timestamp, None)
                )

                menu.addSeparator()

        # Delete action
        delete_action = menu.addAction("Delete Entry")
        delete_action.triggered.connect(lambda: self._delete_entry(index))

        menu.exec(self.viewport().mapToGlobal(position))

    def _assign_to_group(self, timestamp: str, group_id: int | None) -> None:
        """Assign transcript to a focus group."""
        if not self._history_manager or not timestamp:
            return

        if self._history_manager.assign_transcript_to_focus_group(timestamp, group_id):
            source_model = self._get_source_model()
            if source_model:
                source_model.update_entry_group(timestamp, group_id)

            self.entryGroupChanged.emit(timestamp, group_id)
            self._emit_count()

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

    def _delete_entry(self, index: QModelIndex) -> None:
        """Delete an entry from the model and storage."""
        if not index.isValid():
            return

        is_header = index.data(TranscriptionModel.IsHeaderRole)
        if is_header:
            return

        timestamp = index.data(TranscriptionModel.TimestampRole)
        if not timestamp:
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
        source_model = self._get_source_model()
        if source_model:
            source_model.refresh_from_manager()

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


# Compatibility alias
HistoryTreeWidget = HistoryTreeView
