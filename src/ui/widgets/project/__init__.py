"""
Project widgets for navigation.

Provides:
- ProjectDelegate: Custom paint delegate for group items
- ProjectTreeWidget: Tree widget with nested transcripts
"""

from src.ui.widgets.project.project_delegate import ProjectDelegate
from src.ui.widgets.project.project_tree import ProjectTreeWidget

__all__ = [
    "ProjectDelegate",
    "ProjectTreeWidget",
]
