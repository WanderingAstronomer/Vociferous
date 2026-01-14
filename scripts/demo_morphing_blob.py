#!/usr/bin/env python3
"""
Demo script for the morphing blob visualizer.

This script creates a simple window showing the morphing blob
with a slider to control the amplitude level for testing.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.waveform_visualizer import MorphingBlobVisualizer


class MorphingBlobDemo(QMainWindow):
    """Demo window for the morphing blob visualizer."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Morphing Blob Visualizer Demo")
        self.setMinimumSize(600, 500)

        # Create central widget
        central = QWidget()
        self.setCentralWidget(central)

        # Main layout
        layout = QVBoxLayout(central)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Title
        title = QLabel("🎙️ Morphing Blob Visualizer Demo")
        title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #5a9fd4;
                margin: 20px;
            }
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Create the morphing blob visualizer
        self.visualizer = MorphingBlobVisualizer()
        layout.addWidget(self.visualizer, alignment=Qt.AlignmentFlag.AlignCenter)

        # Controls
        controls = QWidget()
        controls_layout = QVBoxLayout(controls)

        # Amplitude slider
        slider_layout = QHBoxLayout()
        slider_label = QLabel("Amplitude:")
        slider_label.setStyleSheet("color: #d4d4d4; font-size: 14px;")
        slider_layout.addWidget(slider_label)

        self.amplitude_slider = QSlider(Qt.Orientation.Horizontal)
        self.amplitude_slider.setMinimum(0)
        self.amplitude_slider.setMaximum(100)
        self.amplitude_slider.setValue(0)
        self.amplitude_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #3c3c3c;
                height: 8px;
                background: #2a2a2a;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #5a9fd4;
                border: 1px solid #6db3e8;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: #6db3e8;
            }
        """)
        slider_layout.addWidget(self.amplitude_slider)

        self.amplitude_value = QLabel("0%")
        self.amplitude_value.setStyleSheet("color: #d4d4d4; font-size: 14px; min-width: 40px;")
        slider_layout.addWidget(self.amplitude_value)

        controls_layout.addLayout(slider_layout)

        # Start/Stop buttons
        button_layout = QHBoxLayout()

        self.start_btn = QPushButton("▶ Start")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background: #2d6a4f;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #40916c;
            }
            QPushButton:pressed {
                background: #1b4332;
            }
        """)
        self.start_btn.clicked.connect(self._on_start)
        button_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background: #e06c75;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #ff8585;
            }
            QPushButton:pressed {
                background: #cc5656;
            }
            QPushButton:disabled {
                background: #3c3c3c;
                color: #555555;
            }
        """)
        self.stop_btn.clicked.connect(self._on_stop)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)

        controls_layout.addLayout(button_layout)

        # Auto pulse button
        self.auto_pulse_btn = QPushButton("🌊 Auto Pulse")
        self.auto_pulse_btn.setStyleSheet("""
            QPushButton {
                background: #3a5f7f;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #4a7f9f;
            }
            QPushButton:pressed {
                background: #2a4f6f;
            }
            QPushButton:disabled {
                background: #3c3c3c;
                color: #555555;
            }
        """)
        self.auto_pulse_btn.clicked.connect(self._on_auto_pulse)
        self.auto_pulse_btn.setEnabled(False)
        controls_layout.addWidget(self.auto_pulse_btn)

        layout.addWidget(controls)

        # Info text
        info = QLabel(
            "Use the slider to control amplitude, or click 'Auto Pulse' "
            "to see a simulated speech pattern."
        )
        info.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 12px;
                margin: 20px;
            }
        """)
        info.setWordWrap(True)
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        # Set window background
        self.setStyleSheet("QMainWindow { background: #1e1e1e; }")

        # Connect slider
        self.amplitude_slider.valueChanged.connect(self._on_amplitude_changed)

        # Auto pulse timer
        self.auto_pulse_timer = QTimer()
        self.auto_pulse_timer.timeout.connect(self._auto_pulse_tick)
        self.auto_pulse_phase = 0.0

    def _on_start(self) -> None:
        """Start the visualization."""
        self.visualizer.start()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.auto_pulse_btn.setEnabled(True)

    def _on_stop(self) -> None:
        """Stop the visualization."""
        self.visualizer.stop()
        self.auto_pulse_timer.stop()
        self.amplitude_slider.setValue(0)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.auto_pulse_btn.setEnabled(False)

    def _on_amplitude_changed(self, value: int) -> None:
        """Handle amplitude slider changes."""
        amplitude = value / 100.0
        self.amplitude_value.setText(f"{value}%")
        if self.visualizer.timer.isActive():
            self.visualizer.add_level(amplitude)

    def _on_auto_pulse(self) -> None:
        """Toggle auto pulse mode."""
        if self.auto_pulse_timer.isActive():
            self.auto_pulse_timer.stop()
            self.auto_pulse_btn.setText("🌊 Auto Pulse")
            self.amplitude_slider.setEnabled(True)
        else:
            self.auto_pulse_timer.start(50)  # 20 Hz updates
            self.auto_pulse_btn.setText("⏸ Stop Pulse")
            self.amplitude_slider.setEnabled(False)

    def _auto_pulse_tick(self) -> None:
        """Generate simulated speech pattern."""
        import math
        import random

        # Simulate organic speech with multiple sine waves and randomness
        self.auto_pulse_phase += 0.1

        # Base wave (breathing pattern)
        base = math.sin(self.auto_pulse_phase * 0.3) * 0.3 + 0.3

        # Speech variation (faster)
        speech = math.sin(self.auto_pulse_phase * 2) * 0.4

        # Random bursts (consonants)
        burst = random.random() * 0.3 if random.random() > 0.7 else 0

        # Combine and clamp
        amplitude = max(0.0, min(1.0, base + speech + burst))

        # Update slider and visualizer
        slider_value = int(amplitude * 100)
        self.amplitude_slider.blockSignals(True)
        self.amplitude_slider.setValue(slider_value)
        self.amplitude_slider.blockSignals(False)
        self.amplitude_value.setText(f"{slider_value}%")
        self.visualizer.add_level(amplitude)

    def closeEvent(self, event) -> None:
        """Clean up on close."""
        self.auto_pulse_timer.stop()
        self.visualizer.cleanup()
        super().closeEvent(event)


def main() -> None:
    """Run the demo."""
    app = QApplication(sys.argv)
    window = MorphingBlobDemo()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
