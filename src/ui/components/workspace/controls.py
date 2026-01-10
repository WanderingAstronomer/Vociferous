"""
WorkspaceControls - Button cluster for workspace actions.

Primary action button (Start/Stop) and secondary buttons (Edit, Save, Cancel, Delete).
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.constants import Dimensions, Spacing


class WorkspaceControls(QWidget):
    """
    Control button cluster for workspace actions.

    Emits signals for button clicks; parent handles state logic.

    Signals:
        primaryClicked(): Start/Stop button clicked
        editSaveClicked(): Edit/Save button clicked
        destructiveClicked(): Cancel/Delete button clicked
        refineClicked(): Refine button clicked
    """

    primaryClicked = pyqtSignal()
    editSaveClicked = pyqtSignal()
    destructiveClicked = pyqtSignal()
    refineClicked = pyqtSignal()

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

        # Optional refinement button (hidden until feature enabled)
        self.refine_btn = QPushButton("Refine")
        self.refine_btn.setObjectName("secondaryButton")
        self.refine_btn.setFixedHeight(Dimensions.BUTTON_HEIGHT_SECONDARY)
        self.refine_btn.clicked.connect(self.refineClicked.emit)
        self.refine_btn.hide()
        layout.addWidget(self.refine_btn)

    def update_for_idle(self) -> None:
        """Configure for idle state."""
        self.primary_btn.setText("Start")
        self.primary_btn.setEnabled(True)
        self.edit_save_btn.hide()
        self.refine_btn.hide()
        self.destructive_btn.hide()

    def update_for_recording(self) -> None:
        """Configure for recording state."""
        self.primary_btn.setText("Stop")
        self.primary_btn.setEnabled(True)
        self.edit_save_btn.hide()
        self.refine_btn.hide()
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
        self.refine_btn.hide()
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
        self.refine_btn.hide()
        self.destructive_btn.setText("Cancel")
        self.destructive_btn.setEnabled(True)
        self.destructive_btn.show()
