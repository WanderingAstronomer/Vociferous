"""
SliderField - combined slider and value label widget.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSlider, QWidget


class SliderField(QWidget):
    """Composite widget for numeric slider settings."""

    valueChanged = pyqtSignal(float)

    def __init__(
        self,
        minimum: float,
        maximum: float,
        step: float,
        initial: float,
        is_float: bool = True,
        formatter: Callable[[float], str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._is_float = is_float
        self._step = step
        self._formatter = formatter or (
            lambda value: f"{value:.2f}" if is_float else str(int(value))
        )

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(self._to_slider_value(minimum))
        self._slider.setMaximum(self._to_slider_value(maximum))
        self._slider.setValue(self._to_slider_value(initial))

        self._value_label = QLabel()
        self._value_label.setMinimumWidth(56)
        self._value_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._update_label(self.value())

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._slider, 1)
        layout.addWidget(self._value_label)

        self._slider.valueChanged.connect(self._handle_change)

    def value(self) -> float:
        """Return the current value."""
        slider_value = self._slider.value()
        if self._is_float:
            return slider_value / self._scale_factor()
        return float(slider_value)

    def set_value(self, value: float) -> None:
        """Set the slider value."""
        self._slider.setValue(self._to_slider_value(value))
        self._update_label(self.value())

    def _scale_factor(self) -> int:
        return max(1, int(round(1.0 / self._step))) if self._is_float else 1

    def _to_slider_value(self, value: float) -> int:
        if self._is_float:
            return int(round(value * self._scale_factor()))
        return int(round(value))

    def _handle_change(self, value: int) -> None:
        current = self.value()
        self._update_label(current)
        self.valueChanged.emit(current)

    def _update_label(self, value: float) -> None:
        self._value_label.setText(self._formatter(value))
