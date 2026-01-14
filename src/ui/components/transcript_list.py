"""
TranscriptList - Reusable component for listing transcripts.

Wraps/Inherits HistoryTreeView to provide consistent behavior across views.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget

from ui.models import ProjectProxyModel, TranscriptionModel
from ui.widgets.history_tree.history_tree_view import HistoryTreeView

if TYPE_CHECKING:
    pass


class TranscriptList(HistoryTreeView):
    """
    Reusable list of transcripts.
    
    Inherits from HistoryTreeView to leverage existing drawing/model logic.
    Adds consistent selection API for Views.
    """
    
    selectionChangedSignal = pyqtSignal(tuple) # Tuple[int, ...] (selected IDs)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        self.setObjectName("transcriptList")
        
        # Connection moved to setModel to ensure selectionModel exists

    def setModel(self, model):
        super().setModel(model)
        if self.selectionModel():
            try:
                self.selectionModel().selectionChanged.disconnect(self._on_selection_changed)
            except Exception:
                pass # Not connected
            self.selectionModel().selectionChanged.connect(self._on_selection_changed)

    def _on_selection_changed(self, selected, deselected) -> None:
        """Handle selection changes from the model."""
        ids = self.get_selected_ids()
        self.selectionChangedSignal.emit(ids)

    def get_selected_ids(self) -> Tuple[int, ...]:
        """Return list of selected transcript IDs (database IDs)."""
        if not self.selectionModel():
            return ()
        indexes = self.selectionModel().selectedRows()
        ids = []
        for index in indexes:
            # Check if it's a valid entry (not a header)
            is_header = index.data(TranscriptionModel.IsHeaderRole)
            if not is_header:
                t_id = index.data(TranscriptionModel.IdRole)
                if t_id is not None:
                    ids.append(t_id)
        return tuple(ids)

    def set_filter_group(self, group_id: int | None) -> None:
        """Filter the list by group ID. None means ungrouped (or all?)."""
        # If we are using a proxy, update it.
        # HistoryTreeView allows setting a model. 
        # We usually want a ProjectProxyModel here.
        model = self.model()
        if isinstance(model, ProjectProxyModel):
            model.set_group_id(group_id)
        elif isinstance(model, TranscriptionModel):
            # If we are on raw model, we might need to wrap it?
            # Ideally the caller sets up the proxy, but we can helper here.
            pass

    def set_show_all(self, show: bool = True) -> None:
        """Configure to show all items vs filtered."""
        # For RecentView, we might want 'All' or 'Ungrouped'
        model = self.model()
        if isinstance(model, ProjectProxyModel):
            if show:
                # If proxy supports 'show all', otherwise we might need to 
                # set the source model directly or similar?
                # ProjectProxy usually filters by group ID.
                # If we want ALL, maybe we shouldn't use the proxy?
                pass
