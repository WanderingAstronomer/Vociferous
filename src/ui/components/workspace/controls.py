"""
WorkspaceControls - Button cluster for workspace actions.

Primary action button (Start/Stop) and secondary buttons (Edit, Save, Cancel, Delete).
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.constants import Colors, Dimensions, Spacing
from utils import ConfigManager


class WorkspaceControls(QWidget):
    """
    Control button cluster for workspace actions.

    Emits signals for button clicks; parent handles state logic.

    Signals:
        primaryClicked(): Start/Stop button clicked
        editSaveClicked(): Edit/Save button clicked
        destructiveClicked(): Cancel/Delete button clicked
        refineClicked(str): Refine button clicked, passing profile (MINIMAL, BALANCED, STRONG)
    """

    primaryClicked = pyqtSignal()
    editSaveClicked = pyqtSignal()
    destructiveClicked = pyqtSignal()
    refineClicked = pyqtSignal(str)  # Passes profile

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create control button layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.CONTROL_ROW_GAP)

        # Row 1: Primary action (Start/Stop)
        self.primary_btn = QPushButton("Start")
        self.primary_btn.setObjectName("primaryButton")
        self.primary_btn.setFixedHeight(Dimensions.BUTTON_HEIGHT_PRIMARY)
        self.primary_btn.setMinimumWidth(Dimensions.BUTTON_MIN_WIDTH_PRIMARY)
        self.primary_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.primary_btn.clicked.connect(self.primaryClicked.emit)
        layout.addWidget(self.primary_btn)

        # Row 2: Edit/Save and Cancel/Delete
        row2 = QHBoxLayout()
        row2.setSpacing(Spacing.BUTTON_GAP)

        self.edit_save_btn = QPushButton("Edit")
        self.edit_save_btn.setObjectName("secondaryButton")
        self.edit_save_btn.setFixedHeight(Dimensions.BUTTON_HEIGHT_SECONDARY)
        self.edit_save_btn.clicked.connect(self.editSaveClicked.emit)
        row2.addWidget(self.edit_save_btn, 1)

        self.destructive_btn = QPushButton("Cancel")
        self.destructive_btn.setObjectName("destructiveButton")
        self.destructive_btn.setFixedHeight(Dimensions.BUTTON_HEIGHT_SECONDARY)
        self.destructive_btn.clicked.connect(self.destructiveClicked.emit)
        row2.addWidget(self.destructive_btn, 1)

        layout.addLayout(row2)

        # Optional refinement row (hidden until feature enabled)
        self.refine_row = QWidget()
        refine_layout = QHBoxLayout(self.refine_row)
        # Match gap of other buttons
        refine_layout.setContentsMargins(0, 0, 0, 0)
        refine_layout.setSpacing(Spacing.BUTTON_GAP)

        # Profile Radio Buttons
        self.profile_group = QButtonGroup(self)
        self.profile_minimal = QRadioButton("Min")
        self.profile_balanced = QRadioButton("Bal")
        self.profile_strong = QRadioButton("Str")

        # Tooltips
        self.profile_minimal.setToolTip("Minimal: Fixes spelling and grammar only.")
        self.profile_balanced.setToolTip("Balanced: Fixes grammar + cleans stutters.")
        self.profile_strong.setToolTip(
            "Strong: Smooths output and fixes sentence flow."
        )

        # Default
        self.profile_balanced.setChecked(True)

        self.profile_group.addButton(self.profile_minimal)
        self.profile_group.addButton(self.profile_balanced)
        self.profile_group.addButton(self.profile_strong)

        # Simple styling for radios to align better
        radio_style = f"""
            QRadioButton {{
                color: {Colors.TEXT_SECONDARY};
                font-weight: 500;
            }}
            QRadioButton:checked {{
                color: {Colors.PRIMARY};
                font-weight: bold;
            }}
        """
        self.profile_minimal.setStyleSheet(radio_style)
        self.profile_balanced.setStyleSheet(radio_style)
        self.profile_strong.setStyleSheet(radio_style)

        # Radios Container
        radios_container = QWidget()
        radios_layout = QHBoxLayout(radios_container)
        radios_layout.setContentsMargins(0, 0, 0, 0)
        radios_layout.setSpacing(8)
        radios_layout.addWidget(self.profile_minimal)
        radios_layout.addWidget(self.profile_balanced)
        radios_layout.addWidget(self.profile_strong)

        # Add to row - takes up 50% roughly
        refine_layout.addWidget(radios_container, 1)

        self.refine_btn = QPushButton("Refine")
        self.refine_btn.setObjectName("secondaryButton")
        self.refine_btn.setFixedHeight(Dimensions.BUTTON_HEIGHT_SECONDARY)
        self.refine_btn.clicked.connect(self._on_refine_clicked)  # Local handler first

        # Refine button takes the other share
        refine_layout.addWidget(self.refine_btn, 1)

        self.refine_row.hide()
        layout.addWidget(self.refine_row)

    def _on_refine_clicked(self) -> None:
        """Determine selected profile and emit."""
        profile = "BALANCED"
        if self.profile_minimal.isChecked():
            profile = "MINIMAL"
        elif self.profile_strong.isChecked():
            profile = "STRONG"

        self.refineClicked.emit(profile)

    def update_for_idle(self) -> None:
        """Configure for idle state."""
        self.primary_btn.setText("Start")
        self.primary_btn.setEnabled(True)
        self.edit_save_btn.hide()
        self.refine_row.hide()
        self.destructive_btn.hide()

    def update_for_recording(self) -> None:
        """Configure for recording state."""
        self.primary_btn.setText("Stop")
        self.primary_btn.setEnabled(True)
        self.edit_save_btn.hide()
        self.refine_row.hide()
        self.destructive_btn.setText("Cancel")
        self.destructive_btn.setEnabled(True)
        self.destructive_btn.show()

    def update_for_viewing(self) -> None:
        """Configure for viewing state."""
        self.primary_btn.setText("Start")
        self.primary_btn.setEnabled(True)
        self.edit_save_btn.setText("Edit")
        self.edit_save_btn.setEnabled(True)
        self.edit_save_btn.show()

        # Show Refine button if feature is enabled
        if ConfigManager.get_config_value("refinement", "enabled"):
            self.refine_row.show()
            self.refine_btn.setEnabled(True)
        else:
            self.refine_row.hide()

        self.destructive_btn.setText("Delete")
        self.destructive_btn.setEnabled(True)
        self.destructive_btn.show()

    def update_for_editing(self) -> None:
        """Configure for editing state."""
        self.primary_btn.setText("Start")
        self.primary_btn.setEnabled(False)
        self.edit_save_btn.setText("Save")
        self.edit_save_btn.setEnabled(True)
        self.edit_save_btn.show()
        self.refine_row.hide()
        self.destructive_btn.setText("Cancel")
        self.destructive_btn.setEnabled(True)
        self.destructive_btn.show()
