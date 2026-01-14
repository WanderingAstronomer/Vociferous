"""
Transcript Inspector Component.

A shared detail view for displaying transcript content and metadata.
Used in RecentView and ProjectsView.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTextEdit,
    QFrame,
    QHBoxLayout,
)

from ui.constants import Colors

if TYPE_CHECKING:
    from history_manager import HistoryEntry


class TranscriptInspector(QWidget):
    """
    Read-only inspector for a single transcript entry.
    Displays timestamp, duration, and full text content.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Initialize the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # Header (Timestamp)
        self._lbl_timestamp = QLabel("Select a transcript")
        self._lbl_timestamp.setObjectName("timestampLabel")
        layout.addWidget(self._lbl_timestamp)
        
        # Metadata Row
        meta_layout = QHBoxLayout()
        self._lbl_duration = QLabel("-")
        self._lbl_duration.setObjectName("durationLabel")
        meta_layout.addWidget(self._lbl_duration)
        meta_layout.addStretch()
        layout.addLayout(meta_layout)
        
        # Content
        self._txt_content = QTextEdit()
        self._txt_content.setReadOnly(True)
        self._txt_content.setFrameShape(QFrame.Shape.NoFrame)
        # Style via unified_stylesheet
        layout.addWidget(self._txt_content)

    def set_entry(self, entry: Optional[HistoryEntry]) -> None:
        """Display the given history entry, or clear if None."""
        if not entry:
            self.clear()
            return

        # Format Timestamp
        # Assuming ISO format "YYYY-MM-DDTHH:MM:SS..."
        try:
            ts = entry.timestamp.split("T")
            date_part = ts[0]
            time_part = ts[1][:8] if len(ts) > 1 else ""
            self._lbl_timestamp.setText(f"{date_part} {time_part}")
        except Exception:
             self._lbl_timestamp.setText(entry.timestamp)

        # Content - Prefer normalized text if available (though dual-text invariant says we have both)
        # If we had a switch for "Raw vs Normalized", we'd handle it here.
        # For now, show Normalized (user visible default).
        self._txt_content.setText(entry.text)
        
        # Metadata
        # If HistoryEntry had duration, we'd show it.
        # Check if attribute exists
        if hasattr(entry, "duration") and entry.duration:
             self._lbl_duration.setText(f"Duration: {entry.duration:.1f}s")
        else:
             self._lbl_duration.setText("")

    def clear(self) -> None:
        """Reset the view to empty state."""
        self._lbl_timestamp.setText("Select a transcript")
        self._lbl_duration.setText("-")
        self._txt_content.clear()
