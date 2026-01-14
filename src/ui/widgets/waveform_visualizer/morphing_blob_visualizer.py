"""
Morphing blob visualizer for voice input.

An organic, liquid-like blob that deforms and pulses based on audio amplitude.
Multiple translucent layers create depth, with smooth animations and gradient colors.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QSize, Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QRadialGradient
from PyQt6.QtWidgets import QSizePolicy, QWidget

from ui.constants import Colors


class MorphingBlobVisualizer(QWidget):
    """
    Organic blob visualizer that morphs with voice input.

    Creates a mesmerizing, liquid-like effect with multiple layers,
    smooth deformations, and gradient colors that respond to audio amplitude.

    Design principles:
    - Organic, flowing movement
    - Multiple layers for depth
    - Smooth color transitions
    - Calm idle animation when silent
    - Performance-optimized
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("morphingBlobVisualizer")

        # Configuration
        self.num_points = 12  # Number of control points for blob shape
        self.base_radius = 60  # Base size of the blob
        self.max_deform = 25  # Maximum deformation in pixels
        self.noise_threshold = 0.08  # Ignore levels below this
        self.num_layers = 3  # Number of overlapping blob layers

        # Animation state
        self.current_level = 0.0
        self.target_level = 0.0
        self.time = 0.0  # Time accumulator for organic movement

        # Blob points (per layer)
        self.layers: list[list[float]] = []
        for layer_idx in range(self.num_layers):
            # Each layer has slightly different phase offsets
            self.layers.append([0.0] * self.num_points)

        # Colors - using your palette
        self.color_quiet = QColor(Colors.PRIMARY)
        self.color_loud = QColor(Colors.PRIMARY_HOVER)

        # Animation timer (60 FPS for smooth morphing)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_animation)
        self.timer.setInterval(16)  # ~60 FPS

        # Widget setup
        self.setFixedSize(200, 200)  # Square aspect ratio
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def sizeHint(self) -> QSize:
        """Return the preferred size for this widget."""
        return QSize(200, 200)

    def minimumSizeHint(self) -> QSize:
        """Return the minimum size required for this widget."""
        return QSize(150, 150)

    def start(self) -> None:
        """Start the visualization animation."""
        self.current_level = 0.0
        self.target_level = 0.0
        self.time = 0.0
        for layer in self.layers:
            for i in range(len(layer)):
                layer[i] = 0.0
        self.timer.start()

    def stop(self) -> None:
        """Stop the visualization animation and reset state."""
        self.timer.stop()
        self.current_level = 0.0
        self.target_level = 0.0
        self.time = 0.0
        self.update()

    def add_level(self, amplitude: float) -> None:
        """
        Add a new amplitude level from audio input.

        Args:
            amplitude: Normalized amplitude value (0.0 to 1.0)
        """
        # Apply noise gate
        if amplitude < self.noise_threshold:
            amplitude = 0.0

        self.target_level = max(0.0, min(1.0, amplitude))

    @pyqtSlot()
    def _update_animation(self) -> None:
        """Update animation state and trigger repaint."""
        # Smooth interpolation toward target level
        self.current_level += (self.target_level - self.current_level) * 0.2

        # Decay target (simulates natural falloff)
        self.target_level *= 0.92

        # Increment time for organic movement
        self.time += 0.02

        # Update each layer with organic deformations
        for layer_idx, layer in enumerate(self.layers):
            # Each layer has unique phase offset for variety
            phase_offset = layer_idx * 2.1

            for i in range(len(layer)):
                # Calculate target deformation for this point
                angle = (i / self.num_points) * math.pi * 2

                # Combine multiple sine waves for organic feel
                idle_wave = (
                    math.sin(self.time * 1.5 + angle * 2 + phase_offset) * 0.15
                )
                voice_wave = (
                    math.sin(self.time * 3 + angle * 3 + phase_offset)
                    * self.current_level
                )

                target_deform = (idle_wave + voice_wave) * self.max_deform

                # Smooth interpolation
                layer[i] += (target_deform - layer[i]) * 0.15

        # Trigger repaint
        self.update()

    def paintEvent(self, event) -> None:
        """Draw the morphing blob with multiple layers."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Calculate center
        center_x = self.width() / 2
        center_y = self.height() / 2

        # Interpolate color based on current level
        current_color = self._interpolate_color(
            self.color_quiet, self.color_loud, self.current_level
        )

        # Draw each layer from back to front
        for layer_idx in reversed(range(self.num_layers)):
            layer = self.layers[layer_idx]

            # Calculate layer properties
            layer_scale = 1.0 - (
                layer_idx * 0.15
            )  # Back layers are slightly smaller
            layer_opacity = 0.3 + (
                layer_idx * 0.25
            )  # Back layers are more transparent

            # Create blob path
            path = QPainterPath()
            points = []

            for i in range(self.num_points):
                angle = (i / self.num_points) * math.pi * 2

                # Calculate radius with deformation
                radius = (self.base_radius + layer[i]) * layer_scale

                # Calculate point position
                x = center_x + math.cos(angle) * radius
                y = center_y + math.sin(angle) * radius
                points.append(QPointF(x, y))

            # Create smooth blob using cubic curves
            if points:
                path.moveTo(points[0])

                for i in range(len(points)):
                    current = points[i]
                    next_point = points[(i + 1) % len(points)]

                    # Calculate control points for smooth curve
                    control1_x = current.x() + (next_point.x() - current.x()) * 0.5
                    control1_y = current.y() + (next_point.y() - current.y()) * 0.5

                    # Add some perpendicular offset for organic curves
                    dx = next_point.x() - current.x()
                    dy = next_point.y() - current.y()
                    perp_x = -dy * 0.3
                    perp_y = dx * 0.3

                    control1 = QPointF(control1_x + perp_x, control1_y + perp_y)

                    path.quadTo(control1, next_point)

                path.closeSubpath()

            # Create radial gradient for depth
            gradient = QRadialGradient(
                center_x, center_y, self.base_radius * layer_scale
            )

            # Center is brighter
            center_color = QColor(current_color)
            center_color.setAlpha(int(255 * layer_opacity))
            gradient.setColorAt(0.0, center_color)

            # Edge fades out
            edge_color = QColor(current_color)
            edge_color.setAlpha(int(100 * layer_opacity))
            gradient.setColorAt(0.7, edge_color)

            # Outer edge is very transparent
            outer_color = QColor(current_color)
            outer_color.setAlpha(0)
            gradient.setColorAt(1.0, outer_color)

            # Draw the blob
            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(path)

        # Optional: Add a subtle glow effect when loud
        if self.current_level > 0.3:
            glow_opacity = int((self.current_level - 0.3) * 200)
            glow_gradient = QRadialGradient(
                center_x, center_y, self.base_radius * 1.3
            )

            glow_color = QColor(current_color)
            glow_color.setAlpha(glow_opacity)
            glow_gradient.setColorAt(0.0, glow_color)

            transparent = QColor(current_color)
            transparent.setAlpha(0)
            glow_gradient.setColorAt(1.0, transparent)

            painter.setBrush(glow_gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(
                int(center_x - self.base_radius * 1.3),
                int(center_y - self.base_radius * 1.3),
                int(self.base_radius * 2.6),
                int(self.base_radius * 2.6),
            )

    def _interpolate_color(self, color1: QColor, color2: QColor, t: float) -> QColor:
        """Interpolate between two colors based on t (0.0 to 1.0)."""
        r = int(color1.red() + (color2.red() - color1.red()) * t)
        g = int(color1.green() + (color2.green() - color1.green()) * t)
        b = int(color1.blue() + (color2.blue() - color1.blue()) * t)
        return QColor(r, g, b)

    def cleanup(self) -> None:
        """Clean up resources before destruction."""
        try:
            if self.timer.isActive():
                self.timer.stop()
            self.layers.clear()
        except Exception:
            pass

    def __del__(self) -> None:
        """Destructor to ensure timer is stopped."""
        try:
            self.cleanup()
        except Exception:
            pass
