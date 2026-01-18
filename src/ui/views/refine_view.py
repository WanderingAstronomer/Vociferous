"""
RefineView - Interface for refinement and diffs.
"""

from __future__ import annotations


from PyQt6.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QWidget,
    QPushButton,
    QFrame,
    QPlainTextEdit,
    QSlider,
)
from PyQt6.QtCore import pyqtSignal, Qt

import ui.constants.colors as c
from ui.constants.view_ids import VIEW_REFINE
from ui.constants import Spacing
from ui.views.base_view import BaseView
from ui.contracts.capabilities import Capabilities, ActionId
from ui.components.shared import ContentPanel


class RefineView(BaseView):
    """
    View for refining text and viewing differences.

    Displays side-by-side comparison of Original vs Refined text.
    Capabilities (can_accept, can_discard) are advertised via get_capabilities(),
    and ActionDock handles button presentation and dispatch_action() routing.
    """

    # Signals for routing back to controller/orchestrator
    refinementAccepted = pyqtSignal(int, str)  # transcript_id, refined_text
    refinementDiscarded = pyqtSignal()  # No args needed - just return to history
    refinementRerunRequested = pyqtSignal(
        int, str, str
    )  # transcript_id, profile, user_instruct

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_transcript_id: int | None = None
        self._original_text = ""
        self._refined_text = ""
        self._is_loading = False
        self._profiles = ["MINIMAL", "BALANCED", "STRONG"]

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(Spacing.S4, Spacing.S4, Spacing.S4, Spacing.S4)
        main_layout.setSpacing(Spacing.S4)

        # --- Comparison Area ---
        comparison_layout = QHBoxLayout()
        comparison_layout.setSpacing(Spacing.S4)

        # Left: Original
        self._panel_original = ContentPanel()
        comparison_layout.addWidget(self._panel_original, 1)

        # Right: Refined
        self._panel_refined = ContentPanel()
        comparison_layout.addWidget(self._panel_refined, 1)

        main_layout.addLayout(comparison_layout, 1)

        # --- Divider ---
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        divider.setStyleSheet(
            f"background-color: {c.GRAY_7}; margin-top: 4px; margin-bottom: 4px;"
        )
        main_layout.addWidget(divider)

        # --- Footer Area (Controls + Input) ---
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(
            Spacing.S2
        )  # Reduced spacing (margins) for tighter integration

        # 1. Strength Controls (Left of input)
        strength_container = QWidget()
        strength_layout = QVBoxLayout(strength_container)
        strength_layout.setContentsMargins(0, 0, 0, 0)
        strength_layout.setSpacing(2)

        strength_layout.addStretch()  # Center vertically

        # Label
        lbl_strength = QLabel("Strength")
        lbl_strength.setStyleSheet(
            f"color: {c.GRAY_4}; font-size: 10px; font-weight: bold;"
        )
        strength_layout.addWidget(lbl_strength)

        # Slider
        self.slider_strength = QSlider(Qt.Orientation.Horizontal)
        self.slider_strength.setRange(0, 2)
        self.slider_strength.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_strength.setTickInterval(1)
        self.slider_strength.setValue(1)
        self.slider_strength.setFixedWidth(120)  # Increased width
        self.slider_strength.valueChanged.connect(self._update_strength_label)
        strength_layout.addWidget(self.slider_strength)

        # Value Label
        self._lbl_strength_value = QLabel("BALANCED")
        self._lbl_strength_value.setStyleSheet(
            f"color: {c.BLUE_3}; font-size: 10px; font-weight: bold;"
        )
        strength_layout.addWidget(self._lbl_strength_value)

        strength_layout.addStretch()  # Center vertically

        footer_layout.addWidget(strength_container)

        # 2. User Prompt Input (Center)
        self._user_prompt_input = QPlainTextEdit()
        self._user_prompt_input.setPlaceholderText(
            "Add specific instructions (e.g., 'Make it bullet points', 'Fix technical jargon')..."
        )
        # Taller input box for more text visibility
        self._user_prompt_input.setMinimumHeight(100)
        self._user_prompt_input.setMaximumHeight(150)
        # Margin 0 to ensure no extra whitespace pushes neighbors
        self._user_prompt_input.setStyleSheet(
            f"border: 1px solid {c.GRAY_6}; border-radius: 4px; padding: 4px; background: {c.GRAY_8}; margin: 0px;"
        )
        footer_layout.addWidget(self._user_prompt_input, 1)

        # 3. Rerun Button (Right of input)
        # Wrap in layout/widget to align it properly (e.g. center vertical)
        rerun_container = QWidget()
        rerun_layout = QVBoxLayout(rerun_container)
        rerun_layout.setContentsMargins(0, 0, 0, 0)
        rerun_layout.addStretch()  # Push button to vertical center

        self.btn_rerun = QPushButton("Retry?")
        self.btn_rerun.clicked.connect(self._on_rerun_clicked)
        self.btn_rerun.setFixedWidth(100)  # Increased width
        self.btn_rerun.setStyleSheet("padding: 8px; font-weight: bold;")

        rerun_layout.addWidget(self.btn_rerun)
        rerun_layout.addStretch()

        footer_layout.addWidget(rerun_container)

        main_layout.addLayout(footer_layout)

        # Loading Overlay (placeholder for now, can be sophisticated later)
        self._lbl_loading = QLabel("Refining...", self)
        self._lbl_loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_loading.setStyleSheet(
            f"background: {c.OVERLAY_BACKDROP}; color: white; font-size: 24px; border-radius: 8px;"
        )
        self._lbl_loading.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._lbl_loading.resize(self.size())

    def _update_strength_label(self, value: int) -> None:
        if 0 <= value < len(self._profiles):
            self._lbl_strength_value.setText(self._profiles[value])

    def set_loading(self, is_loading: bool) -> None:
        """Set loading state."""
        self._is_loading = is_loading
        self._lbl_loading.setVisible(is_loading)
        self.capabilitiesChanged.emit()

    def _on_rerun_clicked(self) -> None:
        """Handle re-run button click."""
        if self._current_transcript_id is not None:
            user_instructions = self._user_prompt_input.toPlainText().strip()
            # Map slider value to profile string
            val = self.slider_strength.value()
            profile = (
                self._profiles[val] if 0 <= val < len(self._profiles) else "BALANCED"
            )

            self.refinementRerunRequested.emit(
                self._current_transcript_id, profile, user_instructions
            )

    def _make_dummy_entry(self, text: str, title: str):
        """Create a duck-typed object that resembles HistoryEntry for ContentPanel."""
        from types import SimpleNamespace

        return SimpleNamespace(text=text, display_name=title, timestamp="")

    def load_transcript_by_id(self, transcript_id: int, text: str) -> None:
        """
        Load transcript by ID and prepare for refinement.
        Does NOT run the engine; MainWindow must do that.
        """
        self._current_transcript_id = transcript_id
        self._original_text = text
        self._refined_text = ""

        self._panel_original.set_entry(
            self._make_dummy_entry(text, "Original Transcript")
        )
        self._panel_refined.set_entry(
            self._make_dummy_entry("", "Refinement Pending...")
        )

        # Reset loading state (caller will set it if they start engine immediately)
        self.set_loading(False)

    def set_comparison(self, transcript_id: int, original: str, refined: str) -> None:
        """Load data for comparison."""
        self._current_transcript_id = transcript_id
        self._original_text = original
        self._refined_text = refined
        self.set_loading(False)

        self._panel_original.set_entry(
            self._make_dummy_entry(original, "Original Transcript")
        )
        self._panel_refined.set_entry(
            self._make_dummy_entry(refined, "Refined / AI Suggestion")
        )

    def load_transcript(self, text: str, timestamp: str | None = None) -> None:
        """
        Load initial transcript text (Legacy/Generic support).
        """
        self._original_text = text
        self._refined_text = ""
        self._current_transcript_id = None
        self.set_loading(False)

        self._panel_original.set_entry(
            self._make_dummy_entry(text, "Original Transcript")
        )
        self._panel_refined.set_entry(
            self._make_dummy_entry("", "Refinement Pending...")
        )

    def _on_accept(self) -> None:
        """Handle acceptance of refinement (via dispatch_action)."""
        if self._current_transcript_id is not None:
            # Emit both ID and TEXT
            self.refinementAccepted.emit(
                self._current_transcript_id, self._refined_text
            )
            self._panel_refined.set_entry(None)

    def _on_discard(self) -> None:
        """Handle discard of refinement (via dispatch_action)."""
        self._panel_original.set_entry(None)
        self._panel_refined.set_entry(None)
        self.refinementDiscarded.emit()

    def get_view_id(self) -> str:
        return VIEW_REFINE

    def get_capabilities(self) -> Capabilities:
        """
        Advertise capabilities based on refinement state.
        ActionDock will present buttons and route through dispatch_action().
        """
        if self._is_loading:
            return Capabilities()  # No actions while loading

        has_content = bool(self._refined_text)
        return Capabilities(
            can_copy=has_content,
            can_save=has_content,  # Accept refinement (uses SAVE semantically)
            can_discard=True,  # Always allow discard (exit)
        )

    def dispatch_action(self, action_id: ActionId) -> None:
        """Handle actions dispatched by ActionDock."""
        # Functional gating: Ignore actions while loading
        if self._is_loading:
            return

        if action_id == ActionId.SAVE:
            self._on_accept()
        elif action_id == ActionId.DISCARD:
            self._on_discard()
        elif action_id == ActionId.COPY:
            # Copy refined text to clipboard
            from ui.utils.clipboard_utils import copy_text

            copy_text(self._refined_text)
