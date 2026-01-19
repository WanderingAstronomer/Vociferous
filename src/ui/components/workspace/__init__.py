"""
Workspace component for Vociferous.

State-driven content canvas with header, controls, and content areas.
"""

from src.ui.components.workspace.content import WorkspaceContent
from src.ui.components.workspace.footer import BatchStatusFooter
from src.ui.components.workspace.header import WorkspaceHeader
from src.ui.components.workspace.workspace import MainWorkspace

__all__ = [
    "MainWorkspace",
    "WorkspaceContent",
    "BatchStatusFooter",
    "WorkspaceHeader",
]
