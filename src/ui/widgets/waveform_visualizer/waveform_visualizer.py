"""
Horizontal waveform visualizer for recording state.

Displays a left-to-right scrolling waveform with vertical bars that respond to audio amplitude.
Bars fade from left (oldest) to right (newest) with smooth decay animation.
"""

from __future__ import annotations

from collections import deque

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QSizePolicy, QWidget

from ui.constants import Colors


class WaveformVisualizer(QWidget):
    """
    Horizontal waveform display for recording state.

    Displays thin vertical bars arranged linearly, with heights
    representing recent audio amplitude levels. Features smooth
    decay animation for a calm, ocean-wave aesthetic.

    Design principles:
    - Linear scrolling (history)
    - Thin, minimal lines
    - Slow decay when silent
    - Blue accent color palette
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("waveformVisualizer")

        # Configuration - sized for visual impact
        self.num_bars = (
            600  # Number of bars in history buffer (supports ultra-wide displays)
        )
        self.bar_width = 4  # Fixed width per bar in pixels
        self.decay_rate = 0.92  # Smooth decay factor (lower = faster decay)
        self.bar_spacing = 2  # Space between bars in pixels
        self.noise_threshold = 0.08  # Noise gate: ignore levels below this (0.0-1.0)

        # State
        self.levels: deque[float] = deque([0.0] * self.num_bars, maxlen=self.num_bars)
        self.current_level = 0.0
        self.target_level = 0.0

        # Colors
        self.bar_color_quiet = QColor(Colors.ACCENT_BLUE)
        self.bar_color_loud = QColor(Colors.ACCENT_BLUE_HOVER)

        # Animation timer (30 FPS)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_animation)
        self.timer.setInterval(33)  # ~30 FPS

        # Widget setup - fixed height horizontal waveform
        self.setFixedHeight(130)  # Fixed height optimized for view
        self.setMinimumWidth(200)  # Minimum width to show bars
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Styles are applied at app level via generate_unified_stylesheet()

    def sizeHint(self) -> QSize:
        """Return the preferred size for this widget."""
        return QSize(16777215, 130)  # Max width, fixed height

    def minimumSizeHint(self) -> QSize:
        """Return the minimum size required for this widget."""
        return QSize(200, 130)

    def start(self) -> None:
        """Start the visualization animation."""
        self.levels = deque([0.0] * self.num_bars, maxlen=self.num_bars)
        self.current_level = 0.0
        self.target_level = 0.0
        self.timer.start()

    def stop(self) -> None:
        """Stop the visualization animation and reset state."""
        self.timer.stop()
        self.levels = deque([0.0] * self.num_bars, maxlen=self.num_bars)
        self.current_level = 0.0
        self.target_level = 0.0
        self.update()

    def add_level(self, amplitude: float) -> None:
        """
        Add a new amplitude level from audio input.

        Args:
            amplitude: Normalized amplitude value (0.0 to 1.0)
        """
        # Apply noise gate - ignore levels below threshold
        if amplitude < self.noise_threshold:
            amplitude = 0.0

        self.target_level = max(0.0, min(1.0, amplitude))

    @pyqtSlot()
    def _update_animation(self) -> None:
        """Update animation state and trigger repaint."""
        # Smooth interpolation toward target level
        self.current_level += (self.target_level - self.current_level) * 0.3

        # Apply decay to target (simulates audio decay when silent)
        self.target_level *= self.decay_rate

        # Add new level on the right (pushes out leftmost)
        self.levels.append(self.current_level)

        # Trigger repaint
        self.update()

    def paintEvent(self, event) -> None:
        """Draw the horizontal scrolling waveform."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Get current widget width (force fresh calculation)
        available_width = self.size().width()

        # Calculate how many bars can fit
        max_visible_bars = max(
            1, available_width // (self.bar_width + self.bar_spacing)
        )

        # Always draw enough bars to fill the width, padding with zeros on left if needed
        if len(self.levels) >= max_visible_bars:
            visible_levels = list(self.levels)[-max_visible_bars:]
        else:
            # Pad with zeros on the left for missing history
            padding_needed = max_visible_bars - len(self.levels)
            visible_levels = [0.0] * padding_needed + list(self.levels)

        # Add vertical padding to prevent clipping
        vertical_padding = 8
        drawable_height = self.height() - (vertical_padding * 2)

        # Calculate center line using drawable area
        center_y = vertical_padding + (drawable_height / 2)

        # Draw bars from left to right (scrolling effect from deque, not positioning)
        x_pos: float = 0.0
        for i, level in enumerate(visible_levels):
            # Calculate bar height (extends up and down from center)
            bar_height = level * (drawable_height / 2) * 0.80

            # Calculate vertical position (centered)
            y_top = center_y - bar_height
            bar_full_height = bar_height * 2

            # Fade bars on the left (oldest) - use visible count for proper fade
            fade_factor = i / max(1, len(visible_levels) - 1)
            opacity = int(100 + (155 * fade_factor))

            # Color interpolation based on level
            color = self._interpolate_color(
                self.bar_color_quiet, self.bar_color_loud, level
            )
            color.setAlpha(opacity)

            # Draw bar (no rounding for perfect symmetry)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.fillRect(
                int(x_pos), int(y_top), int(self.bar_width), int(bar_full_height), color
            )

            # Move to next bar position
            x_pos += self.bar_width + self.bar_spacing

    def _interpolate_color(self, color1: QColor, color2: QColor, t: float) -> QColor:
        """Interpolate between two colors based on t (0.0 to 1.0)."""
        r = int(color1.red() + (color2.red() - color1.red()) * t)
        g = int(color1.green() + (color2.green() - color1.green()) * t)
        b = int(color1.blue() + (color2.blue() - color1.blue()) * t)
        a = int(color1.alpha() + (color2.alpha() - color1.alpha()) * t)
        return QColor(r, g, b, a)

    def cleanup(self) -> None:
        """Clean up resources before destruction."""
        try:
            if self.timer.isActive():
                self.timer.stop()
            self.levels.clear()
        except Exception:
            pass

    def __del__(self) -> None:
        """Destructor to ensure timer is stopped."""
        try:
            self.cleanup()
        except Exception:
            pass
