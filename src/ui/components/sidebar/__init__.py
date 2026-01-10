"""
Sidebar component for Vociferous.

Contains collapsible Focus Groups and Transcripts sections.
Full-height left panel with navigation spine functionality.
"""

from ui.components.sidebar.sidebar import SidebarWidget
from ui.components.sidebar.sidebar_edge import SIDEBAR_EDGE_WIDTH, SidebarEdge
from ui.components.sidebar.sidebar_styles import get_sidebar_styles
from ui.components.sidebar.transcript_tree import TranscriptTreeView

__all__ = [
    "SIDEBAR_EDGE_WIDTH",
    "SidebarEdge",
    "SidebarWidget",
    "TranscriptTreeView",
    "get_sidebar_styles",
]
