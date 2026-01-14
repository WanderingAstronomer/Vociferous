"""
ProjectProxyModel - Filters transcription entries by Project.

This proxy sits between TranscriptionModel and any view that needs
to show only entries belonging to a specific Project.

Features:
- Filters entries by group_id
- Preserves day header hierarchy (shows day headers that have matching entries)
- Efficient: only re-filters when group_id changes
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    QObject,
    QSortFilterProxyModel,
    QTimer,
)

from ui.models.transcription_model import TranscriptionModel

logger = logging.getLogger(__name__)


class ProjectProxyModel(QSortFilterProxyModel):
    """
    Proxy model that filters TranscriptionModel by Project.

    Usage:
        proxy = ProjectProxyModel()
        proxy.setSourceModel(transcription_model)
        proxy.set_project_id(42)  # Only show entries in project 42
        tree_view.setModel(proxy)
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._project_id: int | None = None
        self.setRecursiveFilteringEnabled(True)
        self.setDynamicSortFilter(
            True
        )  # Ensure updates to project_id trigger re-filtering

        # Defer filter invalidation to avoid segfaults during context menu callbacks
        self._invalidate_timer = QTimer()
        self._invalidate_timer.setSingleShot(True)
        self._invalidate_timer.setInterval(0)
        self._invalidate_timer.timeout.connect(self.invalidateFilter)

    def set_project_id(self, project_id: int | None) -> None:
        """Set the active project ID to filter by. None shows all."""
        if self._project_id != project_id:
            self._project_id = project_id
            self.invalidateFilter()

    def get_project_id(self) -> int | None:
        """Return the current project ID filter."""
        return self._project_id

    def setSourceModel(self, sourceModel: QAbstractItemModel | None) -> None:
        """Set the source model and connect signals."""
        super().setSourceModel(sourceModel)
        if sourceModel:
            sourceModel.dataChanged.connect(self._on_source_data_changed)

    def _on_source_data_changed(
        self, topLeft: QModelIndex, bottomRight: QModelIndex, roles: list[int] = []
    ) -> None:
        """Handle source data changes to trigger re-filtering if needed."""
        # If the ProjectIDRole changed, we MUST re-filter regardless of automatic dynamic sorting
        # This ensures that assigning a project immediately removes it from the view if needed
        if not roles or TranscriptionModel.ProjectIDRole in roles:
            self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """
        Determine if a row should be shown.

        Use recursive filtering:
        - Day headers: Return False (let Qt include them if children match)
        - Entries: Return True if group_id matches
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
                # Rely on setRecursiveFilteringEnabled(True) to show header if children match
                return False

            entry_project_id = source_index.data(TranscriptionModel.ProjectIDRole)
            return entry_project_id == self._project_id
        except Exception:
            logger.exception("Error in filterAcceptsRow")
            return True  # Default to showing row on error

    def _has_matching_children(self, parent_index: QModelIndex) -> bool:
        """Deprecated: Recursive filtering handles this."""
        return False
