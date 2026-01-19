"""
Strength Selector Widget - Refinement intensity control.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider

import src.ui.constants.colors as c
from src.ui.constants import Spacing, Typography
from src.ui.styles.refine_view_styles import get_strength_slider_stylesheet


class StrengthSelector(QWidget):
    """
    A polished strength selector with slider and visual feedback.

    Displays a slider with labeled intensity levels and visual state.
    """

    valueChanged = pyqtSignal(str)  # Emits profile name: "MINIMAL", "BALANCED", etc.

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._profiles = ["MINIMAL", "BALANCED", "STRONG", "OVERKILL"]
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(Spacing.MINOR_GAP)

        # Current value display
        self._lbl_current = QLabel("BALANCED")
        self._lbl_current.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_current.setStyleSheet(
            f"color: {c.BLUE_4}; font-size: {Typography.FONT_SIZE_LG}px; "
            f"font-weight: bold; padding: {Spacing.MINOR_GAP}px; "
            f"border: none; background: transparent;"
        )
        main_layout.addWidget(self._lbl_current)

        # Slider
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 3)
        self._slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._slider.setTickInterval(1)
        self._slider.setValue(1)  # Default to BALANCED
        self._slider.setMinimumHeight(40)
        self._slider.valueChanged.connect(self._on_value_changed)

        # Styling
        self._slider.setStyleSheet(get_strength_slider_stylesheet())

        main_layout.addWidget(self._slider)

        # Labels under slider
        labels_row = QHBoxLayout()
        labels_row.setContentsMargins(0, 0, 0, 0)
        labels_row.setSpacing(0)

        for profile in self._profiles:
            lbl = QLabel(profile.title())
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"color: {c.GRAY_3}; font-size: {Typography.FONT_SIZE_XS}px; "
                f"border: none; background: transparent;"
            )
            labels_row.addWidget(lbl, 1)

        main_layout.addLayout(labels_row)

        # Help text
        help_text = QLabel("Controls how aggressively the text is rewritten")
        help_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        help_text.setStyleSheet(
            f"color: {c.GRAY_3}; font-size: {Typography.FONT_SIZE_SM}px; "
            f"font-style: italic; margin-top: {Spacing.MINOR_GAP}px; "
            f"border: none; background: transparent;"
        )
        help_text.setWordWrap(True)
        main_layout.addWidget(help_text)

    def _on_value_changed(self, value: int) -> None:
        """Update display and emit signal when value changes."""
        if 0 <= value < len(self._profiles):
            profile = self._profiles[value]
            self._lbl_current.setText(profile)
            self.valueChanged.emit(profile)

    def get_value(self) -> str:
        """Get current profile name."""
        val = self._slider.value()
        return self._profiles[val] if 0 <= val < len(self._profiles) else "BALANCED"

    def set_value(self, profile: str) -> None:
        """Set current profile by name."""
        try:
            idx = self._profiles.index(profile.upper())
            self._slider.blockSignals(True)
            self._slider.setValue(idx)
            self._lbl_current.setText(self._profiles[idx])
            self._slider.blockSignals(False)
        except ValueError:
            pass  # Invalid profile name, ignore

    def setEnabled(self, enabled: bool) -> None:
        """Override to update visual state."""
        super().setEnabled(enabled)
        self._slider.setEnabled(enabled)

        if enabled:
            self._lbl_current.setStyleSheet(
                f"color: {c.BLUE_4}; font-size: {Typography.FONT_SIZE_LG}px; "
                f"font-weight: bold; padding: {Spacing.MINOR_GAP}px; "
                f"border: none; background: transparent;"
            )
        else:
            self._lbl_current.setStyleSheet(
                f"color: {c.GRAY_3}; font-size: {Typography.FONT_SIZE_LG}px; "
                f"padding: {Spacing.MINOR_GAP}px; border: none; background: transparent;"
            )
