"""
RefineView - Interface for refinement and diffs.
"""

from __future__ import annotations


from PyQt6.QtWidgets import (
    QHBoxLayout, 
    QVBoxLayout, 
    QTextEdit, 
    QLabel, 
    QWidget,
    QPushButton,
    QSplitter,
    QFrame
)
from PyQt6.QtCore import Qt, pyqtSlot

from ui.constants.view_ids import VIEW_REFINE
from ui.views.base_view import BaseView
from ui.contracts.capabilities import Capabilities
from ui.constants import Colors

class RefineView(BaseView):
    """
    View for refining text and viewing differences.
    
    Displays side-by-side comparison of Original vs Refined text.
    Allows Accepting or Discarding the refinement.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_transcript_id: int | None = None
        self._original_text = ""
        self._refined_text = ""
        
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Title
        self._lbl_title = QLabel("Refinement Review")
        self._lbl_title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {Colors.TEXT_PRIMARY};")
        layout.addWidget(self._lbl_title)
        
        # Splitter for Side-by-Side
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        
        # Left: Original
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0,0,0,0)
        lbl_orig = QLabel("Original")
        lbl_orig.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-weight: bold;")
        self._txt_original = QTextEdit()
        self._txt_original.setReadOnly(True)
        self._txt_original.setStyleSheet("background: #2D2D2D; border: 1px solid #444;")
        left_layout.addWidget(lbl_orig)
        left_layout.addWidget(self._txt_original)
        
        # Right: Refined
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0,0,0,0)
        lbl_new = QLabel("Refined / AI Suggestion")
        lbl_new.setStyleSheet(f"color: {Colors.ACCENT_BLUE}; font-weight: bold;")
        self._txt_refined = QTextEdit()
        self._txt_refined.setReadOnly(True) # User reviews first
        self._txt_refined.setStyleSheet("background: #25303B; border: 1px solid #3A4A5B;")
        right_layout.addWidget(lbl_new)
        right_layout.addWidget(self._txt_refined)
        
        splitter.addWidget(left_container)
        splitter.addWidget(right_container)
        layout.addWidget(splitter)
        
        # Actions Bar
        actions_layout = QHBoxLayout()
        actions_layout.addStretch()
        
        self._btn_discard = QPushButton("Discard")
        self._btn_discard.clicked.connect(self._on_discard)
        self._btn_discard.setStyleSheet("background: #444; color: white; padding: 8px 16px;")
        
        self._btn_accept = QPushButton("Accept Changes")
        self._btn_accept.clicked.connect(self._on_accept)
        self._btn_accept.setStyleSheet(f"background: {Colors.ACCENT_BLUE}; color: white; padding: 8px 16px; font-weight: bold;")
        
        actions_layout.addWidget(self._btn_discard)
        actions_layout.addWidget(self._btn_accept)
        
        layout.addLayout(actions_layout)

    def set_comparison(self, transcript_id: int, original: str, refined: str) -> None:
        """Load data for comparison."""
        self._current_transcript_id = transcript_id
        self._original_text = original
        self._refined_text = refined
        
        self._txt_original.setText(original)
        self._txt_refined.setText(refined)
        
        # Simple simplistic "diff" visual could be added here
        # For now, just plain text

    def _on_accept(self) -> None:
        """Emit intent to save this refinement as the main text."""
        # TODO: Implement wiring to Controller
        pass

    def _on_discard(self) -> None:
        """Switch back to history or clear."""
        # TODO: Implement wiring to Controller
        pass

    def get_view_id(self) -> str:
        return VIEW_REFINE
        
    def get_capabilities(self) -> Capabilities:
        return Capabilities(
            can_copy=True,
            can_edit=False, # It's a review view
            can_delete=False
        )

