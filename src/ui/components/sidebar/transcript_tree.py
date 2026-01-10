"""
TranscriptTreeView - Sidebar transcript tree for Ungrouped transcripts.

Uses FocusGroupProxyModel to filter out grouped transcripts,
showing only entries where group_id is None.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from ui.models import FocusGroupProxyModel, TranscriptionModel
from ui.widgets.history_tree import HistoryTreeView


class TranscriptTreeView(HistoryTreeView):
    """
    Sidebar transcript tree for Ungrouped transcripts.

    Uses proxy model to filter out grouped transcripts.
    Shows only entries where focus_group_id is None.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        # Create proxy model for filtering ungrouped entries
        self._proxy = FocusGroupProxyModel()
        self._proxy.set_group_id(None)  # Only show ungrouped
        super().__init__(model=self._proxy, parent=parent, enter_copies=False)
        self.setObjectName("sidebarList")

    def set_source_model(self, source_model: TranscriptionModel) -> None:
        """Set the underlying transcription model."""
        self._proxy.setSourceModel(source_model)
