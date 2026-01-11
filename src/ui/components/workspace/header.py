"""
WorkspaceHeader - Header area showing greeting, status, or timestamp.

Includes pulse animation for recording state.
"""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QPropertyAnimation
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QGraphicsOpacityEffect,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui.constants import Spacing, Timing, Typography, WorkspaceState


def _get_greeting() -> str:
    """Return time-of-day greeting."""
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    elif hour < 17:
        return "Good afternoon"
    else:
        return "Good evening"


class WorkspaceHeader(QWidget):
    """
    Header area showing greeting, status, or timestamp.

    Includes pulse animation for recording state.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = WorkspaceState.IDLE
        self._current_timestamp = ""
        self._pulse_direction = True

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create header layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, Spacing.GREETING_TOP, 0, 0)
        layout.setSpacing(8)

        # Greeting line (centered)
        self.greeting_label = QLabel()
        self.greeting_label.setObjectName("greetingLabel")
        self.greeting_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(Typography.FONT_SIZE_MD)
        font.setWeight(QFont.Weight.DemiBold)
        self.greeting_label.setFont(font)

        # Pulse animation for recording state
        self._opacity_effect = QGraphicsOpacityEffect(self.greeting_label)
        self.greeting_label.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(1.0)

        self._pulse_animation = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._pulse_animation.setDuration(Timing.PULSE_CYCLE_MS)
        self._pulse_animation.setStartValue(1.0)
        self._pulse_animation.setEndValue(0.5)
        self._pulse_animation.finished.connect(self._reverse_pulse)

        layout.addWidget(self.greeting_label)

        # Subtext (status or context, centered)
        self.subtext_label = QLabel()
        self.subtext_label.setObjectName("subtextLabel")
        self.subtext_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtext_font = QFont()
        subtext_font.setPointSize(Typography.SMALL_SIZE + 1)
        self.subtext_label.setFont(subtext_font)
        layout.addWidget(self.subtext_label)

    def set_state(self, state: WorkspaceState) -> None:
        """Update header for new state."""
        self._state = state

    def set_timestamp(self, timestamp: str) -> None:
        """Set current timestamp for viewing state."""
        self._current_timestamp = timestamp

    def update_for_idle(self) -> None:
        """Configure for idle state."""
        self.greeting_label.setText(_get_greeting())
        self.greeting_label.setProperty("state", "idle")
        self.greeting_label.style().unpolish(self.greeting_label)
        self.greeting_label.style().polish(self.greeting_label)
        self.subtext_label.setText("Your voice-powered transcription assistant")
        self._stop_pulse()

    def update_for_recording(self) -> None:
        """Configure for recording state."""
        self.greeting_label.setText("Recording")
        self.greeting_label.setProperty("state", "recording")
        self.greeting_label.style().unpolish(self.greeting_label)
        self.greeting_label.style().polish(self.greeting_label)
        self.subtext_label.setText("Speak now...")
        self._start_pulse()

    def update_for_transcribing(self) -> None:
        """Configure for transcribing state."""
        self._stop_pulse()
        self.greeting_label.setText("Transcribing...")
        self.greeting_label.setProperty("state", "transcribing")
        self.greeting_label.style().unpolish(self.greeting_label)
        self.greeting_label.style().polish(self.greeting_label)
        self.subtext_label.setText("Processing audio...")
        self._opacity_effect.setOpacity(1.0)

    def update_for_viewing(self) -> None:
        """Configure for viewing state."""
        if self._current_timestamp:
            try:
                dt = datetime.fromisoformat(self._current_timestamp)
                date_str = dt.strftime("%B %d, %Y at %I:%M %p")
                self.greeting_label.setText(date_str)
            except ValueError:
                self.greeting_label.setText("Transcript")
        else:
            self.greeting_label.setText("Transcript")
        self.greeting_label.setProperty("state", "viewing")
        self.greeting_label.style().unpolish(self.greeting_label)
        self.greeting_label.style().polish(self.greeting_label)
        self.subtext_label.setText("")
        self._stop_pulse()

    def update_for_editing(self) -> None:
        """Configure for editing state."""
        self.greeting_label.setText("Editing")
        self.greeting_label.setProperty("state", "editing")
        self.greeting_label.style().unpolish(self.greeting_label)
        self.greeting_label.style().polish(self.greeting_label)
        self.subtext_label.setText("Make your changes, then Save")
        self._stop_pulse()

    def _start_pulse(self) -> None:
        """Start pulsing animation."""
        if self._pulse_animation.state() == QPropertyAnimation.State.Running:
            return
        self._opacity_effect.setOpacity(1.0)
        self._pulse_direction = True
        self._pulse_animation.start()

    def _stop_pulse(self) -> None:
        """Stop pulsing animation."""
        self._pulse_animation.stop()
        self._opacity_effect.setOpacity(1.0)

    def _reverse_pulse(self) -> None:
        """Reverse pulse animation direction."""
        if self._state != WorkspaceState.RECORDING:
            return

        if self._pulse_direction:
            self._pulse_animation.setStartValue(0.5)
            self._pulse_animation.setEndValue(1.0)
        else:
            self._pulse_animation.setStartValue(1.0)
            self._pulse_animation.setEndValue(0.5)

        self._pulse_direction = not self._pulse_direction
        self._pulse_animation.start()

    def scale_font(self, width: int) -> None:
        """Update font size based on available width."""
        greeting_size = Typography.scaled_size(Typography.GREETING_SIZE, width)
        font = self.greeting_label.font()
        font.setPointSize(greeting_size)
        self.greeting_label.setFont(font)
