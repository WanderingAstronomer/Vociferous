"""
Settings View implementation.
The sole UI surface for mutating persistent configuration values.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget, QFrame

from ui.views.base_view import BaseView
from ui.constants.view_ids import VIEW_SETTINGS


class SettingsView(BaseView):
    """
    Placeholder Settings view.
    Ref: Invariant 6.9
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsView")
        self._setup_ui()

    def get_view_id(self) -> str:
        return VIEW_SETTINGS

    def _setup_ui(self) -> None:
        """Initialize the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Title
        title = QLabel("Settings")
        title.setObjectName("viewTitle")  # Assuming this ID is styled
        # If no specific style, we can rely on standard typography tokens later
        # For now, we set a temporary font or rely on inheritance if 'viewTitle' is used
        layout.addWidget(title)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # Content Placeholder
        content = QLabel(
            "Configuration options will appear here.\n\n"
            "• Hotkeys\n"
            "• Models\n"
            "• Refinement\n"
            "• Performance\n"
            "• Theme"
        )
        content.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        content.setWordWrap(True)
        layout.addWidget(content)

        layout.addStretch()
