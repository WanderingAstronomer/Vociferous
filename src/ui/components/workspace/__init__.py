"""
Workspace component for Vociferous.

State-driven content canvas with header, controls, and content areas.
"""

from ui.components.workspace.content import WorkspaceContent
from ui.components.workspace.header import WorkspaceHeader
from ui.components.workspace.workspace import MainWorkspace

__all__ = [
    "MainWorkspace",
    "WorkspaceContent",
    "WorkspaceControls",
    "WorkspaceHeader",
]
