"""
User View implementation.
Contains user-centric, non-mutating informational surfaces:
- Lifetime metrics and explanations
- About Vociferous content
- Help/documentation links
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QUrl, pyqtSlot, QSize
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
    QFrame,
    QScrollArea,
    QPushButton,
    QHBoxLayout,
    QSizePolicy,
)

from src.database.signal_bridge import DatabaseSignalBridge
from src.database.events import EntityChange
from src.ui.views.base_view import BaseView
from src.ui.constants.view_ids import VIEW_USER
import src.ui.constants.colors as c
from src.ui.constants import (
    Spacing,
    Typography,
    HISTORY_EXPORT_LIMIT,
    SPEAKING_SPEED_WPM,
    TYPING_SPEED_WPM,
)
from src.core.resource_manager import ResourceManager
from src.ui.contracts.capabilities import Capabilities, SelectionState, ActionId
from src.ui.styles.user_view_styles import get_user_view_stylesheet

if TYPE_CHECKING:
    from src.database.history_manager import HistoryManager

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

    def cleanup(self) -> None:
        """Disconnect global signals."""
        try:
            DatabaseSignalBridge().data_changed.disconnect(self._handle_data_changed)
        except (TypeError, RuntimeError):
            pass
        try:
            from src.core.config_manager import ConfigManager

            ConfigManager.instance().config_changed.disconnect(self._on_config_changed)
        except (TypeError, RuntimeError):
            pass
        super().cleanup()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("UserView")
        self._history_manager: HistoryManager | None = None
        self._title_label: QLabel | None = None
        self._setup_ui()

        # Apply view-specific stylesheet
        self.setStyleSheet(get_user_view_stylesheet())

        # Connect to config changes for name personalization
        from src.core.config_manager import ConfigManager

        ConfigManager.instance().config_changed.connect(self._on_config_changed)

    def get_view_id(self) -> str:
        return VIEW_USER

    def get_capabilities(self) -> Capabilities:
        """User view has no action capabilities (informational-only)."""
        return Capabilities()

    def get_selection(self) -> SelectionState:
        """User view has no selection."""
        return SelectionState()

    def dispatch_action(self, action_id: ActionId) -> None:
        """User view does not handle standard actions."""
        pass

    def set_history_manager(self, manager: HistoryManager) -> None:
        """Set history manager and refresh metrics."""
        self._history_manager = manager
        self.refresh_metrics()

        # Connect to database updates
        DatabaseSignalBridge().data_changed.connect(self._handle_data_changed)

    @pyqtSlot(EntityChange)
    def _handle_data_changed(self, change: EntityChange) -> None:
        """Handle incoming surgical updates from the database."""
        if change.entity_type == "transcription":
            self.refresh_metrics()

    @pyqtSlot(str, str, object)
    def _on_config_changed(self, section: str, key: str, value: object) -> None:
        """Handle config changes, specifically user name updates."""
        if section == "user" and key == "name" and self._title_label:
            # Update the title bar with the new name
            user_name = str(value) if value else ""
            if user_name and user_name.strip():
                new_title = f"{user_name.strip()}'s Vociferous Journey"
            else:
                new_title = "Your Vociferous Journey"
            self._title_label.setText(new_title)

    def _generate_insight(
        self,
        count: int,
        recorded_seconds: float,
        typing_seconds: float,
        avg_duration: float,
    ) -> str:
        """Generate a deterministic insight string based on usage metrics."""
        if count < 3:
            return "Don't be shy! Record a bit more to see your Vociferous metrics!"

        # Calculate efficiency ratio
        ratio = typing_seconds / recorded_seconds if recorded_seconds > 0 else 0

        if ratio > 2.5:
            return f"Speaking {ratio:.1f}x faster than typing—voice is your superpower!"
        elif ratio > 1.5:
            return "Dictation is significantly faster than typing for you! You're a certified yapper~"

        # Analyze session style
        if avg_duration < 15:
            return "Quick-capture style: rapid-fire notes and thoughts. Keep that momentum going!"
        elif avg_duration > 60:
            return "Deep-work style: long-form dictation sessions. Now that's what I'd call elite comms!"

        return "Consistent dictation is key—keep up the great work!"

    def _create_insight_row(self) -> QWidget:
        """Create the insight text row."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self.insight_label = QLabel("Analyzing usage patterns...")
        self.insight_label.setObjectName("insightText")
        self.insight_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.insight_label.setWordWrap(True)

        layout.addWidget(self.insight_label)
        return container

    def _create_empty_state(self) -> QWidget:
        """Create the empty state onboarding card."""
        card = QFrame()
        card.setObjectName("emptyStateCard")
        # Style defined in user_view_styles.py

        layout = QVBoxLayout(card)
        layout.setContentsMargins(
            Spacing.MAJOR_GAP * 2,
            Spacing.MAJOR_GAP * 2,
            Spacing.MAJOR_GAP * 2,
            Spacing.MAJOR_GAP * 2,
        )
        layout.setSpacing(Spacing.MAJOR_GAP)

        title = QLabel("No metrics yet")
        title.setObjectName("emptyStateTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "Metrics appear after your first transcription is saved.\n"
            "Try making a recording to see your impact."
        )
        desc.setObjectName("emptyStateDescription")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # desc.setWordWrap(True) # Newlines manually added for balance
        layout.addWidget(desc)

        return card

    def _setup_ui(self) -> None:
        """Initialize the UI layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Title Bar
        title_bar = self._create_title_bar()
        main_layout.addWidget(title_bar)

        # Divider after title bar
        main_layout.addWidget(self._create_divider())

        # Scrollable content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setObjectName("userViewScrollArea")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Center everything in a fixed-width container
        content_layout.addStretch()

        # Centered container with fixed width
        center_container = QWidget()
        center_container.setMinimumWidth(800)
        center_container.setMaximumWidth(1200)
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(
            Spacing.MAJOR_GAP,
            Spacing.MAJOR_GAP * 2,
            Spacing.MAJOR_GAP,
            Spacing.MAJOR_GAP * 2,
        )
        center_layout.setSpacing(Spacing.MAJOR_GAP * 2)

        # 1. Stats Container (Metrics + Dividers + Explanations)
        self.stats_container = QWidget()
        stats_layout = QVBoxLayout(self.stats_container)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(Spacing.MAJOR_GAP * 2)

        metrics_section = self._create_metrics_section()
        stats_layout.addWidget(metrics_section)

        stats_layout.addWidget(self._create_divider())

        # Methodology (Collapsible)
        explanations_section = self._create_explanations_section()
        stats_layout.addWidget(explanations_section)

        center_layout.addWidget(self.stats_container)

        # 3. Empty State Container (Hidden by default)
        self.empty_state_container = self._create_empty_state()
        self.empty_state_container.setVisible(False)
        center_layout.addWidget(self.empty_state_container)

        # 4. Divider before footer
        center_layout.addSpacing(Spacing.MAJOR_GAP * 2)
        center_layout.addWidget(self._create_divider())
        center_layout.addSpacing(Spacing.MAJOR_GAP * 2)

        # 5. Footer
        about_section = self._create_about_section()
        center_layout.addWidget(about_section)

        # Add centered container to content layout
        h_layout = QHBoxLayout()
        h_layout.addStretch()
        h_layout.addWidget(center_container)
        h_layout.addStretch()
        content_layout.addLayout(h_layout)
        content_layout.addStretch()

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area, 1)

    def _create_title_bar(self) -> QWidget:
        """Create title bar with label."""
        title_bar = QWidget()
        title_bar.setObjectName("viewTitleBar")
        title_bar.setFixedHeight(80)

        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(Spacing.MAJOR_GAP, 0, Spacing.MAJOR_GAP, 0)

        # Get personalized name from config
        from src.core.config_manager import ConfigManager

        user_name = ConfigManager.get_config_value("user", "name")
        if user_name and isinstance(user_name, str) and user_name.strip():
            title_text = f"{user_name.strip()}'s Vociferous Journey"
        else:
            title_text = "Your Vociferous Journey"

        self._title_label = QLabel(title_text)
        self._title_label.setObjectName("viewTitle")
        self._title_label.setStyleSheet(
            f"font-size: {Typography.FONT_SIZE_XXL}px; font-weight: bold; color: {c.BLUE_4}; border: none;"
        )
        layout.addWidget(self._title_label, 0, Qt.AlignmentFlag.AlignCenter)

        return title_bar

    def _create_divider(self) -> QFrame:
        """Create horizontal divider."""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setObjectName("userViewDivider")
        return line

    def _create_metrics_section(self) -> QWidget:
        """Create lifetime metrics section with grouped layout."""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.MAJOR_GAP * 2)

        # Header (Centered, no badge)
        header = QLabel("Lifetime Statistics")
        header.setObjectName("sectionHeader")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(
            f"font-weight: bold; font-size: {Typography.FONT_SIZE_XXL}px;"
        )
        layout.addWidget(header)

        # Insight/Tagline as subheader
        layout.addWidget(self._create_insight_row())
        layout.addSpacing(Spacing.MINOR_GAP)

        self.metric_labels: dict[str, QLabel] = {}

        # Group 1: Productivity (Headline)
        prod_group = self._create_metric_group("Productivity Impact")

        row1 = QHBoxLayout()
        row1.setSpacing(Spacing.MAJOR_GAP)

        card_saved = self._create_metric_card(
            "time_saved",
            "Time Saved",
            "vs manual typing",
            icon_name="user_view-time_saved",
            highlight=True,
        )
        card_words = self._create_metric_card(
            "total_words",
            "Words Captured",
            "Total transcribed words",
            icon_name="user_view-words_captured",
            highlight=True,
        )

        row1.addWidget(card_saved)
        row1.addWidget(card_words)
        prod_group.layout().addLayout(row1)
        layout.addWidget(prod_group)

        # Group 2: Usage & Activity
        usage_group = self._create_metric_group("Usage & Activity")

        row2 = QHBoxLayout()
        row2.setSpacing(Spacing.MAJOR_GAP)

        card_count = self._create_metric_card(
            "total_transcriptions",
            "Transcriptions",
            "Total recordings",
            icon_name="user_view-transcriptions",
        )
        card_time = self._create_metric_card(
            "time_spent",
            "Time Recorded",
            "Total audio duration",
            icon_name="user_view-time_recorded",
        )
        card_avg = self._create_metric_card(
            "avg_duration",
            "Avg. Length",
            "Per recording",
            icon_name="user_view-avg_length",
        )
        card_total_silence = self._create_metric_card(
            "total_silence",
            "Total Silence",
            "Accumulated pauses",
            icon_name="user_view-total_silence",
        )

        row2.addWidget(card_count)
        row2.addWidget(card_time)
        row2.addWidget(card_avg)
        row2.addWidget(card_total_silence)

        usage_group.layout().addLayout(row2)
        layout.addWidget(usage_group)

        # Group 3: Speech Quality
        quality_group = self._create_metric_group("Speech Quality")

        row3 = QHBoxLayout()
        row3.setSpacing(Spacing.MAJOR_GAP)

        card_complexity = self._create_metric_card(
            "lexical_complexity",
            "Vocabulary",
            "Unique words ratio",
            icon_name="user_view-vocabulary",
        )
        card_silence = self._create_metric_card(
            "avg_silence",
            "Avg. Pauses",
            "Silence between speech",
            icon_name="user_view-pauses",
        )
        card_fillers = self._create_metric_card(
            "filler_count",
            "Filler Words",
            "um, uh, like, you know",
            icon_name="user_view-filler_words",
        )

        row3.addWidget(card_complexity)
        row3.addWidget(card_silence)
        row3.addWidget(card_fillers)

        quality_group.layout().addLayout(row3)
        layout.addWidget(quality_group)

        return section

    def _create_metric_group(self, title: str) -> QWidget:
        """Create a titled grouping container."""
        group = QWidget()
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.MINOR_GAP)

        label = QLabel(title)
        label.setStyleSheet(
            f"font-weight: 600; font-size: {Typography.FONT_SIZE_MD}px; "
            f"color: {c.GRAY_4}; text-transform: uppercase; letter-spacing: 0.5px;"
        )
        label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(label)
        return group

    def _create_metric_card(
        self,
        key: str,
        title: str,
        description: str,
        icon_name: str | None = None,
        highlight: bool = False,
    ) -> QWidget:
        """Create a styled metric card."""
        card = QFrame()
        card.setObjectName("metricCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(
            Spacing.MAJOR_GAP, Spacing.MAJOR_GAP, Spacing.MAJOR_GAP, Spacing.MAJOR_GAP
        )
        card_layout.setSpacing(4)

        # Icon (Optional, tertiary)
        if icon_name:
            icon_label = QLabel()
            icon_label.setObjectName("metricIcon")
            icon_path = ResourceManager.get_icon_path(icon_name)
            if icon_path:
                icon_label.setPixmap(QIcon(icon_path).pixmap(QSize(48, 48)))
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignCenter)
            card_layout.addSpacing(4)

        # Value (large and prominent)
        value_size = 48 if highlight else Typography.FONT_SIZE_LG
        value_color = c.BLUE_4 if highlight else c.GRAY_0

        value = QLabel("—")
        value.setObjectName("metricValue")
        value.setStyleSheet(
            f"font-weight: bold; font-size: {value_size}px; color: {value_color};"
        )
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(value, 0, Qt.AlignmentFlag.AlignHCenter)

        # Title
        title_label = QLabel(title)
        title_label.setObjectName("metricTitle")
        title_label.setStyleSheet(
            f"font-weight: 600; font-size: {Typography.FONT_SIZE_MD}px; margin-top: 4px;"
        )
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title_label)

        # Description
        desc_label = QLabel(description)
        desc_label.setObjectName("metricDescription")
        # Style defined in user_view_styles.py
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(desc_label)

        self.metric_labels[key] = value

        return card

    def _create_explanations_section(self) -> QWidget:
        """Create metrics explanations section with collapsible details."""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.MINOR_GAP)

        # Toggle Button (Header)
        self.toggle_btn = QPushButton("Show Calculation Details ▸")
        self.toggle_btn.setObjectName("collapseButton")
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._toggle_explanations)
        layout.addWidget(self.toggle_btn, 0, Qt.AlignmentFlag.AlignCenter)

        # Container for all explanations (Collapsible)
        self.explanations_container = QWidget()
        self.explanations_container.setVisible(False)
        explanations_layout = QVBoxLayout(self.explanations_container)
        explanations_layout.setContentsMargins(
            Spacing.MAJOR_GAP, Spacing.MAJOR_GAP, Spacing.MAJOR_GAP, 0
        )
        explanations_layout.setSpacing(Spacing.MINOR_GAP)

        explanations = [
            (
                "Transcriptions",
                "Total count of all transcription entries stored in your history database.",
            ),
            (
                "Words Captured",
                "Sum of word counts across all transcriptions. Each entry's words are counted individually.",
            ),
            (
                "Time Recording",
                f"Total recording duration in seconds. If duration is unavailable, estimated as:<br>"
                f"<code>words ÷ {SPEAKING_SPEED_WPM} WPM × 60 = seconds</code>",
            ),
            (
                "Time Saved",
                f"Productivity gain vs. manual typing. Calculated as:<br>"
                f"<code>(words ÷ {TYPING_SPEED_WPM} WPM × 60) − recording_time = time_saved</code><br>"
                f"Based on average typing speed of {TYPING_SPEED_WPM} WPM.",
            ),
            (
                "Average Length",
                "Mean duration per transcription: <code>total_time ÷ transcription_count</code>",
            ),
            (
                "Total Silence",
                f"Total accumulated silence (pauses) across all recordings. Calculated by summing the difference between "
                f"actual recording duration and expected speech time for each entry. "
                f"<code>total_silence = Σ max(0, actual_duration - (word_count ÷ {SPEAKING_SPEED_WPM} × 60))</code>",
            ),
            (
                "Vocabulary",
                "Lexical complexity calculated as the ratio of unique words to total words across all transcriptions. "
                "Higher percentages indicate more diverse vocabulary usage. "
                "Words are normalized to lowercase and punctuation is stripped before counting.",
            ),
            (
                "Average Pauses",
                f"Estimated average silence per recording based on word density. Calculated by comparing actual recording duration "
                f"against expected speech time (based on {SPEAKING_SPEED_WPM} WPM). The difference represents pauses and silence. "
                f"<code>silence = max(0, actual_duration - (word_count ÷ {SPEAKING_SPEED_WPM} × 60))</code>",
            ),
            (
                "Filler Words",
                "Total count of common filler words and phrases detected across all transcriptions. Includes patterns like 'um', 'uh', "
                "'like', 'you know', 'basically', 'literally', 'actually', 'so', 'well', 'right', 'okay', 'i mean', 'kind of', and 'sort of'. "
                "Helps identify speech clarity and confidence patterns.",
            ),
        ]

        # Create simple centered text blocks for each explanation
        for title, explanation in explanations:
            # Create rich text label
            text = f"<b>{title}</b><br><span style='color: {c.GRAY_4};'>{explanation}</span>"
            label = QLabel(text)
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            label.setStyleSheet(
                f"font-size: {Typography.FONT_SIZE_MD}px; padding: {Spacing.MINOR_GAP}px 0px;"
            )
            explanations_layout.addWidget(label)

        layout.addWidget(self.explanations_container)

        return section

    def _toggle_explanations(self) -> None:
        """Toggle visibility of explanations."""
        visible = not self.explanations_container.isVisible()
        self.explanations_container.setVisible(visible)
        text = "Hide Calculation Details ▾" if visible else "Show Calculation Details ▸"
        self.toggle_btn.setText(text)

    def _create_explanation_block(self, title: str, explanation: str) -> QWidget:
        """DEPRECATED: Replaced by simple rich-text labels in _create_explanations_section."""
        block = QFrame()
        block.setObjectName("explanationCard")
        block.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(block)
        layout.setContentsMargins(
            Spacing.MAJOR_GAP, Spacing.MINOR_GAP, Spacing.MAJOR_GAP, Spacing.MINOR_GAP
        )
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("explanationTitle")
        title_label.setStyleSheet(
            f"font-weight: 600; font-size: {Typography.FONT_SIZE_MD}px;"
        )
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        exp_label = QLabel(explanation)
        exp_label.setObjectName("explanationText")
        exp_label.setWordWrap(True)
        exp_label.setStyleSheet(
            f"color: {c.GRAY_4}; font-size: {Typography.FONT_SIZE_SM}px; line-height: 1.4;"
        )
        exp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(exp_label)

        return block

    def _create_about_section(self) -> QWidget:
        """Create About Vociferous section (Footer)."""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.MAJOR_GAP)

        # Content in a centered container
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(
            Spacing.MAJOR_GAP, 0, Spacing.MAJOR_GAP, Spacing.MAJOR_GAP
        )
        content_layout.setSpacing(Spacing.MINOR_GAP)

        # Footer Title
        title = QLabel("Vociferous")
        title.setObjectName("aboutTitle")
        # Style moved to stylesheet
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(title)

        # Version/Tagline
        subtitle = QLabel("Local AI Speech to Text")
        subtitle.setObjectName("aboutSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(subtitle)

        content_layout.addSpacing(Spacing.MINOR_GAP)

        # Description (Expanded, Footer style)
        description = QLabel(
            "Powered by Faster Whisper and Qwen3. A fully local, privacy-first speech-to-text solution "
            "that runs entirely on your machine. No cloud dependencies, no data collection, no internet required. "
            "Enjoy fast, accurate transcription with AI-powered text refinement—all while keeping your voice data completely private."
        )
        description.setWordWrap(True)
        description.setObjectName("aboutDescription")
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(description)

        content_layout.addSpacing(Spacing.MAJOR_GAP)

        # Links in a horizontal centered layout
        links_container = QWidget()
        links_layout = QHBoxLayout(links_container)
        links_layout.setSpacing(Spacing.MAJOR_GAP)
        links_layout.setContentsMargins(0, 0, 0, 0)
        links_layout.addStretch()

        linkedin_btn = QPushButton("LinkedIn")
        linkedin_btn.setObjectName("secondaryButton")
        linkedin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        linkedin_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://www.linkedin.com/in/abrown7521/")
            )
        )
        links_layout.addWidget(linkedin_btn)

        github_btn = QPushButton("GitHub")
        github_btn.setObjectName("secondaryButton")
        github_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        github_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/WanderingAstronomer/Vociferous")
            )
        )
        links_layout.addWidget(github_btn)

        links_layout.addStretch()
        content_layout.addWidget(links_container)

        # Creator info at very bottom
        content_layout.addSpacing(Spacing.MINOR_GAP)
        creator_label = QLabel("Created by Andrew Brown")
        creator_label.setObjectName("aboutCreator")
        creator_label.setStyleSheet(f"color: {c.BLUE_3};")
        creator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(creator_label)

        layout.addWidget(content_container)

        return section

    def refresh_metrics(self) -> None:
        """Refresh lifetime metrics from history manager."""
        if not self._history_manager:
            return

        try:
            entries = self._history_manager.get_recent(limit=HISTORY_EXPORT_LIMIT)

            if not entries:
                # Empty State
                self.stats_container.setVisible(False)
                self.insight_label.setVisible(False)
                self.empty_state_container.setVisible(True)
                return

            # Has Data
            self.stats_container.setVisible(True)
            self.insight_label.setVisible(True)
            self.empty_state_container.setVisible(False)

            count = len(entries)
            total_words = sum(len(entry.text.split()) for entry in entries)

            # Calculate time spent
            recorded_seconds = (
                sum(entry.duration_ms for entry in entries if entry.duration_ms) / 1000
            )
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
            self.metric_labels["time_spent"].setText(
                self._format_duration(recorded_seconds)
            )
            self.metric_labels["time_saved"].setText(
                self._format_duration(time_saved_seconds)
            )
            self.metric_labels["avg_duration"].setText(
                self._format_duration(avg_seconds)
            )

            # Calculate new Speech Quality metrics
            lexical_complexity = self._calculate_lexical_complexity(entries)
            avg_silence = self._calculate_avg_silence(entries)
            total_silence = self._calculate_total_silence(entries)
            filler_count = self._count_filler_words(entries)

            # Update new metric labels
            self.metric_labels["lexical_complexity"].setText(
                f"{lexical_complexity:.0%}" if lexical_complexity > 0 else "—"
            )
            self.metric_labels["avg_silence"].setText(
                self._format_duration(avg_silence) if avg_silence > 0 else "—"
            )
            self.metric_labels["total_silence"].setText(
                self._format_duration(total_silence) if total_silence > 0 else "—"
            )
            self.metric_labels["filler_count"].setText(
                f"{filler_count:,}" if filler_count > 0 else "—"
            )

            # Generate deterministic insight
            msg = self._generate_insight(
                count, recorded_seconds, typing_seconds, avg_seconds
            )
            self.insight_label.setText(msg)

        except Exception:
            logger.exception("Failed to refresh metrics in User View")
            for value_label in self.metric_labels.values():
                value_label.setText("Error")

    def _calculate_lexical_complexity(self, entries: list) -> float:
        """Calculate lexical complexity as ratio of unique words to total words."""
        all_words: list[str] = []
        for entry in entries:
            words = entry.text.lower().split()
            # Strip punctuation
            cleaned = [w.strip(".,!?;:'\"()[]{}") for w in words]
            all_words.extend([w for w in cleaned if w])

        if not all_words:
            return 0.0

        unique_words = set(all_words)
        return len(unique_words) / len(all_words)

    def _calculate_avg_silence(self, entries: list) -> float:
        """Estimate average silence per recording based on word density."""
        total_silence = 0.0
        count_with_duration = 0

        for entry in entries:
            if entry.duration_ms and entry.duration_ms > 0:
                duration_sec = entry.duration_ms / 1000
                word_count = len(entry.text.split())
                # Speaking rate ~150 WPM, so expected speech time:
                expected_speech_sec = (word_count / SPEAKING_SPEED_WPM) * 60
                # Silence is the difference (if duration > expected)
                silence = max(0, duration_sec - expected_speech_sec)
                total_silence += silence
                count_with_duration += 1

        if count_with_duration == 0:
            return 0.0

        return total_silence / count_with_duration

    def _calculate_total_silence(self, entries: list) -> float:
        """Calculate total accumulated silence across all recordings."""
        total_silence = 0.0

        for entry in entries:
            if entry.duration_ms and entry.duration_ms > 0:
                duration_sec = entry.duration_ms / 1000
                word_count = len(entry.text.split())
                # Speaking rate ~150 WPM, so expected speech time:
                expected_speech_sec = (word_count / SPEAKING_SPEED_WPM) * 60
                # Silence is the difference (if duration > expected)
                silence = max(0, duration_sec - expected_speech_sec)
                total_silence += silence

        return total_silence

    def _count_filler_words(self, entries: list) -> int:
        """Count common filler words across all transcripts."""
        filler_patterns = {
            "um",
            "uh",
            "uhm",
            "umm",
            "er",
            "err",
            "like",
            "you know",
            "basically",
            "literally",
            "actually",
            "so",
            "well",
            "right",
            "okay",
            "i mean",
            "kind of",
            "sort of",
        }
        # Single-word fillers
        single_fillers = {f for f in filler_patterns if " " not in f}
        # Multi-word fillers
        multi_fillers = [f for f in filler_patterns if " " in f]

        total_count = 0

        for entry in entries:
            text_lower = entry.text.lower()
            # Count multi-word fillers
            for filler in multi_fillers:
                total_count += text_lower.count(filler)
            # Count single-word fillers
            words = text_lower.split()
            for word in words:
                cleaned = word.strip(".,!?;:'\"()[]{}").lower()
                if cleaned in single_fillers:
                    total_count += 1

        return total_count

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
