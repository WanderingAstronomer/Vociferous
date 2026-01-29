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
)
from PyQt6.QtCore import pyqtSignal, Qt

import src.ui.constants.colors as c
from src.ui.constants.view_ids import VIEW_REFINE
from src.ui.constants import Spacing, Typography
from src.ui.views.base_view import BaseView
from src.ui.contracts.capabilities import Capabilities, ActionId
from src.ui.components.shared.content_panel import ContentPanel
from src.ui.widgets.strength_selector import StrengthSelector
from src.ui.styles.refine_view_styles import get_refine_card_stylesheet


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

        # --- Footer Area (Two Cards Side-by-Side) ---
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(Spacing.MAJOR_GAP)

        # Left Card: Custom Instructions
        instructions_card = self._create_card()
        instructions_layout = QVBoxLayout(instructions_card)
        instructions_layout.setContentsMargins(
            Spacing.MAJOR_GAP, Spacing.MAJOR_GAP, Spacing.MAJOR_GAP, Spacing.MAJOR_GAP
        )
        instructions_layout.setSpacing(Spacing.MINOR_GAP)

        # Label
        lbl_instructions = QLabel("Custom Instructions")
        lbl_instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_instructions.setStyleSheet(
            f"color: {c.GRAY_3}; font-size: {Typography.FONT_SIZE_MD}px; "
            f"font-weight: bold; border: none; background: transparent; padding: 0px;"
        )
        instructions_layout.addWidget(lbl_instructions)

        # Input
        self._user_prompt_input = QPlainTextEdit()
        self._user_prompt_input.setPlaceholderText(
            "Add specific instructions (e.g., 'Make it bullet points', 'Fix technical jargon')..."
        )
        self._user_prompt_input.setStyleSheet(
            f"border: 1px solid {c.BLUE_4}; border-radius: 4px; "
            f"padding: {Spacing.MINOR_GAP}px; background: {c.GRAY_8}; color: {c.GRAY_3};"
        )
        instructions_layout.addWidget(self._user_prompt_input, 1)

        footer_layout.addWidget(instructions_card, 2)

        # Right Card: Refinement Strength
        strength_card = self._create_card()
        strength_layout = QVBoxLayout(strength_card)
        strength_layout.setContentsMargins(
            Spacing.MAJOR_GAP, Spacing.MAJOR_GAP, Spacing.MAJOR_GAP, Spacing.MAJOR_GAP
        )
        strength_layout.setSpacing(Spacing.MINOR_GAP)

        # Label
        lbl_strength = QLabel("Refinement Strength")
        lbl_strength.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_strength.setStyleSheet(
            f"color: {c.GRAY_3}; font-size: {Typography.FONT_SIZE_MD}px; "
            f"font-weight: bold; border: none; background: transparent; padding: 0px;"
        )
        strength_layout.addWidget(lbl_strength)

        # Strength Selector Widget
        self._strength_selector = StrengthSelector()
        strength_layout.addWidget(self._strength_selector, 1)

        footer_layout.addWidget(strength_card, 1)

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

    def _create_card(self) -> QFrame:
        """Create a styled card container matching Settings/User view quality."""
        card = QFrame()
        card.setFrameShape(QFrame.Shape.NoFrame)
        card.setStyleSheet(get_refine_card_stylesheet())
        return card

    def _update_controls_state(self) -> None:
        """Update visual state of controls based on context."""
        has_transcript = self._current_transcript_id is not None
        can_interact = has_transcript and not self._is_loading

        self._strength_selector.setEnabled(can_interact)
        self._user_prompt_input.setEnabled(can_interact)

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
            profile = self._strength_selector.get_value()

            self.refinement_rerun_requested.emit(
                self._current_transcript_id, profile, user_instructions
            )
