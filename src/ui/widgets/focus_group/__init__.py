"""
Focus Group widgets for sidebar navigation.

Provides:
- FocusGroupDelegate: Custom paint delegate for group items
- FocusGroupTreeWidget: Tree widget with nested transcripts
- FocusGroupContainer: Container with header and tree
"""

from ui.widgets.focus_group.focus_group_container import FocusGroupContainer
from ui.widgets.focus_group.focus_group_delegate import FocusGroupDelegate
from ui.widgets.focus_group.focus_group_tree import FocusGroupTreeWidget

__all__ = [
    "FocusGroupContainer",
    "FocusGroupDelegate",
    "FocusGroupTreeWidget",
]
