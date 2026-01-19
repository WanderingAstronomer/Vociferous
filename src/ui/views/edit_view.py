"""
EditView - Ephemeral editor view.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import pyqtSlot, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLabel, QMessageBox

import src.ui.constants.colors as c
from src.ui.constants import Typography, Spacing
from src.ui.constants.view_ids import VIEW_EDIT
from src.ui.contracts.capabilities import ActionId, Capabilities
from src.ui.views.base_view import BaseView

if TYPE_CHECKING:
    from src.database.history_manager import HistoryManager


class EditView(BaseView):
    """View for editing transcription text."""

    navigate_requested = pyqtSignal(str)  # Emitted to return to origin view
    transcript_updated = pyqtSignal(int, str)  # Emitted when text saved

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._history_manager: Optional[HistoryManager] = None
        self._current_id: Optional[int] = None
        self._origin_view: Optional[str] = None
        self._setup_ui()

    def set_history_manager(self, manager: HistoryManager) -> None:
        self._history_manager = manager

    def set_origin_view(self, view_id: str) -> None:
        """Set the view to return to after editing."""
        self._origin_view = view_id

    def get_view_id(self) -> str:
        return VIEW_EDIT

    def get_capabilities(self) -> Capabilities:
        return Capabilities(can_save=True, can_discard=True)  # All other False

    def dispatch_action(self, action_id: ActionId) -> None:
        if action_id == ActionId.SAVE:
            self._save_changes()
        elif action_id == ActionId.DISCARD:
            self._cancel_changes()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.S5, Spacing.S5, Spacing.S5, Spacing.S5)
        layout.setSpacing(Spacing.S3)

        # Header
        lbl_title = QLabel("Edit Transcription")
        lbl_title.setFont(
            QFont("Segoe UI", Typography.FONT_SIZE_XL, Typography.FONT_WEIGHT_BOLD)
        )
        lbl_title.setStyleSheet(f"color: {c.GRAY_4};")
        layout.addWidget(lbl_title)

        # Editor
        self._editor = QTextEdit()
        # Styling in unified_stylesheet.py (EditView QTextEdit)
        layout.addWidget(self._editor)

    def load_transcript_by_id(self, transcript_id: int) -> None:
        self._current_id = transcript_id
        if self._history_manager:
            entry = self._history_manager.get_entry(transcript_id)
            if entry:
                self._editor.setPlainText(entry.text)
            else:
                self._editor.setPlainText("Error: Transcript not found.")
                self._current_id = None

    def _cancel_changes(self) -> None:
        """Abandon changes and return to origin."""
        if self._origin_view:
            self.navigate_requested.emit(self._origin_view)

    @pyqtSlot()
    def _save_changes(self) -> None:
        if self._current_id is None or not self._history_manager:
            return

        new_text = self._editor.toPlainText()
        try:
            self._history_manager.update_text(self._current_id, new_text)
            self.capabilities_changed.emit()
            self.transcript_updated.emit(self._current_id, new_text)

            # Return to origin
            if self._origin_view:
                self.navigate_requested.emit(self._origin_view)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")
