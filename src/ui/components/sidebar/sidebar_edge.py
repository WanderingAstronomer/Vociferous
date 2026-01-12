"""
Sidebar Edge - Visual boundary strip on sidebar right side.

Shows a subtle vertical line separator.
"""

from PyQt6.QtWidgets import QWidget


class SidebarEdge(QWidget):
    """
    Right edge of sidebar - visual boundary strip.

    Shows a subtle vertical line separator.
    """

    WIDTH = 1  # Thin visual separator

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebarEdge")
        self.setFixedWidth(self.WIDTH)


# Export width constant for use elsewhere
SIDEBAR_EDGE_WIDTH = SidebarEdge.WIDTH
