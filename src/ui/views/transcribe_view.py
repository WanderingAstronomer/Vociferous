"""
TranscribeView - Dedicated view for active recording session.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.constants import Colors, Typography
from ui.constants.view_ids import VIEW_TRANSCRIBE
from ui.contracts.capabilities import ActionId, Capabilities
from ui.views.base_view import BaseView
from ui.widgets.waveform_visualizer import WaveformVisualizer
from ui.utils.clipboard_utils import copy_text


class TranscribeView(BaseView):
    """
    View for live recording and waveform visualization.
    
    Displays:
    - Live waveform
    - Optional live text streaming (if supported by engine)
    """
    
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_live_text = ""
        self._is_recording = False
        self._setup_ui()

    def get_view_id(self) -> str:
        return VIEW_TRANSCRIBE

    def get_capabilities(self) -> Capabilities:
        """
        Transcribe view capabilities:
        - Copy: Allowed if there is text.
        - Edit/Refine/Delete: Disabled (live buffer).
        """
        return Capabilities(
            can_copy=bool(self._current_live_text),
            can_edit=False,
            can_delete=False,
            can_refine=False,
            can_move_to_project=False,
            can_preview=False,
            can_export=False,
        )
    
    def dispatch_action(self, action_id: ActionId) -> None:
        """Handle standard actions."""
        if action_id == ActionId.COPY and self._current_live_text:
            copy_text(self._current_live_text)

    def _setup_ui(self) -> None:
        """Create layout with centered waveform and live text area."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        # Spacer
        layout.addStretch(1)
        
        # Waveform Container
        self.waveform = WaveformVisualizer()
        self.waveform.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.waveform.setFixedHeight(130)  # Match legacy WorkspaceContent height
        layout.addWidget(self.waveform)
        
        # Live Text Container
        self.lbl_live_text = QLabel()
        self.lbl_live_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_live_text.setWordWrap(True)
        # Use a slightly larger, easy to read font for live text
        font = self.lbl_live_text.font()
        font.setPointSize(Typography.BODY_SIZE)
        self.lbl_live_text.setFont(font)
        self.lbl_live_text.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        self.lbl_live_text.hide() # Hidden until text arrives
        
        layout.addWidget(self.lbl_live_text)
        
        # Status Label (Recording / Processing...)
        self.lbl_status = QLabel("Ready to Record")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        layout.addWidget(self.lbl_status)
        
        # Spacer
        layout.addStretch(1)

    # Public Slots for Controller

    @pyqtSlot(bool)
    def update_for_recording_state(self, is_recording: bool) -> None:
        """Start or stop the visualization."""
        self._is_recording = is_recording
        if is_recording:
            self.waveform.start()
            self.lbl_status.setText("Recording...")
            # Use Primary accent instead of Error for recording state
            self.lbl_status.setStyleSheet(f"color: {Colors.ACCENT_PRIMARY}; font-weight: bold;")
        else:
            self.waveform.stop()
            self.lbl_status.setText("Processing...")
            self.lbl_status.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
    
    @pyqtSlot(str)
    def set_live_text(self, text: str) -> None:
        """Update the live text display."""
        self._current_live_text = text
        if text:
            self.lbl_live_text.setText(text)
            self.lbl_live_text.show()
        else:
            self.lbl_live_text.clear()
            self.lbl_live_text.hide()

    @pyqtSlot(float)
    def set_audio_level(self, level: float) -> None:
        """Push audio level to visualizer."""
        if self._is_recording:
            self.waveform.current_level = level
