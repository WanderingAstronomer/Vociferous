"""
TranscriptionModel - Single source of truth for transcription data.

Wraps HistoryManager and provides Qt Model/View interface for:
- Day-grouped hierarchical display (day headers as parents, entries as children)
- Multiple simultaneous views (history list, focus group trees, search results)
- Efficient updates via dataChanged signals instead of full reloads

Tree structure:
    Day Header (2025-01-09)
    ├── Entry 1 (12:34:56)
    ├── Entry 2 (14:22:10)
    └── Entry 3 (16:45:33)
    Day Header (2025-01-08)
    └── Entry 4 (09:15:22)
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QAbstractItemModel, QModelIndex, QObject, Qt, pyqtSignal

from ui.utils.history_utils import (
    format_day_header,
    format_preview,
    format_time_compact,
    group_entries_by_day,
)

if TYPE_CHECKING:
    from history_manager import HistoryEntry, HistoryManager

logger = logging.getLogger(__name__)


class TranscriptionModel(QAbstractItemModel):
    """
    Model for transcription history with day-grouped hierarchy.

    This is the ONLY place that knows how to organize entries for display.
    Views just ask "what's at row N?" and display it.

    Data roles:
    - Qt.DisplayRole: Text to display
    - DayKeyRole: ISO date string for day headers (e.g., "2025-01-09")
    - IsHeaderRole: True for day headers, False for entries
    - TimestampRole: ISO timestamp for entries
    - FullTextRole: Complete transcription text
    - GroupIDRole: Focus group ID (or None)
    - ColorRole: Focus group color (or None)
    """

    # Custom roles
    DayKeyRole = Qt.ItemDataRole.UserRole + 1
    IsHeaderRole = Qt.ItemDataRole.UserRole + 2
    TimestampRole = Qt.ItemDataRole.UserRole + 3
    FullTextRole = Qt.ItemDataRole.UserRole + 4
    GroupIDRole = Qt.ItemDataRole.UserRole + 5
    ColorRole = Qt.ItemDataRole.UserRole + 6

    # Signals for UI updates
    entryAdded = pyqtSignal(str)  # timestamp
    entryUpdated = pyqtSignal(str)  # timestamp
    entryDeleted = pyqtSignal(str)  # timestamp

    def __init__(
        self, history_manager: HistoryManager, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._history_manager = history_manager
        self._days: list[tuple[str, datetime, list[HistoryEntry]]] = []
        self._group_colors: dict[int, str | None] = {}
        # Map from Python object id to (is_day_header, day_idx, entry_idx)
        self._index_map: dict[int, tuple[bool, int, int]] = {}
        self._next_id = 0
        try:
            self._refresh_data()
        except Exception as e:
            print(f"Error initializing TranscriptionModel: {e}", file=sys.stderr)
            self._days = []
            self._group_colors = {}

    def _make_index_data(self, is_day_header: bool, day_idx: int, entry_idx: int = 0) -> int:
        """Create and store index metadata, return ID."""
        idx_id = self._next_id
        self._next_id += 1
        self._index_map[idx_id] = (is_day_header, day_idx, entry_idx)
        return idx_id
    
    def _get_index_data(self, idx_id: int) -> tuple[bool, int, int]:
        """Retrieve index metadata."""
        return self._index_map.get(idx_id, (False, -1, -1))

    def _refresh_data(self) -> None:
        """Reload data from HistoryManager."""
        entries = self._history_manager.get_recent(limit=1000)
        self._days = group_entries_by_day(entries)
        self._group_colors = self._history_manager.get_focus_group_colors()

    def refresh_from_manager(self) -> None:
        """Public API for external refresh."""
        self.beginResetModel()
        self._refresh_data()
        self.endResetModel()

    def refresh_group_colors(self) -> None:
        """Refresh focus group colors and notify views."""
        if not self._history_manager:
            return

        self._group_colors = self._history_manager.get_focus_group_colors()

        for day_idx, (_day_key, _day_dt, entries) in enumerate(self._days):
            if not entries:
                continue
            day_model_index = self.index(day_idx, 0)
            top_left = self.index(0, 0, day_model_index)
            bottom_right = self.index(len(entries) - 1, 1, day_model_index)
            if top_left.isValid() and bottom_right.isValid():
                self.dataChanged.emit(top_left, bottom_right, [self.ColorRole])

    def add_entry(self, entry: HistoryEntry) -> None:
        """Add a new entry to the model."""
        dt = datetime.fromisoformat(entry.timestamp)
        day_key = dt.date().isoformat()

        day_index = self._find_day_index(day_key)

        if day_index is None:
            self.beginInsertRows(QModelIndex(), 0, 0)
            self._days.insert(0, (day_key, dt, [entry]))
            self.endInsertRows()
        else:
            day_model_index = self.index(day_index, 0)
            self.beginInsertRows(day_model_index, 0, 0)
            self._days[day_index][2].insert(0, entry)
            self.endInsertRows()

        self.entryAdded.emit(entry.timestamp)

    def update_entry(self, timestamp: str, new_text: str) -> None:
        """Update an entry's text (for edits)."""
        for day_idx, (day_key, day_dt, entries) in enumerate(self._days):
            for entry_idx, entry in enumerate(entries):
                if entry.timestamp == timestamp:
                    entry.text = new_text
                    day_model_index = self.index(day_idx, 0)
                    entry_model_index = self.index(entry_idx, 0, day_model_index)
                    self.dataChanged.emit(
                        entry_model_index,
                        entry_model_index,
                        [Qt.ItemDataRole.DisplayRole, self.FullTextRole],
                    )
                    self.entryUpdated.emit(timestamp)
                    return

    def delete_entry(self, timestamp: str) -> None:
        """Remove an entry from the model."""
        for day_idx, (day_key, day_dt, entries) in enumerate(self._days):
            for entry_idx, entry in enumerate(entries):
                if entry.timestamp == timestamp:
                    day_model_index = self.index(day_idx, 0)
                    self.beginRemoveRows(day_model_index, entry_idx, entry_idx)
                    entries.pop(entry_idx)
                    self.endRemoveRows()

                    if not entries:
                        self.beginRemoveRows(QModelIndex(), day_idx, day_idx)
                        self._days.pop(day_idx)
                        self.endRemoveRows()

                    self.entryDeleted.emit(timestamp)
                    return

    def update_entry_group(self, timestamp: str, group_id: int | None) -> None:
        """Update an entry's focus group membership."""
        for day_idx, (day_key, day_dt, entries) in enumerate(self._days):
            for entry_idx, entry in enumerate(entries):
                if entry.timestamp == timestamp:
                    entry.focus_group_id = group_id
                    day_model_index = self.index(day_idx, 0)
                    entry_model_index = self.index(entry_idx, 0, day_model_index)
                    self.dataChanged.emit(
                        entry_model_index,
                        entry_model_index,
                        [self.GroupIDRole, self.ColorRole],
                    )
                    return

    def _find_day_index(self, day_key: str) -> int | None:
        """Find the index of a day header by its key."""
        for idx, (key, _, _) in enumerate(self._days):
            if key == day_key:
                return idx
        return None

    # === QAbstractItemModel interface ===

    def index(
        self, row: int, column: int, parent: QModelIndex | None = None
    ) -> QModelIndex:
        """Create a model index for the given row/column/parent."""
        try:
            # Safety: check parameter validity
            if column < 0 or row < 0:
                return QModelIndex()
            
            # Safety check for _days existence - must be a list
            if not hasattr(self, '_days'):
                return QModelIndex()
            if self._days is None:
                return QModelIndex()
            if not isinstance(self._days, list):
                return QModelIndex()
            
            # Handle None parent - treat as root
            if parent is None:
                parent = QModelIndex()
            
            # Root level items (days)
            if not parent.isValid():
                if 0 <= row < len(self._days):
                    # Create index for day header
                    idx_data = self._make_index_data(True, row, 0)
                    return self.createIndex(row, column, idx_data)
                return QModelIndex()
            
            # Child items (entries within a day)
            # Use internalId from parent to get day_idx
            parent_internal = parent.internalId()
            parent_data = self._get_index_data(parent_internal)
            if parent_data[0]:  # Is parent a day header?
                day_idx = parent_data[1]
                if 0 <= day_idx < len(self._days):
                    entries = self._days[day_idx][2]
                    if isinstance(entries, list) and 0 <= row < len(entries):
                        idx_data = self._make_index_data(False, day_idx, row)
                        return self.createIndex(row, column, idx_data)
            
            return QModelIndex()
        except Exception as e:
            print(f"Exception in index(): {e}", file=sys.stderr)
            return QModelIndex()

    def parent(self, index: QModelIndex | None = None) -> QModelIndex:  # type: ignore[override]
        """Get the parent of an index."""
        try:
            if index is None:
                index = QModelIndex()
            
            if not index.isValid():
                return QModelIndex()

            # Get metadata for this index
            internal_id = index.internalId()
            is_day_header, day_idx, entry_idx = self._get_index_data(internal_id)
            
            # Day headers have no parent
            if is_day_header:
                return QModelIndex()
            
            # Entries have the day header as parent
            if 0 <= day_idx < len(self._days):
                parent_idx_data = self._make_index_data(True, day_idx, 0)
                return self.createIndex(day_idx, 0, parent_idx_data)

            return QModelIndex()
        except Exception as e:
            print(f"Error in parent(): {e}", file=sys.stderr)
            return QModelIndex()

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        """Number of rows under parent."""
        # Safety: check if _days exists
        if not hasattr(self, '_days') or self._days is None:
            return 0
        
        # Handle None parent - don't create temporary QModelIndex objects
        if parent is None or not isinstance(parent, QModelIndex) or not parent.isValid():
            # Root level - return number of days
            return len(self._days) if self._days else 0

        # Parent is a valid index - return entries for that day
        day_idx = parent.row()
        if 0 <= day_idx < len(self._days):
            entries = self._days[day_idx][2]
            return len(entries) if entries else 0

        return 0

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        """Always 2 columns: [time/day, preview/text]."""
        return 2

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Return data for a given index and role."""
        try:
            # Protect against calls with invalid/corrupted indices
            if not isinstance(index, QModelIndex):
                return None
            
            # The safest check - wrapping isValid in a try/except
            try:
                is_valid = index.isValid()
            except:
                return None
            
            if not is_valid:
                return None

            # Safety check: ensure _days exists and is a list
            if not hasattr(self, '_days') or self._days is None or not isinstance(self._days, list):
                return None

            # Get metadata for this index
            try:
                internal_id = index.internalId()
                is_day_header, day_idx, entry_idx = self._get_index_data(internal_id)
                column = index.column()
            except:
                return None

            if is_day_header:
                return self._day_header_data(day_idx, column, role)
            else:
                return self._entry_data(day_idx, entry_idx, column, role)
        except Exception as e:
            print(f"Error in data(): {e}", file=sys.stderr)
            return None

    def _day_header_data(self, day_idx: int, column: int, role: int) -> Any:
        """Return data for a day header."""
        if not (0 <= day_idx < len(self._days)):
            return None

        day_key, day_dt, entries = self._days[day_idx]

        match role:
            case Qt.ItemDataRole.DisplayRole:
                # Header text goes in column 0 for delegate to fetch
                # (delegate paints full-width from column 0)
                if column == 0:
                    return format_day_header(day_dt)
                return ""
            case self.DayKeyRole:
                return day_key
            case self.IsHeaderRole:
                return True
            case _:
                return None

    def _entry_data(self, day_idx: int, entry_idx: int, column: int, role: int) -> Any:
        """Return data for an entry."""
        if not (0 <= day_idx < len(self._days)):
            return None

        entries = self._days[day_idx][2]
        if not (0 <= entry_idx < len(entries)):
            return None

        entry = entries[entry_idx]

        match role:
            case Qt.ItemDataRole.DisplayRole:
                if column == 0:
                    dt = datetime.fromisoformat(entry.timestamp)
                    return format_time_compact(dt)
                elif column == 1:
                    return format_preview(entry.text, max_length=60)
                return ""
            case self.TimestampRole:
                return entry.timestamp
            case self.FullTextRole:
                return entry.text
            case self.IsHeaderRole:
                return False
            case self.GroupIDRole:
                return entry.focus_group_id
            case self.ColorRole:
                if entry.focus_group_id is not None:
                    return self._group_colors.get(entry.focus_group_id)
                return None
            case _:
                return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """Return item flags."""
        try:
            if not index.isValid():
                return Qt.ItemFlag.NoItemFlags

            internal_id = index.internalId()
            is_day_header, _, _ = self._get_index_data(internal_id)

            if is_day_header:
                return Qt.ItemFlag.ItemIsEnabled

            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        except Exception as e:
            print(f"Error in flags(): {e}", file=sys.stderr)
            return Qt.ItemFlag.NoItemFlags

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """Column headers."""
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            match section:
                case 0:
                    return "Time"
                case 1:
                    return "Transcript"
        return None
