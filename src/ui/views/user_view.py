"""
User View implementation.
Contains user-centric, non-mutating informational surfaces:
- Lifetime metrics and explanations
- About Vociferous content
- Help/documentation links
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
    QFrame,
    QScrollArea,
    QPushButton,
    QHBoxLayout,
    QGridLayout,
)

from ui.views.base_view import BaseView
from ui.constants.view_ids import VIEW_USER
from ui.constants import (
    Colors,
    Spacing,
    Typography,
    HISTORY_EXPORT_LIMIT,
    SPEAKING_SPEED_WPM,
    TYPING_SPEED_WPM,
)

if TYPE_CHECKING:
    from history_manager import HistoryManager

import logging
logger = logging.getLogger(__name__)


class UserView(BaseView):
    """
    User view - informational surface for metrics, about, and help.
    
    Contains:
    - Lifetime transcription metrics
    - Metrics calculation explanations
    - About Vociferous information
    - Links to documentation/repository
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("UserView")
        self._history_manager: HistoryManager | None = None
        self._setup_ui()

    def get_view_id(self) -> str:
        return VIEW_USER

    def set_history_manager(self, manager: HistoryManager) -> None:
        """Set history manager and refresh metrics."""
        self._history_manager = manager
        self.refresh_metrics()

    def _setup_ui(self) -> None:
        """Initialize the UI layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Title Bar
        title_bar = self._create_title_bar()
        main_layout.addWidget(title_bar)

        # Scrollable content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setObjectName("userViewScrollArea")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(Spacing.MAJOR_GAP, Spacing.MAJOR_GAP, Spacing.MAJOR_GAP, Spacing.MAJOR_GAP)
        content_layout.setSpacing(Spacing.MAJOR_GAP)

        # Lifetime Metrics Section
        metrics_section = self._create_metrics_section()
        content_layout.addWidget(metrics_section)

        # Divider
        content_layout.addWidget(self._create_divider())

        # Metrics Explanations Section
        explanations_section = self._create_explanations_section()
        content_layout.addWidget(explanations_section)

        # Divider
        content_layout.addWidget(self._create_divider())

        # About Vociferous Section
        about_section = self._create_about_section()
        content_layout.addWidget(about_section)

        content_layout.addStretch()

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area, 1)

    def _create_title_bar(self) -> QWidget:
        """Create title bar with label."""
        title_bar = QWidget()
        title_bar.setObjectName("viewTitleBar")
        title_bar.setFixedHeight(60)
        
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(Spacing.MAJOR_GAP, 0, Spacing.MAJOR_GAP, 0)
        
        title = QLabel("User")
        title.setObjectName("viewTitle")
        layout.addWidget(title)
        layout.addStretch()
        
        return title_bar

    def _create_divider(self) -> QFrame:
        """Create horizontal divider."""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setObjectName("userViewDivider")
        return line

    def _create_metrics_section(self) -> QWidget:
        """Create lifetime metrics section."""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.MINOR_GAP)

        # Header
        header = QLabel("Lifetime Metrics")
        header.setObjectName("sectionHeader")
        header.setStyleSheet(f"font-weight: bold; font-size: {Typography.FONT_SIZE_XL}px;")
        layout.addWidget(header)

        # Metrics grid
        metrics_grid = QGridLayout()
        metrics_grid.setSpacing(Spacing.MINOR_GAP)
        metrics_grid.setColumnStretch(1, 1)

        # Create metric labels (will be populated in refresh_metrics)
        self.metric_labels = {}
        
        metrics = [
            ("total_transcriptions", "Total Transcriptions:"),
            ("total_words", "Total Words:"),
            ("time_spent", "Time Spent Transcribing:"),
            ("time_saved", "Time Saved vs Typing:"),
            ("avg_duration", "Average Transcription:"),
        ]

        for row, (key, label_text) in enumerate(metrics):
            label = QLabel(label_text)
            label.setObjectName("metricLabel")
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            value = QLabel("—")
            value.setObjectName("metricValue")
            value.setStyleSheet(f"font-weight: bold; font-size: {Typography.FONT_SIZE_LG}px;")
            
            metrics_grid.addWidget(label, row, 0)
            metrics_grid.addWidget(value, row, 1)
            
            self.metric_labels[key] = value

        layout.addLayout(metrics_grid)

        return section

    def _create_explanations_section(self) -> QWidget:
        """Create metrics explanations section."""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.MINOR_GAP)

        # Header
        header = QLabel("How Metrics Are Calculated")
        header.setObjectName("sectionHeader")
        header.setStyleSheet(f"font-weight: bold; font-size: {Typography.FONT_SIZE_XL}px;")
        layout.addWidget(header)

        # Explanations
        explanations = [
            ("Total Transcriptions", "The count of all transcription entries in your history."),
            ("Total Words", "Sum of all words across all transcriptions."),
            ("Time Spent Transcribing", 
             f"Calculated from recording durations. If duration is unavailable, estimated at {SPEAKING_SPEED_WPM} words per minute."),
            ("Time Saved vs Typing", 
             f"Difference between estimated typing time ({TYPING_SPEED_WPM} WPM) and actual recording time. "
             "This represents the productivity gain from using speech-to-text."),
            ("Average Transcription", "Mean duration per transcription entry."),
        ]

        for title, explanation in explanations:
            exp_widget = self._create_explanation_block(title, explanation)
            layout.addWidget(exp_widget)

        return section

    def _create_explanation_block(self, title: str, explanation: str) -> QWidget:
        """Create a single explanation block."""
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(2)

        title_label = QLabel(f"• {title}")
        title_label.setObjectName("explanationTitle")
        title_label.setStyleSheet(f"font-weight: bold; font-size: {Typography.FONT_SIZE_MD}px;")
        layout.addWidget(title_label)

        exp_label = QLabel(explanation)
        exp_label.setObjectName("explanationText")
        exp_label.setWordWrap(True)
        exp_label.setStyleSheet(f"margin-left: 20px; color: {Colors.TEXT_SECONDARY};")
        layout.addWidget(exp_label)

        return block

    def _create_about_section(self) -> QWidget:
        """Create About Vociferous section."""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.MINOR_GAP)

        # Header
        header = QLabel("About Vociferous")
        header.setObjectName("sectionHeader")
        header.setStyleSheet(f"font-weight: bold; font-size: {Typography.FONT_SIZE_XL}px;")
        layout.addWidget(header)

        # App title
        title = QLabel("Vociferous")
        title.setObjectName("aboutTitle")
        title.setStyleSheet(f"font-size: {Typography.FONT_SIZE_XXL}px; font-weight: bold; margin-top: 8px;")
        layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("Modern Speech-to-Text for Linux")
        subtitle.setObjectName("aboutSubtitle")
        subtitle.setStyleSheet(f"font-size: {Typography.FONT_SIZE_LG}px; color: {Colors.TEXT_SECONDARY};")
        layout.addWidget(subtitle)

        # Description
        description = QLabel(
            "Vociferous was created to bring seamless, privacy-focused speech-to-text "
            "to the Linux desktop. Built with OpenAI's Whisper model, it runs entirely "
            "locally—no cloud services, no data collection, just fast and accurate "
            "transcription on your own machine."
        )
        description.setWordWrap(True)
        description.setObjectName("aboutDescription")
        description.setStyleSheet("margin-top: 8px;")
        layout.addWidget(description)

        # Creator info
        creator_label = QLabel("Created by Andrew Brown")
        creator_label.setObjectName("aboutCreator")
        creator_label.setStyleSheet("margin-top: 12px; font-weight: bold;")
        layout.addWidget(creator_label)

        # Links
        links_layout = QHBoxLayout()
        links_layout.setSpacing(Spacing.MINOR_GAP)
        links_layout.setContentsMargins(0, 8, 0, 0)

        linkedin_btn = QPushButton("LinkedIn Profile")
        linkedin_btn.setObjectName("secondaryButton")
        linkedin_btn.setFixedHeight(36)
        linkedin_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://www.linkedin.com/in/abrown7521/")
            )
        )
        links_layout.addWidget(linkedin_btn)

        github_btn = QPushButton("GitHub Repository")
        github_btn.setObjectName("secondaryButton")
        github_btn.setFixedHeight(36)
        github_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/WanderingAstronomer/Vociferous")
            )
        )
        links_layout.addWidget(github_btn)

        links_layout.addStretch()
        layout.addLayout(links_layout)

        return section

    def refresh_metrics(self) -> None:
        """Refresh lifetime metrics from history manager."""
        if not self._history_manager:
            # No history manager, show placeholders
            for value_label in self.metric_labels.values():
                value_label.setText("—")
            return

        try:
            entries = self._history_manager.get_recent(limit=HISTORY_EXPORT_LIMIT)

            if not entries:
                self.metric_labels["total_transcriptions"].setText("0")
                self.metric_labels["total_words"].setText("0")
                self.metric_labels["time_spent"].setText("0s")
                self.metric_labels["time_saved"].setText("0s")
                self.metric_labels["avg_duration"].setText("0s")
                return

            count = len(entries)
            total_words = sum(len(entry.text.split()) for entry in entries)

            # Calculate time spent
            recorded_seconds = sum(entry.duration_ms for entry in entries if entry.duration_ms) / 1000
            if recorded_seconds == 0 and total_words > 0:
                # Estimate from word count if duration unavailable
                recorded_seconds = (total_words / SPEAKING_SPEED_WPM) * 60

            # Calculate time saved
            typing_seconds = (total_words / TYPING_SPEED_WPM) * 60
            time_saved_seconds = max(0, typing_seconds - recorded_seconds)

            # Calculate average
            avg_seconds = recorded_seconds / count if count > 0 else 0

            # Update labels
            self.metric_labels["total_transcriptions"].setText(f"{count:,}")
            self.metric_labels["total_words"].setText(f"{total_words:,}")
            self.metric_labels["time_spent"].setText(self._format_duration(recorded_seconds))
            self.metric_labels["time_saved"].setText(self._format_duration(time_saved_seconds))
            self.metric_labels["avg_duration"].setText(self._format_duration(avg_seconds))

        except Exception:
            logger.exception("Failed to refresh metrics in User View")
            for value_label in self.metric_labels.values():
                value_label.setText("Error")

    def _format_duration(self, seconds: float) -> str:
        """Format seconds into human-readable duration."""
        if seconds < 60:
            return f"{int(seconds)}s"
        
        minutes = int(seconds // 60)
        if minutes < 60:
            return f"{minutes}m"
        
        hours = minutes // 60
        remaining_minutes = minutes % 60
        if remaining_minutes == 0:
            return f"{hours}h"
        return f"{hours}h {remaining_minutes}m"

    def cleanup(self) -> None:
        """Clean up resources."""
        super().cleanup()

