"""
Metrics strip widget for Vociferous.

Thin bottom bar showing usage statistics.
Collapsible to save space.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from ui.constants import (
    HISTORY_EXPORT_LIMIT,
    METRICS_BLOCK_PADDING,
    METRICS_DIVIDER_INSET,
    METRICS_DIVIDER_WIDTH,
    METRICS_STRIP_HEIGHT_COLLAPSED,
    METRICS_STRIP_HEIGHT_EXPANDED,
    METRICS_STRIP_PADDING_H,
    SPEAKING_SPEED_WPM,
    TYPING_SPEED_WPM,
)

if TYPE_CHECKING:
    from history_manager import HistoryManager


class MetricBlock(QWidget):
    """A single metric display with label and value."""

    def __init__(
        self, label: str, value: str = "—", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._setup_ui(label, value)

    def _setup_ui(self, label: str, value: str) -> None:
        """Create horizontal layout with label: value on one line."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(METRICS_BLOCK_PADDING, 0, METRICS_BLOCK_PADDING, 0)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.label = QLabel(f"{label}:")
        self.label.setObjectName("metricLabel")

        self.value = QLabel(value)
        self.value.setObjectName("metricValue")

        layout.addWidget(self.label)
        layout.addWidget(self.value)

    def set_value(self, value: str) -> None:
        """Update the displayed value."""
        self.value.setText(value)


class MetricDivider(QFrame):
    """Vertical divider between metric blocks."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.VLine)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self.setFixedWidth(METRICS_DIVIDER_WIDTH)
        self.setContentsMargins(0, METRICS_DIVIDER_INSET, 0, METRICS_DIVIDER_INSET)
        self.setObjectName("metricDivider")


class MetricsStrip(QWidget):
    """
    Bottom metrics strip showing usage statistics.

    Displays:
    - Time spent recording
    - Time saved (estimated)
    - Total transcriptions
    - Total words

    Can be collapsed to a slim grab handle.
    """

    collapsedChanged = pyqtSignal(bool)

    def __init__(
        self,
        history_manager: HistoryManager | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("metricsStrip")

        self._history_manager = history_manager
        self._collapsed = False

        # Styles are applied at app level via generate_unified_stylesheet()

        self._setup_ui()
        self._update_metrics()

    def _setup_ui(self) -> None:
        """Create metrics strip layout."""
        self.setFixedHeight(METRICS_STRIP_HEIGHT_EXPANDED)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            METRICS_STRIP_PADDING_H, 0, METRICS_STRIP_PADDING_H, 0
        )
        layout.setSpacing(0)

        # Collapsed label (shows when collapsed)
        self.collapsed_label = QLabel("Click to show metrics")
        self.collapsed_label.setObjectName("metricsCollapsed")
        self.collapsed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.collapsed_label.hide()
        layout.addWidget(self.collapsed_label)

        # Metrics container - evenly spaced with equal widths
        self.metrics_container = QWidget()
        metrics_layout = QHBoxLayout(self.metrics_container)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(0)

        # Time spent transcribing
        self.time_spent = MetricBlock("Time Spent Transcribing", "0m")
        metrics_layout.addWidget(self.time_spent, 1)

        # Time saved transcribing
        self.time_saved = MetricBlock("Time Saved by Transcribing", "0m")
        metrics_layout.addWidget(self.time_saved, 1)

        # Total transcriptions
        self.transcription_count = MetricBlock("Total Transcriptions", "0")
        metrics_layout.addWidget(self.transcription_count, 1)

        # Total word count
        self.word_count = MetricBlock("Total Transcription Word Count", "0")
        metrics_layout.addWidget(self.word_count, 1)

        layout.addWidget(self.metrics_container, 1)

    def mousePressEvent(self, event) -> None:
        """Make entire strip clickable to toggle collapse."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_collapse()
            event.accept()
        else:
            super().mousePressEvent(event)

    def set_history_manager(self, manager: HistoryManager) -> None:
        """Set history manager and update metrics."""
        self._history_manager = manager
        self._update_metrics()

    def _update_metrics(self) -> None:
        """Refresh metrics from history manager."""
        if not self._history_manager:
            return

        entries = self._history_manager.get_recent(limit=HISTORY_EXPORT_LIMIT)

        if not entries:
            self.time_spent.set_value("0m")
            self.time_saved.set_value("0m")
            self.transcription_count.set_value("0")
            self.word_count.set_value("0")
            return

        count = len(entries)
        total_words = sum(len(entry.text.split()) for entry in entries)

        recorded_seconds = (
            sum(entry.duration_ms for entry in entries if entry.duration_ms) / 1000
        )

        if recorded_seconds == 0 and total_words > 0:
            recorded_seconds = (total_words / SPEAKING_SPEED_WPM) * 60

        typing_seconds = (total_words / TYPING_SPEED_WPM) * 60
        time_saved_seconds = max(0, typing_seconds - recorded_seconds)

        self.time_spent.set_value(self._format_duration(recorded_seconds))
        self.time_saved.set_value(self._format_duration(time_saved_seconds))
        self.transcription_count.set_value(f"{count:,}")
        self.word_count.set_value(f"{total_words:,}")

    def _format_duration(self, seconds: float) -> str:
        """Format seconds into human-readable duration."""
        if seconds < 60:
            return f"{int(seconds)}s"

        minutes = seconds / 60
        if minutes < 60:
            return f"{int(minutes)}m"

        hours = minutes / 60
        if hours < 24:
            remaining_mins = int(minutes % 60)
            if remaining_mins > 0:
                return f"{int(hours)}h {remaining_mins}m"
            return f"{int(hours)}h"

        days = int(hours / 24)
        return f"{days}d"

    def toggle_collapse(self) -> None:
        """Toggle between expanded and collapsed states."""
        self._collapsed = not self._collapsed

        if self._collapsed:
            self.setFixedHeight(METRICS_STRIP_HEIGHT_COLLAPSED)
            self.metrics_container.hide()
            self.collapsed_label.show()
        else:
            self.setFixedHeight(METRICS_STRIP_HEIGHT_EXPANDED)
            self.metrics_container.show()
            self.collapsed_label.hide()

        self.collapsedChanged.emit(self._collapsed)

    def is_collapsed(self) -> bool:
        """Return current collapsed state."""
        return self._collapsed

    def set_collapsed(self, collapsed: bool) -> None:
        """Set collapsed state without animation."""
        if self._collapsed != collapsed:
            self.toggle_collapse()

    def refresh(self) -> None:
        """Refresh metrics (call after new transcriptions)."""
        self._update_metrics()
