"""
Content Panel - Detail display for transcript metadata.

Displays transcript title, full content text, and timestamp footer.
Used by HistoryView and ProjectsView to show transcript details on the right panel.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ui.utils.history_utils import format_day_header, format_preview, format_time
import ui.constants.dimensions as d

if TYPE_CHECKING:
    from database.history_manager import HistoryEntry


class ContentPanel(QWidget):
    """
    Detail display for transcript metadata.

    Shows title, full text content, and timestamp footer.
    Used exclusively by HistoryView and ProjectsView for the right-side detail panel.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the content panel.

        Args:
            parent: Optional parent widget for Qt ownership hierarchy.
        """
        super().__init__(parent)
        self.setObjectName("contentPanel")

        # Ensure custom widgets respect background-color in stylesheet
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Initialize the UI layout with detail display structure."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            d.CONTENT_PANEL_DETAIL_MARGIN_H,
            d.CONTENT_PANEL_DETAIL_MARGIN_V,
            d.CONTENT_PANEL_DETAIL_MARGIN_H,
            d.CONTENT_PANEL_DETAIL_MARGIN_V,
        )
        layout.setSpacing(d.CONTENT_PANEL_DETAIL_SPACING)

        # Header Section (Title)
        self._lbl_title = QLabel("Select a transcript")
        self._lbl_title.setObjectName("contentPanelTitle")
        layout.addWidget(self._lbl_title)

        # Separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setObjectName("contentPanelSeparator")
        layout.addWidget(separator)

        # Content area (read-only)
        self._txt_content = QTextBrowser()
        self._txt_content.setFrameShape(QFrame.Shape.NoFrame)
        self._txt_content.setObjectName("contentPanelText")
        # Disable default context menu (prevents 'Copy Link Location')
        self._txt_content.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        layout.addWidget(self._txt_content)

        # Footer Section (Timestamp)
        self._lbl_timestamp = QLabel("-")
        self._lbl_timestamp.setObjectName("contentPanelFooter")
        self._lbl_timestamp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._lbl_timestamp)

    def set_entry(self, entry: Optional[HistoryEntry]) -> None:
        """Display the given history entry, or clear if None."""
        if not entry:
            self.clear()
            return

        # Title Logic: Display Name > Fallback
        if entry.display_name and entry.display_name.strip():
            self._lbl_title.setText(entry.display_name)
        else:
            self._lbl_title.setText(format_preview(entry.text, max_length=30))

        # Content
        self._txt_content.setText(entry.text)

        # Footer - Timestamp & Project
        try:
            dt = datetime.fromisoformat(entry.timestamp)
            day = format_day_header(dt)
            time = format_time(dt)

            footer_text = f"{day} • {time}"
            if entry.project_name:
                footer_text += f" • Project: {entry.project_name}"

            self._lbl_timestamp.setText(footer_text)
        except Exception:
            self._lbl_timestamp.setText(entry.timestamp)

    def clear(self) -> None:
        """Reset the view to empty state."""
        self._lbl_title.setText("Select a transcript")
        self._txt_content.clear()
        self._lbl_timestamp.setText("-")
