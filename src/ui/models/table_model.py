from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex

from PyQt6.QtGui import QColor

from src.ui.constants import HISTORY_EXPORT_LIMIT

if TYPE_CHECKING:
    from src.database.history_manager import HistoryManager, HistoryEntry

logger = logging.getLogger(__name__)


class TranscriptionTableModel(QAbstractTableModel):
    """
    Flat table model for transcription history, enabling standard table sorting/filtering.

    Roles:
    - DisplayRole: Formatted string for UI
    - UserRole: Raw value for sorting
    """

    COL_ID = 0
    COL_TIMESTAMP = 1
    COL_PROJECT = 2
    COL_DURATION = 3
    COL_TEXT = 4

    HEADERS = ["ID", "Time", "Project", "Duration (s)", "Text"]

    # Roles for compatibility
    IdRole = Qt.ItemDataRole.UserRole + 7
    FullTextRole = Qt.ItemDataRole.UserRole + 4
    TimestampRole = Qt.ItemDataRole.UserRole + 3

    def __init__(self, history_manager: HistoryManager, parent=None):
        super().__init__(parent)
        self._history_manager = history_manager
        self.entries: list[HistoryEntry] = []
        self._project_map: dict[int, str] = {}
        self._color_map: dict[int, str | None] = {}
        # Initial load
        self.refresh_from_manager()

    def refresh_from_manager(self):
        """Reload data from the history manager."""
        self.beginResetModel()

        # Load projects mapping
        projects = self._history_manager.get_projects()
        self._project_map = {p_id: p_name for p_id, p_name, _, _ in projects}

        # Load project colors
        self._color_map = self._history_manager.get_project_colors()

        # Use export limit constant for full history view
        self.entries = self._history_manager.get_recent(limit=HISTORY_EXPORT_LIMIT)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self.entries)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self.entries)):
            return None

        entry = self.entries[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == self.COL_ID:
                return str(entry.id)
            elif col == self.COL_TIMESTAMP:
                # Basic formatting: remove T, keep seconds
                return entry.timestamp.replace("T", " ")[:19]
            elif col == self.COL_PROJECT:
                if entry.project_id:
                    return self._project_map.get(
                        entry.project_id, f"ID:{entry.project_id}"
                    )
                return "Default"
            elif col == self.COL_DURATION:
                return f"{entry.duration_ms / 1000:.2f}"
            elif col == self.COL_TEXT:
                # Truncate very long text for display efficiency?
                # QTableView handles it ok, but maybe limit distinct display?
                return entry.text

        elif role == Qt.ItemDataRole.UserRole:  # Raw data for sorting
            if col == self.COL_ID:
                return entry.id
            elif col == self.COL_TIMESTAMP:
                return entry.timestamp
            elif col == self.COL_PROJECT:
                return entry.project_id if entry.project_id else 0
            elif col == self.COL_DURATION:
                return entry.duration_ms
            elif col == self.COL_TEXT:
                return entry.text

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col == self.COL_TEXT:
                return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignCenter

        elif role == Qt.ItemDataRole.BackgroundRole:
            if col == self.COL_PROJECT and entry.project_id:
                color_hex = self._color_map.get(entry.project_id)
                if color_hex:
                    try:
                        color = QColor(color_hex)
                        color.setAlpha(40)  # Low alpha for readability
                        return color
                    except Exception:
                        pass

        elif role == self.IdRole:
            return entry.id
        elif role == self.FullTextRole:
            return entry.text
        elif role == self.TimestampRole:
            return entry.timestamp

        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            if 0 <= section < len(self.HEADERS):
                return self.HEADERS[section]
        return None
