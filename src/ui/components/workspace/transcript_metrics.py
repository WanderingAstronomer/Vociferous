"""
TranscriptMetrics - Display comprehensive recording metrics above transcript text.

Shows multiple time-based metrics following the measurement framework:
- Raw Duration: Total recording time (human cognitive time: speaking + thinking)
- Speech Duration: Effective speech time after VAD filtering
- Silence Ratio: Proportion of time spent thinking/pausing
- Words Per Minute: Idea throughput rate
- Typing Time Saved: Time saved vs manual typing (with explicit assumption)
"""

from __future__ import annotations

from PyQt6.QtWidgets import QGridLayout, QLabel, QWidget

from ui.constants import Colors, Typography

# Constants for time estimation (explicit assumptions)
SPEAKING_SPEED_WPM = 150  # Average conversational speaking speed
TYPING_SPEED_WPM = 40  # Average typing speed for composition


class TranscriptMetrics(QWidget):
    """
    Displays comprehensive metrics for a single transcript.
    
    Implements multi-metric framework:
    - Human time (raw duration with pauses)
    - Machine time (speech duration after VAD)
    - Derived metrics (silence ratio, WPM, time saved)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("transcriptMetrics")
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create the metrics grid layout."""
        layout = QGridLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setHorizontalSpacing(24)
        layout.setVerticalSpacing(8)

        # Row 0: Primary metrics
        # Column 0: Raw Duration
        self.raw_duration_label = self._create_metric_label("Recording Time:")
        self.raw_duration_value = self._create_value_label("0s")
        layout.addWidget(self.raw_duration_label, 0, 0)
        layout.addWidget(self.raw_duration_value, 0, 1)

        # Column 2: Speech Duration
        self.speech_duration_label = self._create_metric_label("Speech Duration:")
        self.speech_duration_value = self._create_value_label("0s")
        layout.addWidget(self.speech_duration_label, 0, 2)
        layout.addWidget(self.speech_duration_value, 0, 3)
        self.speech_duration_label.hide()
        self.speech_duration_value.hide()

        # Column 4: Silence Time (absolute pause/thinking time)
        self.silence_time_label = self._create_metric_label("Silence Time:")
        self.silence_time_value = self._create_value_label("0s")
        layout.addWidget(self.silence_time_label, 0, 4)
        layout.addWidget(self.silence_time_value, 0, 5)
        self.silence_time_label.hide()
        self.silence_time_value.hide()

        # Row 1: Derived metrics
        # Column 0: Words Per Minute
        self.wpm_label = self._create_metric_label("Words/Min:")
        self.wpm_value = self._create_value_label("0")
        layout.addWidget(self.wpm_label, 1, 0)
        layout.addWidget(self.wpm_value, 1, 1)

        # Column 2: Time Saved
        self.saved_label = self._create_metric_label("Typing-Equivalent Time Saved:")
        self.saved_label.setToolTip("Compared to typing at 40 WPM (see Help → Metrics Calculations)")
        self.saved_value = self._create_value_label("0s")
        layout.addWidget(self.saved_label, 1, 2)
        layout.addWidget(self.saved_value, 1, 3)

        # Column 4: Speaking Rate (WPM during active speech)
        self.speaking_rate_label = self._create_metric_label("Speaking Rate:")
        self.speaking_rate_value = self._create_value_label("--")
        layout.addWidget(self.speaking_rate_label, 1, 4)
        layout.addWidget(self.speaking_rate_value, 1, 5)
        self.speaking_rate_label.hide()
        self.speaking_rate_value.hide()

        # Make columns expand proportionally
        for col in range(6):
            layout.setColumnStretch(col, 1)

    def _create_metric_label(self, text: str) -> QLabel:
        """Create a label for the metric name (gray)."""
        label = QLabel(text)
        label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: {Typography.FONT_SIZE_SM}px;")
        return label

    def _create_value_label(self, text: str) -> QLabel:
        """Create a label for the metric value (white)."""
        label = QLabel(text)
        label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: {Typography.FONT_SIZE_SM}px; font-weight: {Typography.FONT_WEIGHT_EMPHASIS};")
        return label

    def set_metrics(
        self,
        raw_duration_ms: int,
        speech_duration_ms: int | None,
        word_count: int
    ) -> None:
        """
        Update metrics display with comprehensive framework.
        
        Args:
            raw_duration_ms: Total recording duration (human cognitive time)
            speech_duration_ms: Effective speech duration after VAD (or None if not available)
            word_count: Number of words in transcript
        """
        raw_duration_seconds = raw_duration_ms / 1000
        speech_duration_seconds = (speech_duration_ms / 1000) if speech_duration_ms else 0

        # Primary Metric 1: Raw Duration (human cognitive time)
        self.raw_duration_value.setText(self._format_duration(raw_duration_seconds))

        # Primary Metric 2: Speech Duration (after VAD filtering)
        if speech_duration_ms and speech_duration_ms > 0:
            self.speech_duration_value.setText(self._format_duration(speech_duration_seconds))
            self.speech_duration_label.setVisible(True)
            self.speech_duration_value.setVisible(True)
            
            # Also show Silence Time (absolute thinking/pause time)
            silence_seconds = raw_duration_seconds - speech_duration_seconds
            self.silence_time_value.setText(self._format_duration(silence_seconds))
            self.silence_time_label.setVisible(True)
            self.silence_time_value.setVisible(True)
        else:
            self.speech_duration_label.setVisible(False)
            self.speech_duration_value.setVisible(False)
            self.silence_time_label.setVisible(False)
            self.silence_time_value.setVisible(False)

        # Derived Metric 2: Words Per Cognitive Minute (idea throughput)
        if raw_duration_seconds > 0:
            wpm = (word_count / raw_duration_seconds) * 60
            self.wpm_value.setText(f"{wpm:.0f}")
        else:
            self.wpm_value.setText("0")

        # Derived Metric 3: Typing-Equivalent Time Saved
        typing_seconds = (word_count / TYPING_SPEED_WPM) * 60
        time_saved_seconds = max(0, typing_seconds - raw_duration_seconds)
        self.saved_value.setText(self._format_duration(time_saved_seconds))

        # Derived Metric 4: Speaking Rate (WPM during active speech, excluding pauses)
        if speech_duration_seconds > 0 and speech_duration_ms and speech_duration_ms > 0:
            speaking_rate = (word_count / speech_duration_seconds) * 60
            self.speaking_rate_value.setText(f"{speaking_rate:.0f} WPM")
            self.speaking_rate_label.setVisible(True)
            self.speaking_rate_value.setVisible(True)
        else:
            self.speaking_rate_label.setVisible(False)
            self.speaking_rate_value.setVisible(False)

    def _format_duration(self, seconds: float) -> str:
        """Format seconds into human-readable duration."""
        if seconds < 60:
            return f"{int(seconds)}s"

        minutes = seconds / 60
        if minutes < 60:
            remaining_secs = int(seconds % 60)
            if remaining_secs > 0:
                return f"{int(minutes)}m {remaining_secs}s"
            return f"{int(minutes)}m"

        hours = minutes / 60
        remaining_mins = int(minutes % 60)
        if remaining_mins > 0:
            return f"{int(hours)}h {remaining_mins}m"
        return f"{int(hours)}h"

    def clear(self) -> None:
        """Reset metrics to zero."""
        self.raw_duration_value.setText("0s")
        self.speech_duration_value.setText("0s")
        self.silence_time_value.setText("0s")
        self.wpm_value.setText("0")
        self.saved_value.setText("0s")
        self.speaking_rate_value.setText("--")
        self.speech_duration_label.hide()
        self.speech_duration_value.hide()
        self.silence_time_label.hide()
        self.silence_time_value.hide()
        self.speaking_rate_label.hide()
        self.speaking_rate_value.hide()
