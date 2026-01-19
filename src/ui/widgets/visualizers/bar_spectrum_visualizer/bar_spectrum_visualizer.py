"""
BarSpectrumVisualizer - A traditional bar-style spectrum renderer.

Renders frequency bands as vertical bars with peak-hold "gravity" effects.
Smoothing logic adapted from CAVA (https://github.com/karlstav/cava), MIT License.
"""

from __future__ import annotations

import time
from typing import Iterable

import numpy as np
from PyQt6.QtCore import QRectF, QTimer, Qt, QPointF, QSize
from PyQt6.QtGui import QColor, QPainter, QLinearGradient
from PyQt6.QtWidgets import QSizePolicy, QWidget

import src.ui.constants.colors as c
from src.core.config_manager import ConfigManager


class BarSpectrumVisualizer(QWidget):
    """Bar-style frequency spectrum visualizer."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(200, 100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Internal state
        self._num_bars = 64
        self._spectrum = np.zeros(self._num_bars, dtype=np.float32)
        # Separate input buffer so decay logic works correctly
        self._input_spectrum = np.zeros(self._num_bars, dtype=np.float32)
        self._peaks = np.zeros(self._num_bars, dtype=np.float32)
        self._peak_times = np.zeros(self._num_bars, dtype=np.float32)

        # CAVA-style smoothing buffers
        self._prev_spectrum = np.zeros(self._num_bars, dtype=np.float32)
        self._cava_mem = np.zeros(self._num_bars, dtype=np.float32)
        self._cava_fall = np.zeros(self._num_bars, dtype=np.float32)

        # Configuration
        self._bar_gap = 2
        self._decay_rate = 0.1
        self._peak_hold_ms = 800
        self._peak_fall_rate = 0.015
        self._monstercat = 0.8
        self._noise_reduction = (
            0.85  # Higher = more temporal smoothing (stable monotone speech)
        )

        # Voice calibration (for visual emphasis weighting)
        self._calibration = None
        self._load_calibration()

        self._paused = False
        self._last_update = time.monotonic()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self._cache_config()

        try:
            ConfigManager.instance().config_changed.connect(self._on_config_changed)
        except Exception:
            pass

    def _load_calibration(self) -> None:
        """Load voice calibration data if available."""
        try:
            self._calibration = ConfigManager.get_config_section("voice_calibration")
        except Exception:
            self._calibration = None

    def _cache_config(self) -> None:
        """Read config settings."""
        vis_config = ConfigManager.get_config_section("visualizer")
        self._intensity = float(vis_config.get("intensity", 1.0))

        bar_config = ConfigManager.get_config_section("bar_spectrum")
        requested_bars = int(bar_config.get("num_bars", 64))

        # Only re-init if bar count actually changed
        if requested_bars != self._num_bars:
            self._num_bars = requested_bars
            self._spectrum = np.zeros(self._num_bars, dtype=np.float32)
            self._input_spectrum = np.zeros(self._num_bars, dtype=np.float32)
            self._peaks = np.zeros(self._num_bars, dtype=np.float32)
            self._peak_times = np.zeros(self._num_bars, dtype=np.float32)
            self._prev_spectrum = np.zeros(self._num_bars, dtype=np.float32)
            self._cava_mem = np.zeros(self._num_bars, dtype=np.float32)
            self._cava_fall = np.zeros(self._num_bars, dtype=np.float32)

        self._decay_rate = float(bar_config.get("decay_rate", 0.1))
        self._peak_hold_ms = int(bar_config.get("peak_hold_ms", 800))
        self._monstercat = float(bar_config.get("monstercat", 0.8))
        self._noise_reduction = float(bar_config.get("noise_reduction", 0.77))

    def sizeHint(self) -> QSize:
        """
        Return preferred size for the bar spectrum visualizer.

        Per Qt6 layout documentation, custom widgets must implement sizeHint()
        to provide layout engines with sizing information.

        Returns:
            QSize: Preferred size of 200x100 pixels

        References:
            - layout.html § "Custom Widgets in Layouts"
        """
        return QSize(200, 100)

    def minimumSizeHint(self) -> QSize:
        """
        Return minimum acceptable size for the visualizer.

        Returns:
            QSize: Minimum size of 100x50 pixels
        """
        return QSize(100, 50)

    def _on_config_changed(self, section: str, _key: str, _value: object) -> None:
        if section in {"visualizer", "bar_spectrum"}:
            self._cache_config()

    def start(self) -> None:
        self._paused = False
        if not self._timer.isActive():
            self.show()
            self._timer.start(16)  # ~60 FPS

    def pause(self) -> None:
        self._paused = True
        self._timer.stop()
        self.update()

    def stop(self) -> None:
        self._timer.stop()
        self.hide()
        self._paused = False
        self._spectrum.fill(0.0)
        self._input_spectrum.fill(0.0)
        self._peaks.fill(0.0)
        self._prev_spectrum.fill(0.0)
        self._cava_mem.fill(0.0)
        self._cava_fall.fill(0.0)

    def _monstercat_filter(self, bars: np.ndarray) -> np.ndarray:
        """Apply horizontal smoothing inspired by CAVA/Monstercat."""
        if self._monstercat <= 0:
            return bars

        out = bars.copy()
        # CAVA uses a pow(monstercat * 1.5, distance) divisor
        divisor = self._monstercat * 1.5

        for i in range(self._num_bars):
            # Left side
            for j in range(i - 1, max(-1, i - 10), -1):
                dist = i - j
                val = bars[i] / (divisor**dist)
                if val > out[j]:
                    out[j] = val
            # Right side
            for j in range(i + 1, min(self._num_bars, i + 10)):
                dist = j - i
                val = bars[i] / (divisor**dist)
                if val > out[j]:
                    out[j] = val
        return out

    def _compute_emphasis_weighting(self) -> np.ndarray:
        """
        Compute bar emphasis weighting based on calibrated mean frequency.

        Frequencies near mean get higher emphasis (glow, intensity).
        Frequencies far from mean taper smoothly.
        This is visual emphasis - NOT axis centering.
        """
        if not self._calibration or "freq_mean" not in self._calibration:
            # No calibration: uniform weighting
            return np.ones(self._num_bars, dtype=np.float32)

        mean_freq_hz = self._calibration.get("freq_mean", 1000)
        freq_std = self._calibration.get("freq_std", 500)

        # Map bar indices (0-63) to approximate frequencies
        # This is approximate - actual mapping depends on AudioService's bin edges
        freq_per_bar = 8000 / self._num_bars  # 125 Hz/bar average

        # Compute Gaussian emphasis: peak at mean, tails at extremes
        bar_freqs = np.arange(self._num_bars) * freq_per_bar
        z_scores = (bar_freqs - mean_freq_hz) / freq_std

        # Gaussian: exp(-0.5 * z^2), clamped to [0.5, 1.0]
        emphasis = np.exp(-0.5 * z_scores**2)
        emphasis = np.clip(emphasis, 0.5, 1.0)

        return emphasis.astype(np.float32)

    def add_spectrum(self, bands: Iterable[float]) -> None:
        """Receive FFT band energies (normalized 0-1)."""
        new_data = np.array(list(bands), dtype=np.float32)
        if new_data.size == 0:
            return

        # If input size doesn't match our display bars, interpolate
        if new_data.size != self._num_bars:
            x_in = np.linspace(0, 1, new_data.size)
            x_out = np.linspace(0, 1, self._num_bars)
            new_data = np.interp(x_out, x_in, new_data).astype(np.float32)

        # 1. Apply intensity
        new_data *= self._intensity

        # 2. Monstercat filter (Horizontal)
        new_data = self._monstercat_filter(new_data)

        # 3. Integral Smoothing (Temporal - CAVA style)
        # cava_out[n] = p->cava_mem[n] * p->noise_reduction + cava_out[n];
        # We need to divide by (1 + noise_reduction) or similar to keep scale?
        # Actually CAVA just accumulates and handles it in sensitivity.
        # Let's try a simple EMA for now to keep it sane.
        # self._spectrum = self._spectrum * self._noise_reduction + new_data * (1.0 - self._noise_reduction)

        # Let's try simple EMA to accumulate input:
        self._cava_mem = self._cava_mem * self._noise_reduction + new_data

        # Store in INPUT buffer, not display buffer
        self._input_spectrum = np.clip(
            self._cava_mem * (1.0 - self._noise_reduction), 0, 1
        )

        # Update peaks (based on input magnitude, instant)
        now = time.monotonic()
        # Use input for peaks so they look responsive
        mask = self._input_spectrum > self._peaks
        self._peaks[mask] = self._input_spectrum[mask]
        self._peak_times[mask] = now

    def _tick(self) -> None:
        """Progress animations."""
        now = time.monotonic()
        dt = now - self._last_update
        self._last_update = now

        # Frame scalar (assume 60fps base)
        fs = dt / 0.0166

        # CAVA-style Gravity (Quadratic falloff)
        # Simplified for Python:
        g_mod = 1.5 / max(0.1, self._noise_reduction)

        for i in range(self._num_bars):
            # Target is the latest input
            target = self._input_spectrum[i]
            prev = self._prev_spectrum[i]

            if target < prev:
                # Gravity falloff
                # We decay FROM the previous value
                val = prev * (1.0 - (self._cava_fall[i] * self._cava_fall[i] * g_mod))

                # But we can't go below the target input
                self._spectrum[i] = max(target, val)
                self._cava_fall[i] += 0.02 * fs
            else:
                # Attack phase - snap to target (or smooth attack if desire, but CAVA snaps up)
                self._spectrum[i] = target
                self._cava_fall[i] = 0

            self._prev_spectrum[i] = self._spectrum[i]

        # Decay peaks after hold time
        for i in range(self._num_bars):
            if now - self._peak_times[i] > self._peak_hold_ms / 1000.0:
                self._peaks[i] -= self._peak_fall_rate * fs
                if self._peaks[i] < self._spectrum[i]:
                    self._peaks[i] = self._spectrum[i]

        self.update()

    def paintEvent(self, event) -> None:
        if self._paused and np.all(self._spectrum < 0.01):
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Calculate bar geometry
        gap = self._bar_gap if self._num_bars < 48 else 1
        bar_width = (w - (self._num_bars - 1) * gap) / self._num_bars

        # Get emphasis weighting (biases visual prominence toward mean frequency)
        emphasis = self._compute_emphasis_weighting()

        # Colors (Deep Blue to Light Blue gradient)
        # 0.0 (Bottom): Deep Blue
        # 1.0 (Top): Very Light Blue
        color_start = QColor(c.BLUE_9)
        color_mid = QColor(c.BLUE_6)
        color_end = QColor(c.BLUE_3)

        peak_color = QColor(c.BLUE_4)

        for i in range(self._num_bars):
            x = i * (bar_width + gap)

            # Apply emphasis weighting to bar height
            # Bars near mean frequency are emphasized (1.0x)
            # Bars far away are suppressed (0.5x minimum)
            weighted_spectrum = self._spectrum[i] * emphasis[i]
            bar_h = weighted_spectrum * h

            # Suppress visually very low bars (noise floor)
            if bar_h < 1:
                continue

            # Draw main bar with rounded corners for a modern look
            rect = QRectF(x, h - bar_h, bar_width, bar_h)
            radius = min(bar_width / 2, 6)

            # Gradient for bar
            gradient = QLinearGradient(QPointF(x, h), QPointF(x, h - bar_h))
            gradient.setColorAt(0, color_start)
            gradient.setColorAt(0.5, color_mid)
            gradient.setColorAt(1, color_end)

            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, radius, radius)

            # Draw peak hold line
            if self._peaks[i] > weighted_spectrum + 0.02:
                peak_y = h - (self._peaks[i] * emphasis[i] * h)
                # Ensure peak line is visible
                painter.setPen(QColor(peak_color))
                painter.drawLine(QPointF(x, peak_y), QPointF(x + bar_width, peak_y))

    def cleanup(self) -> None:
        self.stop()
