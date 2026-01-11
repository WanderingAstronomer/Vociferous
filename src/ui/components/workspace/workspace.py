"""
MainWorkspace - State-driven main workspace canvas.

States:
- IDLE: Welcome greeting, start button, description
- RECORDING: Recording indicator, stop button
- VIEWING: Transcript display, edit button
- EDITING: Editable transcript, save button
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.constants import Dimensions, Spacing, Typography, WorkspaceState
from ui.utils.clipboard_utils import copy_text
from ui.widgets.content_panel import ContentPanel
from ui.interaction import (
    InteractionIntent,
    IntentOutcome,
    IntentResult,
    IntentSource,
    BeginRecordingIntent,
    StopRecordingIntent,
    CancelRecordingIntent,
    ViewTranscriptIntent,
    EditTranscriptIntent,
    CommitEditsIntent,
    DiscardEditsIntent,
    DeleteTranscriptIntent,
)

from ui.components.workspace.content import WorkspaceContent
from ui.components.workspace.controls import WorkspaceControls
from ui.components.workspace.header import WorkspaceHeader

if TYPE_CHECKING:
    from history_manager import HistoryEntry, HistoryManager

logger = logging.getLogger(__name__)


class MainWorkspace(QWidget):
    """
    State-driven main workspace canvas.

    Orchestrates atomic components and handles state transitions.

    Signals:
        startRequested(): Recording should start
        stopRequested(): Recording should stop
        cancelRequested(): Current action should be cancelled
        saveRequested(str): Edited text should be saved
        deleteRequested(): Current entry should be deleted
        refineRequested(): Transcript refinement requested
        textEdited(): Text was edited
    """

    startRequested = pyqtSignal()
    stopRequested = pyqtSignal()
    cancelRequested = pyqtSignal()
    saveRequested = pyqtSignal(str)
    deleteRequested = pyqtSignal()
    refineRequested = pyqtSignal()
    textEdited = pyqtSignal()

    # Intent processing signal (Phase 2: observability only)
    intentProcessed = pyqtSignal(object)  # IntentResult

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("mainWorkspace")
        self.setAutoFillBackground(True)  # Ensure background is painted

        self._state = WorkspaceState.IDLE
        self._has_unsaved_changes = False
        self._history_manager = None

        self._setup_ui()
        self._connect_signals()
        self._update_for_state()

    def _setup_ui(self) -> None:
        """Create workspace layout with full-width content."""
        # Styles are applied at app level via generate_unified_stylesheet()
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(
            Spacing.CONTENT_COLUMN_OUTER,
            Spacing.WORKSPACE,
            Spacing.CONTENT_COLUMN_OUTER,
            Spacing.WORKSPACE,
        )
        outer_layout.setSpacing(0)

        # Content column (expands to fill available space)
        self.content_column = QWidget()
        self.content_column.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        layout = QVBoxLayout(self.content_column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header component (fixed height, no stretch)
        self.header = WorkspaceHeader()
        layout.addWidget(self.header, 0)
        layout.addSpacing(Spacing.HEADER_CONTROLS_GAP)

        # Metrics display (above content panel, hidden by default)
        from ui.components.workspace.transcript_metrics import TranscriptMetrics
        self.metrics = TranscriptMetrics()
        self.metrics.hide()
        layout.addWidget(self.metrics, 0)
        layout.addSpacing(Spacing.MINOR_GAP)

        # Content panel (visual container) - EXPANDS TO FILL ALL REMAINING SPACE
        self._setup_content_panel(layout)

        layout.addSpacing(Spacing.CONTROLS_CONTENT_GAP)

        # Hotkey hint (fixed height, no stretch)
        self.hotkey_hint = QLabel("Press Alt to start recording")
        self.hotkey_hint.setObjectName("hotkeyHint")
        self.hotkey_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_font = QFont()
        hint_font.setPointSize(Typography.SMALL_SIZE)
        self.hotkey_hint.setFont(hint_font)
        layout.addWidget(self.hotkey_hint, 0)

        layout.addSpacing(Spacing.CONTROLS_CONTENT_GAP)

        # Controls component (fixed height, no stretch)
        self.controls = WorkspaceControls()
        layout.addWidget(self.controls, 0)

        outer_layout.addWidget(self.content_column, 1)


    def _setup_content_panel(self, parent_layout: QVBoxLayout) -> None:
        """Create visual content panel container."""
        self.content_panel = ContentPanel()
        self.content_panel.setObjectName("contentPanelPainted")
        # Content panel expands vertically to fill available space
        self.content_panel.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )

        panel_layout = QVBoxLayout(self.content_panel)
        panel_layout.setContentsMargins(
            Spacing.CONTENT_PANEL,
            Spacing.CONTENT_PANEL,
            Spacing.CONTENT_PANEL,
            Spacing.CONTENT_PANEL + 6,
        )
        panel_layout.setSpacing(0)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setObjectName("workspaceScrollArea")
        scroll.setViewportMargins(0, 0, 0, 4)
        self.content_scroll = scroll

        # Content component
        self.content = WorkspaceContent()
        scroll.setWidget(self.content)

        panel_layout.addWidget(scroll)
        parent_layout.addWidget(self.content_panel, 1)  # Stretch=1: claim all vertical space

    def _connect_signals(self) -> None:
        """Wire up component signals to workspace handlers."""
        self.controls.primaryClicked.connect(self._on_primary_click)
        self.controls.editSaveClicked.connect(self._on_edit_save_click)
        self.controls.destructiveClicked.connect(self._on_destructive_click)
        self.controls.refineClicked.connect(self.refineRequested.emit)

        self.content.textChanged.connect(self._on_text_changed)
        self.content.editRequested.connect(self._on_edit_save_click)
        self.content.deleteRequested.connect(self._on_destructive_click)

    def _update_for_state(self) -> None:
        """Update all components for current state."""
        is_editing = self._state == WorkspaceState.EDITING
        is_recording = self._state == WorkspaceState.RECORDING

        self.content_panel.setProperty("editing", is_editing)
        self.content_panel.setProperty("recording", is_recording)
        self.content_panel.style().unpolish(self.content_panel)
        self.content_panel.style().polish(self.content_panel)
        self.content_panel.update()

        match self._state:
            case WorkspaceState.IDLE:
                self.header.set_state(self._state)
                self.header.update_for_idle()
                self.controls.update_for_idle()
                self.content.update_for_idle()
                self.hotkey_hint.setText("Press Alt to start recording")
                self.metrics.hide()
                self.content_scroll.setVerticalScrollBarPolicy(
                    Qt.ScrollBarPolicy.ScrollBarAlwaysOff
                )

            case WorkspaceState.RECORDING:
                self.header.set_state(self._state)
                self.header.update_for_recording()
                self.controls.update_for_recording()
                self.content.update_for_recording()
                self.hotkey_hint.setText("Press Alt to stop recording")
                self.metrics.hide()
                self.content_scroll.setVerticalScrollBarPolicy(
                    Qt.ScrollBarPolicy.ScrollBarAlwaysOff
                )
                # Ensure the waveform is fully visible even if the scroll area was
                # previously scrolled in VIEWING/EDITING.
                self.content_scroll.verticalScrollBar().setValue(0)

            case WorkspaceState.VIEWING:
                self.header.set_state(self._state)
                self.header.update_for_viewing()
                self.controls.update_for_viewing()
                self.content.update_for_viewing()
                self.hotkey_hint.setText("Press Alt to start recording")
                # Metrics visibility is handled in load_transcript/display_new_transcript
                self.content_scroll.setVerticalScrollBarPolicy(
                    Qt.ScrollBarPolicy.ScrollBarAsNeeded
                )

            case WorkspaceState.EDITING:
                self.header.set_state(self._state)
                self.header.update_for_editing()
                self.controls.update_for_editing()
                self.content.update_for_editing()
                self.hotkey_hint.setText("Press Alt to start recording")
                self.metrics.hide()
                self.content_scroll.setVerticalScrollBarPolicy(
                    Qt.ScrollBarPolicy.ScrollBarAsNeeded
                )

    # Public API

    def set_history_manager(self, manager) -> None:
        """Set history manager for fetching transcript metadata."""
        self._history_manager = manager

    def set_state(self, state: WorkspaceState) -> None:
        """Change workspace state."""
        try:
            self._state = state
            self._update_for_state()
        except Exception as e:
            logger.exception("Error setting workspace state")

    def get_state(self) -> WorkspaceState:
        """Return current state."""
        return self._state

    def load_transcript(self, text: str, timestamp: str) -> None:
        """Load a transcript for viewing/editing."""
        try:
            # Try to fetch duration and speech_duration from history manager
            duration_ms = None
            speech_duration_ms = None
            if self._history_manager:
                entry = self._history_manager.get_entry_by_timestamp(timestamp)
                if entry:
                    duration_ms = entry.duration_ms
                    speech_duration_ms = entry.speech_duration_ms
            
            self.content.set_transcript(text, timestamp)
            self.header.set_timestamp(timestamp)
            self._has_unsaved_changes = False

            # Update metrics if we have duration data
            if text and duration_ms is not None:
                word_count = len(text.split())
                self.metrics.set_metrics(duration_ms, speech_duration_ms, word_count)
                self.metrics.show()
            else:
                self.metrics.hide()

            if text:
                self.set_state(WorkspaceState.VIEWING)
            else:
                self.set_state(WorkspaceState.IDLE)
        except Exception as e:
            logger.exception("Error loading transcript")
            raise

    def display_new_transcript(self, entry: HistoryEntry) -> None:
        """Display a newly created transcript."""
        try:
            self.content.set_transcript(entry.text, entry.timestamp)
            self.header.set_timestamp(entry.timestamp)
            self._has_unsaved_changes = False
            
            # Update metrics with entry data
            if entry.text and entry.duration_ms is not None:
                word_count = len(entry.text.split())
                self.metrics.set_metrics(entry.duration_ms, entry.speech_duration_ms, word_count)
                self.metrics.show()
            else:
                self.metrics.hide()
            
            self.set_state(WorkspaceState.VIEWING)
        except Exception as e:
            logger.exception("Error displaying new transcript")
            raise

    def show_transcribing_status(self) -> None:
        """Show transcribing indicator (after recording stops)."""
        try:
            self.header.update_for_transcribing()
        except Exception as e:
            logger.exception("Error showing transcribing status")

    def get_current_text(self) -> str:
        """Return current transcript text."""
        try:
            return self.content.get_text()
        except Exception as e:
            logger.exception("Error getting current text")
            return ""

    def get_current_timestamp(self) -> str:
        """Return current transcript timestamp."""
        try:
            return self.content.get_timestamp()
        except Exception as e:
            logger.exception("Error getting current timestamp")
            return ""

    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved edits."""
        return self._has_unsaved_changes

    def copy_current(self) -> None:
        """Copy current transcript to clipboard."""
        try:
            text = self.content.get_text()
            if text:
                copy_text(text)
        except Exception as e:
            logger.exception("Error copying text to clipboard")

    def add_audio_level(self, level: float) -> None:
        """Forward audio level to waveform visualization."""
        try:
            self.content.add_audio_level(level)
        except Exception as e:
            # Don't log every audio level error to avoid spam
            pass

    # Button handlers

    def _on_primary_click(self) -> None:
        """Handle primary button (Start/Stop) click via intent system."""
        try:
            # Phase 3: Route through intent system (handle_intent is authoritative)
            match self._state:
                case WorkspaceState.IDLE | WorkspaceState.VIEWING:
                    intent = BeginRecordingIntent(source=IntentSource.CONTROLS)
                    self.handle_intent(intent)
                case WorkspaceState.RECORDING:
                    intent = StopRecordingIntent(source=IntentSource.CONTROLS)
                    self.handle_intent(intent)
        except Exception as e:
            logger.exception("Error in primary button click")

    def _on_edit_save_click(self) -> None:
        """Handle Edit/Save button click."""
        try:
            match self._state:
                case WorkspaceState.VIEWING:
                    self.set_state(WorkspaceState.EDITING)
                case WorkspaceState.EDITING:
                    edited_text = self.content.get_text()
                    self.content.set_transcript(edited_text, self.content.get_timestamp())
                    self._has_unsaved_changes = False
                    self.saveRequested.emit(edited_text)
                    self.set_state(WorkspaceState.VIEWING)
        except Exception as e:
            logger.exception("Error in edit/save button click")

    def _on_destructive_click(self) -> None:
        """Handle Cancel/Delete button click.
        
        Phase 3: RECORDING state now routes through intent layer.
        EDITING and VIEWING still use legacy path (pending migration).
        """
        try:
            match self._state:
                case WorkspaceState.RECORDING:
                    # Phase 3: Route through intent layer
                    intent = CancelRecordingIntent(source=IntentSource.HOTKEY)
                    self.handle_intent(intent)
                case WorkspaceState.EDITING:
                    self._has_unsaved_changes = False
                    self.set_state(WorkspaceState.VIEWING)
                case WorkspaceState.VIEWING:
                    self.deleteRequested.emit()
        except Exception as e:
            logger.exception("Error in destructive button click")

    def _on_text_changed(self) -> None:
        """Track when text is edited."""
        try:
            if self._state == WorkspaceState.EDITING:
                self._has_unsaved_changes = True
                self.textEdited.emit()
        except Exception as e:
            logger.exception("Error tracking text change")

    # Intent handling (Phase 2: bridge to existing handlers)

    def handle_intent(self, intent: InteractionIntent) -> IntentResult:
        """
        Process an interaction intent and return the outcome.

        Phase 2: This is a compatibility bridge. It logs the intent,
        delegates to existing handlers, and produces an IntentResult.
        No behavior changes; existing signal wiring remains authoritative.

        Args:
            intent: The semantic intent to process

        Returns:
            IntentResult describing what happened
        """
        logger.debug("Intent received: %s", type(intent).__name__)

        result: IntentResult

        match intent:
            # Authoritative apply methods (Phase 3)
            case BeginRecordingIntent():
                result = self._apply_begin_recording(intent)

            case StopRecordingIntent():
                result = self._apply_stop_recording(intent)

            case CancelRecordingIntent():
                result = self._apply_cancel_recording(intent)

            # Bridge methods (pending Phase 3 migration)

            case EditTranscriptIntent():
                result = self._bridge_edit_transcript(intent)

            case CommitEditsIntent(content=text):
                result = self._bridge_commit_edits(intent, text)

            case DiscardEditsIntent():
                result = self._bridge_discard_edits(intent)

            case DeleteTranscriptIntent():
                result = self._bridge_delete_transcript(intent)

            case ViewTranscriptIntent(timestamp=ts):
                result = self._bridge_view_transcript(intent, ts)

            case _:
                result = IntentResult(
                    outcome=IntentOutcome.REJECTED,
                    intent=intent,
                    reason=f"Unknown intent type: {type(intent).__name__}",
                )

        logger.debug("Intent result: %s (%s)", result.outcome.name, result.reason or "")
        self.intentProcessed.emit(result)
        return result

    def _apply_begin_recording(self, intent: BeginRecordingIntent) -> IntentResult:
        """Apply BeginRecordingIntent: transition to RECORDING state.
        
        Phase 3: Authoritative state mutator for BeginRecordingIntent.
        All state mutation for this intent happens here. Bridges route,
        applies mutate.
        
        Precondition: state in (IDLE, VIEWING)
        Postcondition: state == RECORDING, no unsaved changes
        """
        if self._state in (WorkspaceState.IDLE, WorkspaceState.VIEWING):
            # Authoritative mutation
            self.set_state(WorkspaceState.RECORDING)
            self.startRequested.emit()
            
            # Invariant assertions: RECORDING implies clean slate
            assert self._state == WorkspaceState.RECORDING, \
                f"BeginRecordingIntent accepted but state is {self._state.value}"
            assert not self._has_unsaved_changes, \
                "BeginRecordingIntent accepted but has_unsaved_changes is True"
            
            return IntentResult(outcome=IntentOutcome.ACCEPTED, intent=intent)
        else:
            return IntentResult(
                outcome=IntentOutcome.REJECTED,
                intent=intent,
                reason=f"Cannot start recording in {self._state.value} state",
            )

    def _apply_stop_recording(self, intent: StopRecordingIntent) -> IntentResult:
        """Apply StopRecordingIntent: request transcription and show status.
        
        Phase 3: Authoritative state mutator for StopRecordingIntent.
        State remains RECORDING until transcription completes externally.
        Bridges route, applies mutate.
        
        Precondition: state == RECORDING
        Postcondition: transcribing UI visible, stopRequested emitted
        """
        if self._state == WorkspaceState.RECORDING:
            # Authoritative mutation: show transcribing UI and emit signal
            self.show_transcribing_status()
            self.stopRequested.emit()
            
            # Note: State remains RECORDING here. Transition to VIEWING happens
            # when transcription completes via show_transcription().
            
            return IntentResult(outcome=IntentOutcome.ACCEPTED, intent=intent)
        else:
            return IntentResult(
                outcome=IntentOutcome.REJECTED,
                intent=intent,
                reason="Not currently recording",
            )

    def _apply_cancel_recording(self, intent: CancelRecordingIntent) -> IntentResult:
        """Apply CancelRecordingIntent: abort recording and return to IDLE.
        
        Phase 3: Authoritative state mutator for CancelRecordingIntent.
        Bridges route, applies mutate.
        
        Precondition: state == RECORDING
        Postcondition: state == IDLE, cancelRequested emitted
        """
        if self._state == WorkspaceState.RECORDING:
            # Authoritative mutation
            self.cancelRequested.emit()
            self.set_state(WorkspaceState.IDLE)
            
            # Invariant assertions: IDLE implies clean slate
            assert self._state == WorkspaceState.IDLE, \
                f"CancelRecordingIntent accepted but state is {self._state.value}"
            assert not self._has_unsaved_changes, \
                "CancelRecordingIntent accepted but has_unsaved_changes is True"
            
            return IntentResult(outcome=IntentOutcome.ACCEPTED, intent=intent)
        else:
            return IntentResult(
                outcome=IntentOutcome.REJECTED,
                intent=intent,
                reason="Not currently recording",
            )

    def _bridge_edit_transcript(self, intent: EditTranscriptIntent) -> IntentResult:
        """Bridge: delegate to existing edit/save click logic for edit."""
        if self._state == WorkspaceState.VIEWING:
            self._on_edit_save_click()
            return IntentResult(outcome=IntentOutcome.ACCEPTED, intent=intent)
        elif self._state == WorkspaceState.EDITING:
            return IntentResult(
                outcome=IntentOutcome.NO_OP,
                intent=intent,
                reason="Already in edit mode",
            )
        else:
            return IntentResult(
                outcome=IntentOutcome.REJECTED,
                intent=intent,
                reason=f"Cannot edit in {self._state.value} state",
            )

    def _bridge_commit_edits(self, intent: CommitEditsIntent, content: str) -> IntentResult:
        """Bridge: delegate to existing edit/save click logic for save."""
        if self._state == WorkspaceState.EDITING:
            self._on_edit_save_click()
            return IntentResult(outcome=IntentOutcome.ACCEPTED, intent=intent)
        else:
            return IntentResult(
                outcome=IntentOutcome.REJECTED,
                intent=intent,
                reason="Not in edit mode",
            )

    def _bridge_discard_edits(self, intent: DiscardEditsIntent) -> IntentResult:
        """Bridge: delegate to existing destructive click logic for discard."""
        if self._state == WorkspaceState.EDITING:
            self._on_destructive_click()
            return IntentResult(outcome=IntentOutcome.ACCEPTED, intent=intent)
        else:
            return IntentResult(
                outcome=IntentOutcome.NO_OP,
                intent=intent,
                reason="Not in edit mode",
            )

    def _bridge_delete_transcript(self, intent: DeleteTranscriptIntent) -> IntentResult:
        """Bridge: delegate to existing destructive click logic for delete."""
        if self._state == WorkspaceState.VIEWING:
            self._on_destructive_click()
            return IntentResult(outcome=IntentOutcome.ACCEPTED, intent=intent)
        else:
            return IntentResult(
                outcome=IntentOutcome.REJECTED,
                intent=intent,
                reason=f"Cannot delete in {self._state.value} state",
            )

    def _bridge_view_transcript(self, intent: ViewTranscriptIntent, timestamp: str) -> IntentResult:
        """Bridge: delegate to load_transcript for viewing."""
        # Phase 2: This does NOT validate conflicts (recording, editing).
        # Validation will be added in Phase 4. For now, just log and accept.
        if self._state == WorkspaceState.RECORDING:
            return IntentResult(
                outcome=IntentOutcome.REJECTED,
                intent=intent,
                reason="Cannot view transcript while recording",
            )
        if self._state == WorkspaceState.EDITING and self._has_unsaved_changes:
            return IntentResult(
                outcome=IntentOutcome.REJECTED,
                intent=intent,
                reason="Unsaved changes exist",
            )
        # Accept but do NOT call load_transcript here (that remains in MainWindow).
        # Phase 2 bridge only validates; actual load happens via existing wiring.
        return IntentResult(outcome=IntentOutcome.ACCEPTED, intent=intent)

    # Resize handling

    def resizeEvent(self, event) -> None:
        """Handle resize for responsive typography."""
        try:
            super().resizeEvent(event)
            width = event.size().width()
            self.header.scale_font(width)
        except Exception as e:
            logger.exception("Error in resize event")
