"""
User View implementation.
Placeholder for user-centric data (identity, licensing, personalization).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget, QFrame

from ui.views.base_view import BaseView
from ui.constants.view_ids import VIEW_USER
from ui.constants import Colors


class UserView(BaseView):
    """
    Placeholder User view.
    Ref: Invariant 6.8
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("UserView")
        self._setup_ui()

    def get_view_id(self) -> str:
        return VIEW_USER

    def _setup_ui(self) -> None:
        """Initialize the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Title
        title = QLabel("User Profile")
        title.setObjectName("viewTitle")
        layout.addWidget(title)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # Content Placeholder (Empty State)
        content = QLabel("No user profile data available.")
        content.setObjectName("emptyStateParams") # Hint at styling
        content.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Use Colors constant instead of raw hex
        content.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-style: italic;") 
        
        layout.addWidget(content)
        
        description = QLabel(
            "This view will eventually host account, identity, "
            "licensing, or personalization concepts."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        layout.addStretch()
