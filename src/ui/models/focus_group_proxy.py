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

from PyQt6.QtCore import QModelIndex, QObject, QSortFilterProxyModel

from ui.models.transcription_model import TranscriptionModel

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

    def _has_matching_children(self, parent_index: QModelIndex) -> bool:
        """Check if a day header has any entries matching our filter."""
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

    def setSourceModel(self, source_model: QAbstractItemModel | None) -> None:
        """Set the source model (should be TranscriptionModel)."""
        super().setSourceModel(source_model)
        if isinstance(source_model, TranscriptionModel):
            source_model.entryAdded.connect(lambda _: self.invalidateFilter())
            source_model.entryDeleted.connect(lambda _: self.invalidateFilter())
