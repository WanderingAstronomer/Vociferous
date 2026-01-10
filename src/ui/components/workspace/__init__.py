"""
Workspace component for Vociferous.

State-driven content canvas with header, controls, and content areas.
"""

from ui.components.workspace.content import WorkspaceContent
from ui.components.workspace.controls import WorkspaceControls
from ui.components.workspace.header import WorkspaceHeader
from ui.components.workspace.workspace import MainWorkspace
from ui.components.workspace.workspace_styles import get_workspace_styles

__all__ = [
    "MainWorkspace",
    "WorkspaceContent",
    "WorkspaceControls",
    "WorkspaceHeader",
    "get_workspace_styles",
]
