"""
Project widgets for navigation.

Provides:
- ProjectDelegate: Custom paint delegate for group items
- ProjectTreeWidget: Tree widget with nested transcripts
- ProjectContainer: Container with header and tree
"""

from ui.widgets.project.project_container import ProjectContainer
from ui.widgets.project.project_delegate import ProjectDelegate
from ui.widgets.project.project_tree import ProjectTreeWidget

__all__ = [
    "ProjectContainer",
    "ProjectDelegate",
    "ProjectTreeWidget",
]
