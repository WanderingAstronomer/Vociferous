"""
EditView - Ephemeral editor view.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QLabel, QMessageBox
)

from ui.constants import Colors, Typography
from ui.constants.view_ids import VIEW_EDIT
from ui.contracts.capabilities import ActionId, Capabilities
from ui.views.base_view import BaseView

if TYPE_CHECKING:
    from history_manager import HistoryManager

class EditView(BaseView):
    """View for editing transcription text."""
    
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._history_manager: Optional[HistoryManager] = None
        self._current_id: Optional[int] = None
        self._setup_ui()

    def set_history_manager(self, manager: HistoryManager) -> None:
        self._history_manager = manager

    def get_view_id(self) -> str:
        return VIEW_EDIT
    
    def get_capabilities(self) -> Capabilities:
        return Capabilities(
            can_save=True,
            can_discard=True
        ) # All other False

    def dispatch_action(self, action_id: ActionId) -> None:
        if action_id == ActionId.SAVE:
            self._save_changes()
        elif action_id == ActionId.DISCARD or action_id == ActionId.CANCEL:
            # Revert or close? Usually Cancel -> Back to View.
            # Ideally navigate back.
            pass

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)
        
        # Header
        lbl_title = QLabel("Edit Transcription")
        lbl_title.setFont(QFont("Segoe UI", Typography.FONT_SIZE_XL, Typography.FONT_WEIGHT_BOLD))
        lbl_title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
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

    @pyqtSlot()
    def _save_changes(self) -> None:
        if self._current_id is None or not self._history_manager:
            return
            
        new_text = self._editor.toPlainText()
        try:
            self._history_manager.update_text(self._current_id, new_text)
            # Maybe emit a signal that we saved?
            self.capabilitiesChanged.emit()
            QMessageBox.information(self, "Saved", "Changes saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")
