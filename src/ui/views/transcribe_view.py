"""
TranscribeView - Dedicated view for active recording session.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSlot, QPropertyAnimation, QAbstractAnimation, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QFrame,
    QTextEdit,
    QGraphicsOpacityEffect
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
    
    Structure:
    - HeaderPanel (Welcome, MOTD)
    - MainPanel (Instruction, Status, Waveform, Preview)
    """

    editNormalizedText = pyqtSignal(int, str)
    
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_transcript = ""
        self._current_entry_id: int | None = None
        self._is_recording = False
        
        self._edit_timer = QTimer(self)
        self._edit_timer.setSingleShot(True)
        self._edit_timer.setInterval(1000) # 1 sec debounce
        self._edit_timer.timeout.connect(self._on_edit_timeout)
        
        self._setup_ui()

    def get_view_id(self) -> str:
        return VIEW_TRANSCRIBE

    def get_capabilities(self) -> Capabilities:
        return Capabilities(
            can_copy=bool(self._current_transcript),
            can_edit=bool(self._current_transcript),
            can_delete=False,
            can_refine=False,
            can_move_to_project=False,
            can_preview=False,
            can_export=False,
        )
    
    def dispatch_action(self, action_id: ActionId) -> None:
        if action_id == ActionId.COPY and self._current_transcript:
            copy_text(self._current_transcript)
        elif action_id == ActionId.EDIT:
             # Route to edit - typically handled by Main Window observing dispatch or signals
             # For now, we rely on standard contract. 
             # But BaseView doesn't emit editRequested automatically.
             # We should probably define a signal if we support edit from here.
             pass

    def _setup_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        
        # --- Header Panel ---
        self.header_panel = QFrame()
        self.header_panel.setObjectName("headerPanel")
        header_layout = QVBoxLayout(self.header_panel)
        header_layout.setContentsMargins(24, 24, 24, 24)
        header_layout.setSpacing(8)
        
        self.lbl_welcome = QLabel("Good morning, Andrew! Welcome to Vociferous.")
        self.lbl_welcome.setObjectName("welcomeLabel")
        self.lbl_welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_welcome.setFont(QFont("Segoe UI", Typography.FONT_SIZE_LG, Typography.FONT_WEIGHT_BOLD))
        
        self.lbl_motd = QLabel("Ready to capture your thoughts.")
        self.lbl_motd.setObjectName("motdLabel")
        self.lbl_motd.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        header_layout.addWidget(self.lbl_welcome)
        header_layout.addWidget(self.lbl_motd)
        
        root_layout.addWidget(self.header_panel)
        
        # --- Main Panel ---
        self.main_panel = QFrame()
        self.main_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.main_panel.setStyleSheet(f"background-color: {Colors.BACKGROUND};")
        main_layout = QVBoxLayout(self.main_panel)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(24)
        
        # Instruction
        self.lbl_instruction = QLabel("Press the microphone button or hotkey to start.")
        self.lbl_instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_instruction.setStyleSheet(f"color: {Colors.TEXT_TERTIARY};")
        main_layout.addWidget(self.lbl_instruction)
        
        # Recording Status with Blink
        self.lbl_recording_status = QLabel("RECORDING")
        self.lbl_recording_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_recording_status.setFont(QFont("Segoe UI", Typography.FONT_SIZE_XXL, Typography.FONT_WEIGHT_BOLD))
        self.lbl_recording_status.setStyleSheet(f"color: {Colors.DESTRUCTIVE}; letter-spacing: 2px;")
        self.lbl_recording_status.hide()
        
        # Blink Effect
        self._blink_effect = QGraphicsOpacityEffect(self.lbl_recording_status)
        self.lbl_recording_status.setGraphicsEffect(self._blink_effect)
        self._blink_anim = QPropertyAnimation(self._blink_effect, b"opacity")
        self._blink_anim.setDuration(1400)
        self._blink_anim.setStartValue(1.0)
        self._blink_anim.setEndValue(0.2)
        self._blink_anim.setLoopCount(-1) # Infinite
        self._blink_anim.setKeyValueAt(0.5, 0.2)
        self._blink_anim.setKeyValueAt(1.0, 1.0)
        
        main_layout.addWidget(self.lbl_recording_status)
        
        # Waveform
        self.waveform = WaveformVisualizer()
        self.waveform.setFixedHeight(120)
        self.waveform.hide()
        main_layout.addWidget(self.waveform)
        
        # Transcript Preview
        self.preview_browser = QTextEdit()
        self.preview_browser.setAcceptRichText(False)
        self.preview_browser.textChanged.connect(self._on_text_changed)
        # Styling in unified_stylesheet.py (TranscribeView QTextEdit)
        
        self.preview_browser.hide()
        main_layout.addWidget(self.preview_browser)
        
        main_layout.addStretch()
        
        root_layout.addWidget(self.main_panel)

    def set_recording_state(self, is_recording: bool) -> None:
        self._is_recording = is_recording
        if is_recording:
            self.lbl_instruction.hide()
            self.lbl_recording_status.show()
            self.waveform.show()
            self._blink_anim.start()
            self.preview_browser.hide()
            self.lbl_motd.setText("Listening...")
        else:
            self.lbl_instruction.show()
            self.lbl_recording_status.hide()
            self.waveform.hide()
            self._blink_anim.stop()
            self.lbl_motd.setText("Ready.")
            
    def set_transcript(self, id: int, text: str) -> None:
        self._current_entry_id = id
        self._current_transcript = text
        
        # Block signals to prevent triggering "edited" signal on load
        self.preview_browser.blockSignals(True)
        self.preview_browser.setPlainText(text)
        self.preview_browser.blockSignals(False)
        
        self.preview_browser.show()
        self.capabilitiesChanged.emit()

    @pyqtSlot()
    def _on_text_changed(self) -> None:
        self._edit_timer.start()

    @pyqtSlot()
    def _on_edit_timeout(self) -> None:
        if self._current_entry_id is None:
            return
            
        new_text = self.preview_browser.toPlainText()
        if new_text != self._current_transcript:
            self._current_transcript = new_text
            self.editNormalizedText.emit(self._current_entry_id, new_text)

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
