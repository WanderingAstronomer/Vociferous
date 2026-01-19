"""
MainWorkspace - State-driven main workspace canvas.

States:
- IDLE: Welcome greeting
- RECORDING: Active recording state
- VIEWING: Transcript display
- EDITING: Editable transcript
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.ui.components.workspace.content import WorkspaceContent
from src.ui.components.workspace.footer import BatchStatusFooter
from src.ui.components.workspace.header import WorkspaceHeader
from src.ui.constants import Spacing, WorkspaceState
from src.ui.widgets.workspace_panel import WorkspacePanel
from src.ui.interaction import (
    BeginRecordingIntent,
    CancelRecordingIntent,
    CommitEditsIntent,
    DeleteTranscriptIntent,
    DiscardEditsIntent,
    EditTranscriptIntent,
    IntentOutcome,
    IntentResult,
    IntentSource,
    InteractionIntent,
    StopRecordingIntent,
    ViewTranscriptIntent,
)
from src.ui.utils.clipboard_utils import copy_text

if TYPE_CHECKING:
    from src.database.history_manager import HistoryEntry

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

    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    cancel_requested = pyqtSignal()
    save_requested = pyqtSignal(str)
    delete_requested = pyqtSignal()
    refine_requested = pyqtSignal(str, str, str)  # Passes (profile, text, timestamp)
    edit_requested = pyqtSignal(str)  # Passes timestamp
    text_edited = pyqtSignal()
    state_changed = pyqtSignal(WorkspaceState)

    # Intent processing signal (Phase 2: observability only)
    intent_processed = pyqtSignal(object)  # IntentResult

    # New signal for MOTD refresh
    motd_refresh_requested = pyqtSignal()

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
        self.header.request_motd_refresh.connect(self.motd_refresh_requested.emit)
        layout.addWidget(self.header, 0)
        layout.addSpacing(Spacing.HEADER_CONTROLS_GAP)

        # Metrics display (above content panel, hidden by default)
        from src.ui.components.workspace.transcript_metrics import TranscriptMetrics

        self.metrics = TranscriptMetrics()
        self.metrics.hide()
        layout.addWidget(self.metrics, 0)
        layout.addSpacing(Spacing.MINOR_GAP)

        # Content panel (visual container) - EXPANDS TO FILL ALL REMAINING SPACE
        self._setup_content_panel(layout)

        # Batch status footer (appears at the very bottom)
        self.batch_footer = BatchStatusFooter()
        layout.addWidget(self.batch_footer, 0)

        outer_layout.addWidget(self.content_column, 1)

    def _setup_content_panel(self, parent_layout: QVBoxLayout) -> None:
        """Create visual content panel container."""
        self.content_panel = WorkspacePanel()
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

        # Content component
        self.content = WorkspaceContent()
        panel_layout.addWidget(self.content)

        parent_layout.addWidget(
            self.content_panel, 1
        )  # Stretch=1: claim all vertical space

    def _connect_signals(self) -> None:
        """Wire up component signals to workspace handlers."""
        self.content.text_changed.connect(self._on_text_changed)
        self.content.edit_requested.connect(self._on_edit_save_click)
        self.content.delete_requested.connect(self._on_destructive_click)

    def _handle_refine_request(self, profile: str) -> None:
        """Collect transcript data and emit refinement request."""
        text = self.content.get_text()
        timestamp = self.content.get_timestamp()
        if text and timestamp:
            self.refine_requested.emit(profile, text, timestamp)

    def on_refinement_completed(
        self, text: str, timestamp: str, variants: list
    ) -> None:
        """Handle completion of external refinement.

        Updates the view only if we are still looking at the same transcript.
        """
        current_ts = self.content.get_timestamp()
        if current_ts == timestamp:
            self.load_transcript(text, timestamp)
            self.content.set_variants(variants)

    def _update_for_state(self) -> None:
        """Update all components for current state."""
        is_editing = self._state == WorkspaceState.EDITING
        is_recording = self._state == WorkspaceState.RECORDING
        is_transcribing = self._state == WorkspaceState.TRANSCRIBING

        self.content_panel.setProperty("editing", is_editing)
        self.content_panel.setProperty("recording", is_recording or is_transcribing)
        self.content_panel.style().unpolish(self.content_panel)
        self.content_panel.style().polish(self.content_panel)
        self.content_panel.update()

        match self._state:
            case WorkspaceState.IDLE:
                self.header.set_state(self._state)
                self.header.update_for_idle()
                # self.controls.update_for_idle() - DEPRECATED
                self.content.update_for_idle()
                self.metrics.hide()

            case WorkspaceState.RECORDING:
                self.header.set_state(self._state)
                self.header.update_for_recording()
                # self.controls.update_for_recording() - DEPRECATED
                self.content.update_for_recording()
                self.metrics.hide()

            case WorkspaceState.TRANSCRIBING:
                self.header.set_state(self._state)
                self.header.update_for_transcribing()
                self.content.update_for_transcribing()
                self.metrics.hide()

            case WorkspaceState.VIEWING:
                self.header.set_state(self._state)
                self.header.update_for_viewing()
                # self.controls.update_for_viewing() - DEPRECATED
                self.content.update_for_viewing()
                # Metrics visibility is handled in load_transcript/display_new_transcript

            case WorkspaceState.READY:
                self.header.set_state(self._state)
                self.header.update_for_ready()
                self.content.update_for_viewing()
                # Metrics should be visible for ready state

            case WorkspaceState.EDITING:
                self.header.set_state(self._state)
                self.header.update_for_editing()
                # self.controls.update_for_editing() - DEPRECATED
                self.content.update_for_editing()
                # Metrics visibility preserved from VIEWING state

    # Public API

    def get_transcript_scroll_area(self) -> WorkspacePanel:
        """Public accessor for the transcript scroll area."""
        return self.content_panel

    def set_history_manager(self, manager) -> None:
        """Set history manager for fetching transcript metadata."""
        self._history_manager = manager

    def set_audio_level(self, level: float) -> None:
        """Update waveform audio level."""
        self.content.set_audio_level(level)

    def set_live_text(self, text: str) -> None:
        """Update live transcription text."""
        self.content.set_live_text(text)

    def set_state(self, state: WorkspaceState) -> None:
        """Change workspace state."""
        try:
            if self._state == state:
                return

            self._state = state
            self._update_for_state()
            self.state_changed.emit(state)
        except Exception:
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
        except Exception:
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
                self.metrics.set_metrics(
                    entry.duration_ms, entry.speech_duration_ms, word_count
                )
                self.metrics.show()
            else:
                self.metrics.hide()

            self.set_state(WorkspaceState.READY)
        except Exception:
            logger.exception("Error displaying new transcript")
            raise

    def show_transcribing_status(self) -> None:
        """Show transcribing indicator (after recording stops)."""
        try:
            self.header.update_for_transcribing()
        except Exception:
            logger.exception("Error showing transcribing status")

    def get_current_text(self) -> str:
        """Return current transcript text."""
        try:
            return self.content.get_text()
        except Exception:
            logger.exception("Error getting current text")
            return ""

    def get_current_timestamp(self) -> str:
        """Return current transcript timestamp."""
        try:
            return self.content.get_timestamp()
        except Exception:
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
        except Exception:
            logger.exception("Error copying text to clipboard")

    def add_audio_level(self, level: float) -> None:
        """Forward audio level to visualizer."""
        try:
            self.content.add_audio_level(level)
        except Exception:
            # Don't log every audio level error to avoid spam
            pass

    def add_audio_spectrum(self, bands: list[float]) -> None:
        """Forward FFT spectrum to visualizer."""
        try:
            self.content.set_audio_spectrum(bands)
        except Exception:
            pass

    # Button handlers

    def _on_primary_click(self) -> None:
        """Handle primary button (Start/Stop) click via intent system."""
        try:
            # Phase 3: Route through intent system (handle_intent is authoritative)
            match self._state:
                case WorkspaceState.IDLE | WorkspaceState.VIEWING:
                    self.handle_intent(
                        BeginRecordingIntent(source=IntentSource.CONTROLS)
                    )
                case WorkspaceState.RECORDING:
                    self.handle_intent(
                        StopRecordingIntent(source=IntentSource.CONTROLS)
                    )
        except Exception:
            logger.exception("Error in primary button click")

    def _on_edit_save_click(self) -> None:
        """Handle Edit/Save button click.

        Phase 4: VIEWING state now routes through intent layer for edit.
        EDITING state still uses legacy path for save (pending migration).
        """
        try:
            match self._state:
                case WorkspaceState.VIEWING:
                    # Phase 4: Route through intent layer
                    timestamp = self.get_current_timestamp()
                    transcript_id = 0
                    if self._history_manager and timestamp:
                        # Resolve ID securely
                        res = self._history_manager.get_id_by_timestamp(timestamp)
                        if res is not None:
                            transcript_id = res

                    self.handle_intent(
                        EditTranscriptIntent(
                            source=IntentSource.CONTROLS,
                            transcript_id=str(transcript_id),
                        )
                    )
                case WorkspaceState.EDITING:
                    # Phase 4: Route through intent layer
                    edited_text = self.content.get_text()
                    self.handle_intent(
                        CommitEditsIntent(
                            source=IntentSource.CONTROLS,
                            content=edited_text,
                        )
                    )
        except Exception:
            logger.exception("Error in edit/save button click")

    def _on_destructive_click(self) -> None:
        """Handle Cancel/Delete button click.

        Phase 5: All cases now route through intent layer.
        """
        try:
            match self._state:
                case WorkspaceState.RECORDING:
                    # Phase 3: Route through intent layer
                    self.handle_intent(
                        CancelRecordingIntent(source=IntentSource.HOTKEY)
                    )
                case WorkspaceState.EDITING:
                    # Phase 4: Route through intent layer
                    self.handle_intent(DiscardEditsIntent(source=IntentSource.CONTROLS))
                case WorkspaceState.VIEWING:
                    # Phase 5: Route through intent layer
                    self.handle_intent(
                        DeleteTranscriptIntent(source=IntentSource.CONTROLS)
                    )
        except Exception:
            logger.exception("Error in destructive button click")

    def _on_text_changed(self) -> None:
        """Track when text is edited."""
        try:
            if self._state == WorkspaceState.EDITING:
                self._has_unsaved_changes = True
                self.text_edited.emit()
        except Exception:
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

            case EditTranscriptIntent():
                result = self._apply_edit_transcript(intent)

            case CommitEditsIntent(content=text):
                result = self._apply_commit_edits(intent, text)

            case DiscardEditsIntent():
                result = self._apply_discard_edits(intent)

            # Authoritative apply methods

            case DeleteTranscriptIntent():
                result = self._apply_delete_transcript(intent)

            case ViewTranscriptIntent(timestamp=ts, text=txt):
                result = self._apply_view_transcript(intent, ts, txt)

            case _:
                result = IntentResult(
                    outcome=IntentOutcome.REJECTED,
                    intent=intent,
                    reason=f"Unknown intent type: {type(intent).__name__}",
                )

        logger.debug("Intent result: %s (%s)", result.outcome.name, result.reason or "")
        self.intent_processed.emit(result)
        return result

    def _apply_begin_recording(self, intent: BeginRecordingIntent) -> IntentResult:
        """Apply BeginRecordingIntent: transition to RECORDING state.

        Phase 3: Authoritative state mutator for BeginRecordingIntent.
        All state mutation for this intent happens here. Bridges route,
        applies mutate.

        Precondition: state in (IDLE, VIEWING, READY)
        Postcondition: state == RECORDING, no unsaved changes
        """
        if self._state in (
            WorkspaceState.IDLE,
            WorkspaceState.VIEWING,
            WorkspaceState.READY,
        ):
            # Clear residual content from READY state before new recording
            if self._state == WorkspaceState.READY:
                self.content.set_transcript("", "")
                self.header.set_timestamp("")
                self.metrics.hide()
                self._has_unsaved_changes = False

            # Authoritative mutation
            self.set_state(WorkspaceState.RECORDING)
            self.start_requested.emit()

            # Invariant checks: RECORDING implies clean slate
            if self._state != WorkspaceState.RECORDING:
                message = (
                    f"BeginRecordingIntent accepted but state is {self._state.value}"
                )
                logger.error(message)
                raise RuntimeError(message)
            if self._has_unsaved_changes:
                message = (
                    "BeginRecordingIntent accepted but has_unsaved_changes is True"
                )
                logger.error(message)
                raise RuntimeError(message)

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
        State transitions to TRANSCRIBING until completion signals arrive.
        Bridges route, applies mutate.

        Precondition: state == RECORDING
        Postcondition: state == TRANSCRIBING, stop_requested emitted
        """
        if self._state == WorkspaceState.RECORDING:
            # Authoritative mutation: transition to TRANSCRIBING and emit signal
            self.set_state(WorkspaceState.TRANSCRIBING)
            self.stop_requested.emit()

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
        Postcondition: state == IDLE, cancel_requested emitted
        """
        if self._state == WorkspaceState.RECORDING:
            # Authoritative mutation
            self.cancel_requested.emit()
            self.set_state(WorkspaceState.IDLE)

            # Invariant assertions: IDLE implies clean slate
            assert self._state == WorkspaceState.IDLE, (
                f"CancelRecordingIntent accepted but state is {self._state.value}"
            )
            assert not self._has_unsaved_changes, (
                "CancelRecordingIntent accepted but has_unsaved_changes is True"
            )

            return IntentResult(outcome=IntentOutcome.ACCEPTED, intent=intent)
        else:
            return IntentResult(
                outcome=IntentOutcome.REJECTED,
                intent=intent,
                reason="Not currently recording",
            )

    def _apply_edit_transcript(self, intent: EditTranscriptIntent) -> IntentResult:
        """Apply EditTranscriptIntent: request editing for current transcript.

        Phase 4: Authoritative handler for EditTranscriptIntent.

        CHANGED: Now delegates to external edit view via signal instead of
        entering in-place editing mode. This ensures architectural consistency.

        Precondition: state in (VIEWING, READY), current transcript loaded
        Postcondition: edit_requested emitted
        """
        if self._state in (WorkspaceState.VIEWING, WorkspaceState.READY):
            # Invariant 1: Must have a transcript loaded to edit
            current_ts = self.get_current_timestamp()
            if not current_ts:
                return IntentResult(
                    outcome=IntentOutcome.REJECTED,
                    intent=intent,
                    reason="No transcript loaded to edit",
                )

            # Authoritative delegation: emit signal for external routing
            self.edit_requested.emit(current_ts)

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

    def _apply_commit_edits(
        self, intent: CommitEditsIntent, content: str
    ) -> IntentResult:
        """Apply CommitEditsIntent: save edited content and exit editing mode.

        Phase 4: Authoritative state mutator for CommitEditsIntent.
        This is a terminal intent for editing sessions.
        Bridges route, applies mutate.

        Precondition: state == EDITING
        Postcondition: state == VIEWING, _has_unsaved_changes == False

        Invariant 4: Editing can only exit through terminal intents.
        """
        if self._state == WorkspaceState.EDITING:
            # Authoritative mutation: persist edits and transition to VIEWING
            self.content.set_transcript(content, self.content.get_timestamp())
            self._has_unsaved_changes = False
            self.save_requested.emit(content)
            self.set_state(WorkspaceState.VIEWING)

            # Postcondition assertions
            assert self._state == WorkspaceState.VIEWING, (
                f"CommitEditsIntent accepted but state is {self._state.value}"
            )
            assert not self._has_unsaved_changes, (
                "CommitEditsIntent: unsaved changes should be False after commit"
            )

            return IntentResult(outcome=IntentOutcome.ACCEPTED, intent=intent)
        else:
            return IntentResult(
                outcome=IntentOutcome.REJECTED,
                intent=intent,
                reason="Not in edit mode",
            )

    def _apply_discard_edits(self, intent: DiscardEditsIntent) -> IntentResult:
        """Apply DiscardEditsIntent: abandon edits and exit editing mode.

        Phase 4: Authoritative state mutator for DiscardEditsIntent.
        This is a terminal intent for editing sessions.
        Bridges route, applies mutate.

        Precondition: state == EDITING
        Postcondition: state == VIEWING, _has_unsaved_changes == False

        Invariant 4: Editing can only exit through terminal intents.
        """
        if self._state == WorkspaceState.EDITING:
            # Authoritative mutation: discard edits and transition to VIEWING
            self._has_unsaved_changes = False
            self.set_state(WorkspaceState.VIEWING)

            # Postcondition assertions
            assert self._state == WorkspaceState.VIEWING, (
                f"DiscardEditsIntent accepted but state is {self._state.value}"
            )
            assert not self._has_unsaved_changes, (
                "DiscardEditsIntent: unsaved changes should be False after discard"
            )

            return IntentResult(outcome=IntentOutcome.ACCEPTED, intent=intent)
        else:
            return IntentResult(
                outcome=IntentOutcome.NO_OP,
                intent=intent,
                reason="Not in edit mode",
            )

    def _apply_delete_transcript(self, intent: DeleteTranscriptIntent) -> IntentResult:
        """Apply DeleteTranscriptIntent: request deletion of current transcript.

        Phase 5: Authoritative validator for DeleteTranscriptIntent.

        Precondition: state == VIEWING (must have a transcript to delete)
        Postcondition: deleteRequested emitted

        Note: This does NOT change state. Actual deletion and state transition
        happen when MainWindow confirms and calls clear_transcript().
        The confirmation dialog is a UX concern owned by MainWindow.
        """
        # Precondition: can only delete while viewing or just finished
        if self._state not in (WorkspaceState.VIEWING, WorkspaceState.READY):
            return IntentResult(
                outcome=IntentOutcome.REJECTED,
                intent=intent,
                reason=f"Cannot delete in {self._state.value} state",
            )

        # Precondition: must have a transcript selected
        timestamp = self.get_current_timestamp()
        if not timestamp:
            return IntentResult(
                outcome=IntentOutcome.REJECTED,
                intent=intent,
                reason="No transcript selected",
            )

        # Emit signal for MainWindow to handle (shows confirmation, performs I/O)
        self.delete_requested.emit()

        # State change happens in clear_transcript() after confirmation
        return IntentResult(outcome=IntentOutcome.ACCEPTED, intent=intent)

    def clear_transcript(self) -> None:
        """Clear the current transcript and transition to IDLE.

        Called by MainWindow after delete confirmation and I/O completion.
        This is the terminal state mutation for delete operations.
        """
        self.set_state(WorkspaceState.IDLE)
        self._has_unsaved_changes = False
        self.content.set_transcript("", "")
        self.header.set_timestamp("")
        self.metrics.hide()

    def _apply_view_transcript(
        self, intent: ViewTranscriptIntent, timestamp: str, text: str
    ) -> IntentResult:
        """Apply ViewTranscriptIntent: display a transcript for viewing.

        Phase 5: Authoritative state mutator for ViewTranscriptIntent.

        Precondition: state != RECORDING
        Precondition: if EDITING with unsaved changes, reject (Invariant 3)
        Postcondition: state == VIEWING if text non-empty, else IDLE
        Postcondition: _has_unsaved_changes == False
        """
        # Idempotent check: already viewing this transcript
        if (
            self._state == WorkspaceState.VIEWING
            and timestamp == self.get_current_timestamp()
        ):
            return IntentResult(
                outcome=IntentOutcome.NO_OP,
                intent=intent,
                reason="Already viewing this transcript",
            )

        # Precondition: cannot view while recording
        if self._state == WorkspaceState.RECORDING:
            return IntentResult(
                outcome=IntentOutcome.REJECTED,
                intent=intent,
                reason="Cannot view transcript while recording",
            )

        # Precondition: cannot switch view with unsaved edits (Invariant 3)
        if self._state == WorkspaceState.EDITING and self._has_unsaved_changes:
            return IntentResult(
                outcome=IntentOutcome.REJECTED,
                intent=intent,
                reason="Unsaved changes exist",
            )

        # Precondition: must have valid timestamp
        if not timestamp:
            return IntentResult(
                outcome=IntentOutcome.REJECTED,
                intent=intent,
                reason="No timestamp provided",
            )

        # Authoritative mutation: load transcript
        # Inline the load_transcript logic for authority over state
        try:
            # Fetch duration metadata from history manager if available
            duration_ms = None
            speech_duration_ms = None
            if self._history_manager:
                entry = self._history_manager.get_entry_by_timestamp(timestamp)
                if entry:
                    duration_ms = entry.duration_ms
                    speech_duration_ms = entry.speech_duration_ms

            self.content.set_transcript(text, timestamp)

            # Pass variants to content for carousel (Phase 6)
            if hasattr(intent, "variants"):
                self.content.set_variants(intent.variants)
            else:
                self.content.set_variants([])

            self.header.set_timestamp(timestamp)
            self._has_unsaved_changes = False

            # Update metrics if we have duration data
            if text and duration_ms is not None:
                word_count = len(text.split())
                self.metrics.set_metrics(duration_ms, speech_duration_ms, word_count)
                self.metrics.show()
            else:
                self.metrics.hide()

            # Set state based on content
            if text:
                self.set_state(WorkspaceState.VIEWING)
            else:
                self.set_state(WorkspaceState.IDLE)

            # Postcondition assertions
            expected_state = WorkspaceState.VIEWING if text else WorkspaceState.IDLE
            assert self._state == expected_state, (
                f"ViewTranscriptIntent: expected {expected_state.value}, got {self._state.value}"
            )
            assert not self._has_unsaved_changes, (
                "ViewTranscriptIntent: _has_unsaved_changes should be False"
            )

            return IntentResult(outcome=IntentOutcome.ACCEPTED, intent=intent)

        except Exception as e:
            logger.exception("Error in _apply_view_transcript")
            return IntentResult(
                outcome=IntentOutcome.REJECTED,
                intent=intent,
                reason=f"Load failed: {e}",
            )

    # Resize handling

    def resizeEvent(self, event) -> None:
        """Handle resize for responsive typography."""
        try:
            super().resizeEvent(event)
            width = event.size().width()
            self.header.scale_font(width)
        except Exception:
            logger.exception("Error in resize event")
