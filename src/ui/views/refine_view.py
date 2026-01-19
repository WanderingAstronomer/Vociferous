"""
RefineView - Interface for refinement and diffs.
"""

from __future__ import annotations


from PyQt6.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QWidget,
    QFrame,
    QPlainTextEdit,
    QSlider,
)
from PyQt6.QtCore import pyqtSignal, Qt

import src.ui.constants.colors as c
from src.ui.constants.view_ids import VIEW_REFINE
from src.ui.constants import Spacing
from src.ui.views.base_view import BaseView
from src.ui.contracts.capabilities import Capabilities, ActionId
from src.ui.components.shared import ContentPanel


from src.ui.views.refine_view_styles import get_refine_view_stylesheet


class RefineView(BaseView):
    """
    View for refining text and viewing differences.

    Displays side-by-side comparison of Original vs Refined text.
    Capabilities (can_accept, can_discard) are advertised via get_capabilities(),
    and ActionDock handles button presentation and dispatch_action() routing.
    """

    # Signals for routing back to controller/orchestrator
    refinement_accepted = pyqtSignal(int, str)  # transcript_id, refined_text
    refinement_discarded = pyqtSignal()  # No args needed - just return to history
    refinement_rerun_requested = pyqtSignal(
        int, str, str
    )  # transcript_id, profile, user_instruct

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_transcript_id: int | None = None
        self._original_text = ""
        self._refined_text = ""
        self._is_loading = False
        self._profiles = ["MINIMAL", "BALANCED", "STRONG", "OVERKILL"]

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
        footer_layout.setSpacing(Spacing.S4)  # Gap between Input and Action Strip

        # 1. User Prompt Input (Left/Center - Expanding)
        self._user_prompt_input = QPlainTextEdit()
        self._user_prompt_input.setPlaceholderText(
            "Add specific instructions (e.g., 'Make it bullet points', 'Fix technical jargon')..."
        )
        self._user_prompt_input.setMinimumHeight(80)
        self._user_prompt_input.setMaximumHeight(120)
        self._user_prompt_input.setStyleSheet(
            f"border: 1px solid {c.GRAY_6}; border-radius: 4px; padding: 6px; background: {c.GRAY_8}; margin: 0px;"
        )
        footer_layout.addWidget(self._user_prompt_input, 1)

        # 2. Refinement Action Strip (Right - Strength Slider Group)
        action_strip = QWidget()
        strip_layout = QVBoxLayout(action_strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(4)
        strip_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)

        # Microcopy FIRST (top of the stack)
        self._lbl_microcopy = QLabel("Controls how aggressively the text is rewritten")
        self._lbl_microcopy.setStyleSheet(
            f"color: {c.GRAY_5}; font-size: 10px; font-style: italic;"
        )
        self._lbl_microcopy.setAlignment(Qt.AlignmentFlag.AlignRight)
        strip_layout.addWidget(self._lbl_microcopy)

        # Strength Group (Label + Slider) - full width now
        strength_container = QWidget()
        strength_layout = QVBoxLayout(strength_container)
        strength_layout.setContentsMargins(0, 0, 0, 0)
        strength_layout.setSpacing(2)

        # Label Row
        lbl_layout = QHBoxLayout()
        lbl_layout.setSpacing(4)
        lbl_layout.addStretch()  # Center the labels

        lbl_strength_title = QLabel("Strength:")
        lbl_strength_title.setStyleSheet(f"color: {c.GRAY_5}; font-size: 10px;")

        self._lbl_strength_value = QLabel("BALANCED")
        self._lbl_strength_value.setStyleSheet(
            f"color: {c.BLUE_3}; font-size: 10px; font-weight: bold;"
        )

        lbl_layout.addWidget(lbl_strength_title)
        lbl_layout.addWidget(self._lbl_strength_value)
        lbl_layout.addStretch()

        strength_layout.addLayout(lbl_layout)

        # Slider (Muted track color, accent thumb) - wider now
        self.slider_strength = QSlider(Qt.Orientation.Horizontal)
        self.slider_strength.setRange(0, 3)
        self.slider_strength.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_strength.setTickInterval(1)
        self.slider_strength.setValue(1)
        self.slider_strength.setMinimumWidth(180)  # Wider than before
        self.slider_strength.valueChanged.connect(self._update_strength_label)
        # Apply specific styling to subordinate visual dominance
        self.slider_strength.setStyleSheet(get_refine_view_stylesheet())
        strength_layout.addWidget(self.slider_strength)

        strip_layout.addWidget(strength_container)

        footer_layout.addWidget(action_strip)

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

    def _update_controls_state(self) -> None:
        """Update visual state of controls based on context."""
        has_transcript = self._current_transcript_id is not None
        can_interact = has_transcript and not self._is_loading

        self.slider_strength.setEnabled(can_interact)
        self._user_prompt_input.setEnabled(can_interact)

        # Microcopy visibility
        self._lbl_microcopy.setVisible(can_interact)

        # Visual styling for strength label
        if can_interact:
            # Wake up slider visual
            self._lbl_strength_value.setStyleSheet(
                f"color: {c.BLUE_3}; font-size: 10px; font-weight: bold;"
            )
        else:
            # Mute slider visual
            self._lbl_strength_value.setStyleSheet(
                f"color: {c.GRAY_5}; font-size: 10px;"
            )

    def _update_strength_label(self, value: int) -> None:
        if 0 <= value < len(self._profiles):
            self._lbl_strength_value.setText(self._profiles[value])

    def set_loading(self, is_loading: bool) -> None:
        """Set loading state."""
        self._is_loading = is_loading
        self._lbl_loading.setVisible(is_loading)
        self._update_controls_state()
        self.capabilities_changed.emit()

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
        self._update_controls_state()

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
        self._update_controls_state()

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
        self._update_controls_state()

    def _on_accept(self) -> None:
        """Handle acceptance of refinement (via dispatch_action)."""
        if self._current_transcript_id is not None:
            # Emit both ID and TEXT
            self.refinement_accepted.emit(
                self._current_transcript_id, self._refined_text
            )
            self._panel_refined.set_entry(None)

    def _on_discard(self) -> None:
        """Handle discard of refinement (via dispatch_action)."""
        self._panel_original.set_entry(None)
        self._panel_refined.set_entry(None)
        self.refinement_discarded.emit()

    def get_view_id(self) -> str:
        return VIEW_REFINE

    def get_capabilities(self) -> Capabilities:
        """
        Advertise capabilities based on refinement state.
        ActionDock will present buttons and route through dispatch_action().
        """
        if self._is_loading:
            return Capabilities()  # No actions while loading

        has_transcript = self._current_transcript_id is not None
        has_refined_content = bool(self._refined_text)

        return Capabilities(
            can_refine=has_transcript,  # Can run refinement if transcript loaded
            can_copy=has_refined_content,
            can_save=has_refined_content,  # Accept refinement (uses SAVE semantically)
            can_discard=True,  # Always allow discard (exit)
        )

    def dispatch_action(self, action_id: ActionId) -> None:
        """Handle actions dispatched by ActionDock."""
        # Functional gating: Ignore actions while loading
        if self._is_loading:
            return

        if action_id == ActionId.REFINE:
            self._on_refine_clicked()
        elif action_id == ActionId.SAVE:
            self._on_accept()
        elif action_id == ActionId.DISCARD:
            self._on_discard()
        elif action_id == ActionId.COPY:
            # Copy refined text to clipboard
            from src.ui.utils.clipboard_utils import copy_text

            copy_text(self._refined_text)

    def _on_refine_clicked(self) -> None:
        """Handle Refine button click from ActionDock."""
        if self._current_transcript_id is not None:
            user_instructions = self._user_prompt_input.toPlainText().strip()
            # Map slider value to profile string
            val = self.slider_strength.value()
            profile = (
                self._profiles[val] if 0 <= val < len(self._profiles) else "BALANCED"
            )

            self.refinement_rerun_requested.emit(
                self._current_transcript_id, profile, user_instructions
            )
