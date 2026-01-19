"""
History tree widgets for transcription display.

Provides:
- TreeHoverDelegate: Custom paint delegate
- HistoryTreeView: Day-grouped tree view with Model/View pattern
- HistoryTreeWidget: Compatibility alias for HistoryTreeView
"""

from src.ui.widgets.history_tree.history_tree_delegate import TreeHoverDelegate
from src.ui.widgets.history_tree.history_tree_view import (
    HistoryTreeView,
    HistoryTreeWidget,
)

__all__ = [
    "HistoryTreeView",
    "HistoryTreeWidget",
    "TreeHoverDelegate",
]
