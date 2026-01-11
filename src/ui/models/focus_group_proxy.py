"""
FocusGroupProxyModel - Filters transcription entries by focus group.

This proxy sits between TranscriptionModel and any view that needs
to show only entries belonging to a specific focus group.

Features:
- Filters entries by group_id
- Preserves day header hierarchy (shows day headers that have matching entries)
- Efficient: only re-filters when group_id changes
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QModelIndex, QObject, QSortFilterProxyModel, QTimer

from ui.models.transcription_model import TranscriptionModel
from ui.utils.error_handler import safe_callback

if TYPE_CHECKING:
    from PyQt6.QtCore import QAbstractItemModel

logger = logging.getLogger(__name__)


class FocusGroupProxyModel(QSortFilterProxyModel):
    """
    Proxy model that filters TranscriptionModel by focus group.

    Usage:
        proxy = FocusGroupProxyModel()
        proxy.setSourceModel(transcription_model)
        proxy.set_group_id(42)  # Only show entries in group 42
        tree_view.setModel(proxy)
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._group_id: int | None = None
        self.setRecursiveFilteringEnabled(True)
        
        # Defer filter invalidation to avoid segfaults during context menu callbacks
        self._invalidate_timer = QTimer()
        self._invalidate_timer.setSingleShot(True)
        self._invalidate_timer.setInterval(0)
        self._invalidate_timer.timeout.connect(self.invalidateFilter)

    def set_group_id(self, group_id: int | None) -> None:
        """Set the focus group ID to filter by."""
        if self._group_id != group_id:
            self._group_id = group_id
            self.invalidateFilter()

    def get_group_id(self) -> int | None:
        """Get the current focus group ID."""
        return self._group_id

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """
        Determine if a row should be shown.

        Day headers (no parent) are shown if they have matching children.
        Entries are shown if their group_id matches our filter.
        """
        try:
            source_model = self.sourceModel()
            if source_model is None:
                return True

            source_index = source_model.index(source_row, 0, source_parent)
            if not source_index.isValid():
                return False

            is_header = source_index.data(TranscriptionModel.IsHeaderRole)

            if is_header:
                return self._has_matching_children(source_index)

            entry_group_id = source_index.data(TranscriptionModel.GroupIDRole)
            return entry_group_id == self._group_id
        except Exception:
            logger.exception("Error in filterAcceptsRow")
            return True  # Default to showing row on error

    def _has_matching_children(self, parent_index: QModelIndex) -> bool:
        """Check if a day header has any entries matching our filter."""
        try:
            source_model = self.sourceModel()
            if source_model is None:
                return False

            child_count = source_model.rowCount(parent_index)

            for i in range(child_count):
                child_index = source_model.index(i, 0, parent_index)
                entry_group_id = child_index.data(TranscriptionModel.GroupIDRole)
                if entry_group_id == self._group_id:
                    return True

            return False
        except Exception:
            logger.exception("Error in _has_matching_children")
            return False

    def setSourceModel(self, source_model: QAbstractItemModel | None) -> None:
        """Set the source model (should be TranscriptionModel)."""
        super().setSourceModel(source_model)
        if isinstance(source_model, TranscriptionModel):
            # Use deferred invalidation to prevent segfaults when changes
            # happen during context menu callbacks or other Qt operations
            source_model.entryAdded.connect(
                safe_callback(lambda _: self._invalidate_timer.start(), "proxy_entry_added")
            )
            source_model.entryDeleted.connect(
                safe_callback(lambda _: self._invalidate_timer.start(), "proxy_entry_deleted")
            )
            source_model.entryUpdated.connect(
                safe_callback(lambda _: self._invalidate_timer.start(), "proxy_entry_updated")
            )
