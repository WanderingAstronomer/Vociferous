"""
WorkspaceHeader - Header area showing greeting, status, or timestamp.

Includes pulse animation for recording state.
"""

from __future__ import annotations

from datetime import datetime


from PyQt6.QtCore import QPropertyAnimation, Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QGraphicsOpacityEffect,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QPushButton,
    QSizePolicy,
)

import src.ui.constants.colors as c
from src.ui.constants import (
    Spacing,
    Timing,
    Typography,
    WorkspaceState,
    BLURB_MAX_WIDTH,
)
from src.core.config_manager import ConfigManager
from src.core.resource_manager import ResourceManager


def _get_greeting() -> str:
    """Return time-of-day greeting with personalization."""
    hour = datetime.now().hour

    # Easter Egg
    if 0 <= hour < 5:
        return "Hey there, night owl!"

    if hour < 12:
        base = "Good morning"
    elif hour < 17:
        base = "Good afternoon"
    else:
        base = "Good evening"

    name = ConfigManager.get_config_value("user", "name")
    if name:
        return f"{base}, {name}."
    return f"{base}."


def _balance_motd_text(text: str, max_lines: int | None = None) -> str:
    """
    Balance MOTD text across lines with roughly equal word/character counts.
    Adjusts target line count based on total length to avoid crowded lines.

    Args:
        text: The MOTD text to balance
        max_lines: Optional override for the number of lines to split into

    Returns:
        Text with manual line breaks for balanced wrapping
    """
    words = text.split()
    total_words = len(words)
    total_chars = len(text)

    # 1. Be LESS strict: Higher threshold for balancing.
    # We want to allow longer strings to stay on fewer lines to span the workspace.
    if total_words <= 28 and max_lines is None:
        return text

    # 2. Dynamic line count based on visual density (if not overridden)
    # Aims for ~80-100 characters per line for standard spans.
    if max_lines is None:
        if total_chars < 240:
            max_lines = 2
        elif total_chars < 420:
            max_lines = 3
        else:
            max_lines = 4

    # Calculate target words per line
    words_per_line = max(1, total_words // max_lines)

    # Build balanced lines
    lines: list[str] = []
    current_line = []

    for word in words:
        current_line.append(word)
        # Split when we reach target, but only if we have more lines to fill
        if len(current_line) >= words_per_line and len(lines) < max_lines - 1:
            lines.append(" ".join(current_line))
            current_line = []

    # Add remaining words to last line
    if current_line:
        lines.append(" ".join(current_line))

    return "\n".join(lines)


class WorkspaceHeader(QWidget):
    """
    Header area showing greeting, status, or timestamp.

    Includes pulse animation for recording state.
    """

    request_motd_refresh = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = WorkspaceState.IDLE
        self._current_timestamp = ""
        self._pulse_direction = True
        self._motd = ""  # Empty means use default "Press key..." hint

        self._setup_ui()

        # Connect to config updates to refresh hotkey hints
        self._config_manager = ConfigManager.instance()
        self._config_manager.config_reloaded.connect(self._on_config_updated)
        self._config_manager.config_changed.connect(
            lambda s, k, v: self._on_config_updated()
        )

    def cleanup(self) -> None:
        """Cleanup resources and disconnect signals."""
        try:
            self._config_manager.config_reloaded.disconnect(self._on_config_updated)
            self._config_manager.config_changed.disconnect()
        except (RuntimeError, TypeError, AttributeError):
            # Signals already disconnected or object deleted
            pass

    def __del__(self) -> None:
        """Cleanup on deletion."""
        self.cleanup()

    def _setup_ui(self) -> None:
        """Create header layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, Spacing.GREETING_TOP, 0, 0)
        layout.setSpacing(Spacing.MINOR_GAP)

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

        # Subtext container (label + refresh button)
        subtext_container = QWidget()
        subtext_layout = QHBoxLayout(subtext_container)
        subtext_layout.setContentsMargins(0, 0, 0, 0)
        subtext_layout.setSpacing(Spacing.MINOR_GAP)

        # Spacers to center the content
        subtext_layout.addStretch()

        # Dummy spacer to balance the refresh button (ensures label is perfectly centered)
        self._centering_spacer = QWidget()
        self._centering_spacer.setFixedSize(24, 24)
        self._centering_spacer.setVisible(False)
        subtext_layout.addWidget(self._centering_spacer)

        # Subtext (status or context, centered)
        self.subtext_label = QLabel()
        self.subtext_label.setObjectName("subtextLabel")
        self.subtext_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtext_label.setWordWrap(True)
        self.subtext_label.setMaximumWidth(BLURB_MAX_WIDTH)
        self.subtext_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        subtext_font = QFont()
        subtext_font.setPointSize(Typography.SMALL_SIZE + 1)
        self.subtext_label.setFont(subtext_font)
        subtext_layout.addWidget(self.subtext_label)

        # Refresh Button (only visible in IDLE state usually, but managed by container)
        self.refresh_button = QPushButton()
        self.refresh_button.setObjectName("motdRefreshButton")
        self.refresh_button.setFlat(True)
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.setIcon(
            QIcon(ResourceManager.get_icon_path("motd_icon-refresh"))
        )
        self.refresh_button.setIconSize(QSize(24, 24))
        self.refresh_button.setFixedSize(24, 24)
        self.refresh_button.clicked.connect(lambda: self.request_motd_refresh.emit())
        self.refresh_button.setVisible(
            False
        )  # Hidden by default until IDLE state confirms

        subtext_layout.addWidget(self.refresh_button)

        subtext_layout.addStretch()

        layout.addWidget(subtext_container)

    def set_state(self, state: WorkspaceState) -> None:
        """Update header for new state."""
        self._state = state

    def _get_hotkey_label(self) -> str:
        """Fetch and format the current activation hotkey."""
        key = ConfigManager.get_config_value("recording_options", "activation_key")
        if not key:
            return "Alt"
        return key.replace("_", " ").title()

    def _on_config_updated(self) -> None:
        """Refresh display when configuration changes."""  # Guard against accessing deleted widgets during teardown
        try:
            if not self.greeting_label or not self.refresh_button:
                return
        except RuntimeError:
            # Widget has been deleted
            return
            # Force a refresh of the current state's text
        match self._state:
            case WorkspaceState.IDLE:
                self.update_for_idle()
            case WorkspaceState.RECORDING:
                self.update_for_recording()
            # case WorkspaceState.TRANSCRIBING:  # Not a valid Enum state
            #     self.update_for_transcribing()
            case WorkspaceState.VIEWING:
                self.update_for_viewing()
            case WorkspaceState.READY:
                self.update_for_ready()
            case WorkspaceState.EDITING:
                self.update_for_editing()

    def set_timestamp(self, timestamp: str) -> None:
        """Set current timestamp for viewing state."""
        self._current_timestamp = timestamp

    def set_motd(self, text: str) -> None:
        """Set custom Message of the Day."""
        self._motd = text
        if self._state == WorkspaceState.IDLE:
            balanced_text = _balance_motd_text(text)
            self.subtext_label.setText(balanced_text)

    def update_for_idle(self) -> None:
        """Configure for idle state."""
        try:
            self.greeting_label.setText(_get_greeting())
            self.greeting_label.setProperty("state", "idle")
            self.greeting_label.setStyleSheet("")  # Reset style
            self.greeting_label.style().unpolish(self.greeting_label)
            self.greeting_label.style().polish(self.greeting_label)
        except RuntimeError:
            # Widget has been deleted
            return

        if self._motd:
            balanced_text = _balance_motd_text(self._motd)
            self.subtext_label.setText(balanced_text)
        else:
            hotkey = self._get_hotkey_label()
            self.subtext_label.setText(f"Press {hotkey} to start recording")

        # Refinement feature gate for refresh button
        refinement_enabled = ConfigManager.get_config_value("refinement", "enabled")
        show_refresh = bool(refinement_enabled)
        self.refresh_button.setVisible(show_refresh)
        self._centering_spacer.setVisible(show_refresh)
        self._stop_pulse()

    def update_for_recording(self) -> None:
        """Configure for recording state."""
        try:
            self.refresh_button.setVisible(False)
            self._centering_spacer.setVisible(False)
            self.greeting_label.setText("Recording")
            self.greeting_label.setProperty("state", "recording")
            # Apply red color specifically for recording state
        except RuntimeError:
            # Widget has been deleted
            return
        self.greeting_label.setStyleSheet(f"color: {c.RED_5};")
        self.greeting_label.style().unpolish(self.greeting_label)
        self.greeting_label.style().polish(self.greeting_label)
        hotkey = self._get_hotkey_label()
        self.subtext_label.setText(f"Go ahead and speak (Press {hotkey} to stop)")
        self._start_pulse()

    def update_for_transcribing(self) -> None:
        """Configure for transcribing state."""
        self.refresh_button.setVisible(False)
        self._centering_spacer.setVisible(False)
        self._stop_pulse()
        self.greeting_label.setText("Transcribing...")
        self.greeting_label.setProperty("state", "transcribing")
        self.greeting_label.style().unpolish(self.greeting_label)
        self.greeting_label.style().polish(self.greeting_label)
        self.subtext_label.setText("Processing audio...")
        self._opacity_effect.setOpacity(1.0)

    def update_for_viewing(self) -> None:
        """Configure for viewing state."""
        try:
            self.refresh_button.setVisible(False)
            self._centering_spacer.setVisible(False)
            # DEMOTED: Timestamp removed from UI entirely per user request
            self.greeting_label.setText("Transcript Loaded")
            self.greeting_label.setProperty("state", "viewing")
        except RuntimeError:
            # Widget has been deleted
            return
        self.greeting_label.setStyleSheet("")  # Reset style
        self.greeting_label.style().unpolish(self.greeting_label)
        self.greeting_label.style().polish(self.greeting_label)
        hotkey = self._get_hotkey_label()
        self.subtext_label.setText(f"Press {hotkey} to start recording")
        self._stop_pulse()

    def update_for_ready(self) -> None:
        """Configure for ready state (fresh transcription)."""
        self.refresh_button.setVisible(False)
        self._centering_spacer.setVisible(False)
        self.greeting_label.setText("Transcription complete")
        self.greeting_label.setProperty("state", "ready")
        # Green color for success/ready state
        self.greeting_label.setStyleSheet(f"color: {c.GREEN_5};")
        self.greeting_label.style().unpolish(self.greeting_label)
        self.greeting_label.style().polish(self.greeting_label)
        hotkey = self._get_hotkey_label()
        self.subtext_label.setText(
            f"Press {hotkey} to start recording, or select an action below"
        )
        self._stop_pulse()

    def update_for_editing(self) -> None:
        """Configure for editing state."""
        self.refresh_button.setVisible(False)
        self._centering_spacer.setVisible(False)
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
