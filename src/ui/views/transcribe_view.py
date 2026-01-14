"""
TranscribeView - Dedicated view for active recording session.

Hosts the MainWorkspace (canonical surface owner) to provide:
- Recording controls and visualization
- Transcript viewing and editing
- State management for the primary workflow
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import pyqtSlot, pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QSizePolicy

from ui.components.workspace.workspace import MainWorkspace
from ui.constants import WorkspaceState
from ui.constants.view_ids import VIEW_TRANSCRIBE
from ui.contracts.capabilities import ActionId, Capabilities
from ui.interaction.intents import BeginRecordingIntent, StopRecordingIntent, IntentSource
from ui.interaction import (
    EditTranscriptIntent, DeleteTranscriptIntent,
    DiscardEditsIntent, CancelRecordingIntent,
    CommitEditsIntent
)
from ui.views.base_view import BaseView

if TYPE_CHECKING:
    from history_manager import HistoryManager


class TranscribeView(BaseView):
    """
    View for live recording and transcript interaction.
    
    Acts as a thin host for MainWorkspace, delegating active surface duties.
    """

    # Signal to maintain contract with MainWindow's expectation
    # (id, text)
    editNormalizedText = pyqtSignal(int, str)

    def __init__(self, history_manager: Optional[HistoryManager] = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.history_manager = history_manager
        
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Initialize the view layout with MainWorkspace."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.workspace = MainWorkspace()
        # Ensure workspace expands
        self.workspace.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        if self.history_manager:
            self.workspace.set_history_manager(self.history_manager)
            
        layout.addWidget(self.workspace)

    def _connect_signals(self) -> None:
        """Wire workspace signals to view signals."""
        # Forward save requests
        self.workspace.saveRequested.connect(self._handle_save_requested)
        
        # Propagate state changes to capabilities
        self.workspace.stateChanged.connect(lambda _: self.capabilitiesChanged.emit())

        # Propagate content changes to capabilities
        # This ensures ActionGrid refreshes when text is typed or modified
        self.workspace.content.textChanged.connect(lambda: self.capabilitiesChanged.emit())

        # Note: start/stop/cancel signals from workspace are typically 
        # connected directly by the Orchestrator (MainWindow), or via Intents.
        # We handle 'editNormalizedText' specifically because the wrapper expects it.

    def _handle_save_requested(self, text: str) -> None:
        """Adapt workspace save signal to view contract."""
        timestamp = self.workspace.content.get_timestamp()
        if self.history_manager and timestamp:
            entry_id = self.history_manager.get_id_by_timestamp(timestamp)
            if entry_id is not None:
                self.editNormalizedText.emit(entry_id, text)

    # BaseView Implementation
    
    def get_view_id(self) -> str:
        return VIEW_TRANSCRIBE

    def get_capabilities(self) -> Capabilities:
        """
        Delegate capabilities determination to workspace state.
        For now, returns a reasonable default, or relies on WorkspaceControls availability.
        """
        # Simplification: The workspace controls its own buttons. 
        # This contract might be for global menus/actions.
        state = self.workspace.get_state()
        has_text = bool(self.workspace.content.get_text())
        is_recording = state == WorkspaceState.RECORDING
        is_editing = state == WorkspaceState.EDITING
        
        return Capabilities(
            can_copy=has_text,
            can_edit=has_text and not is_recording and not is_editing,
            can_delete=has_text and not is_recording and not is_editing,
            can_refine=has_text and not is_recording and not is_editing,  # Refine available in VIEWING state
            can_move_to_project=False,
            can_preview=False,
            can_export=False,
            can_save=is_editing,
            can_discard=is_editing or is_recording,
            can_start_recording=not is_recording and not is_editing,
            can_stop_recording=is_recording,
        )
    
    def dispatch_action(self, action_id: ActionId) -> None:
        """Dispatch external actions to the workspace."""
        if action_id == ActionId.START_RECORDING:
            self.workspace.handle_intent(
                BeginRecordingIntent(source=IntentSource.CONTROLS)
            )
        elif action_id == ActionId.STOP_RECORDING:
            self.workspace.handle_intent(
                StopRecordingIntent(source=IntentSource.CONTROLS)
            )
        elif action_id == ActionId.COPY:
            self.workspace.copy_current()
        elif action_id == ActionId.DELETE:
            self.workspace.handle_intent(
                DeleteTranscriptIntent(source=IntentSource.CONTROLS)
            )
        elif action_id == ActionId.EDIT:
            timestamp = self.workspace.get_current_timestamp()
            if self.history_manager and timestamp:
                tid = self.history_manager.get_id_by_timestamp(timestamp)
                if tid is not None:
                    self.workspace.handle_intent(
                        EditTranscriptIntent(
                            source=IntentSource.CONTROLS,
                            transcript_id=str(tid)
                        )
                    )
        elif action_id == ActionId.SAVE:
            text = self.workspace.get_current_text()
            self.workspace.handle_intent(
                CommitEditsIntent(
                    source=IntentSource.CONTROLS,
                    content=text
                )
            )
        elif action_id == ActionId.DISCARD:
            self.workspace.handle_intent(
                DiscardEditsIntent(source=IntentSource.CONTROLS)
            )
        elif action_id == ActionId.CANCEL:
            self.workspace.handle_intent(
                CancelRecordingIntent(source=IntentSource.CONTROLS)
            )
        elif action_id == ActionId.REFINE:
            text = self.workspace.get_current_text()
            timestamp = self.workspace.get_current_timestamp()
            if text and timestamp:
                # Fallback to existing signal until RefineIntent exists
                self.workspace.refineRequested.emit("default", text, timestamp)

    # Public Slots for Controller / Orchestrator

    @pyqtSlot(bool)
    def update_for_recording_state(self, is_recording: bool) -> None:
        """Start or stop the visualization."""
        if is_recording:
            self.workspace.set_state(WorkspaceState.RECORDING)
        else:
            # Transition to IDLE if no text
            if not self.workspace.content.get_text():
                self.workspace.set_state(WorkspaceState.IDLE)
    
    @pyqtSlot(str)
    def set_live_text(self, text: str) -> None:
        """Update the live text display."""
        self.workspace.set_live_text(text)

    @pyqtSlot(float)
    def set_audio_level(self, level: float) -> None:
        """Push audio level to visualizer."""
        self.workspace.set_audio_level(level)
        
    def load_transcript(self, text: str, timestamp: str) -> None:
        """Load a transcript for viewing/editing."""
        self.workspace.load_transcript(text, timestamp)
