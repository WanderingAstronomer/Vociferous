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

from src.ui.components.workspace.workspace import MainWorkspace
from src.ui.constants import WorkspaceState
from src.ui.constants.view_ids import VIEW_TRANSCRIBE
from src.ui.contracts.capabilities import ActionId, Capabilities
from src.ui.interaction.intents import (
    BeginRecordingIntent,
    StopRecordingIntent,
    IntentSource,
)
from src.ui.interaction import (
    EditTranscriptIntent,
    DeleteTranscriptIntent,
    DiscardEditsIntent,
    CancelRecordingIntent,
    CommitEditsIntent,
)
from src.ui.views.base_view import BaseView

if TYPE_CHECKING:
    from src.database.history_manager import HistoryManager
    from src.database.dtos import HistoryEntry


class TranscribeView(BaseView):
    """
    View for live recording and transcript interaction.

    Acts as a thin host for MainWorkspace, delegating active surface duties.
    """

    # Signal to maintain contract with MainWindow's expectation
    # (id, text)
    edit_normalized_text = pyqtSignal(int, str)

    # Routing signals
    edit_requested = pyqtSignal(int)
    delete_requested = pyqtSignal()
    refine_requested = pyqtSignal(int)

    # Needs explicit signal for refresh
    motd_refresh_requested = pyqtSignal()

    def __init__(
        self,
        history_manager: Optional[HistoryManager] = None,
        parent: QWidget | None = None,
    ) -> None:
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
        self.workspace.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        if self.history_manager:
            self.workspace.set_history_manager(self.history_manager)

        layout.addWidget(self.workspace)

    def _connect_signals(self) -> None:
        """Wire workspace signals to view signals."""
        # Forward save requests
        self.workspace.save_requested.connect(self._handle_save_requested)

        # Propagate state changes to capabilities
        self.workspace.state_changed.connect(lambda _: self.capabilities_changed.emit())

        # Propagate content changes to capabilities
        # This ensures ActionGrid refreshes when text is typed or modified
        self.workspace.content.text_changed.connect(
            lambda: self.capabilities_changed.emit()
        )

        # Routing connections
        self.workspace.edit_requested.connect(self._handle_workspace_edit_requested)
        self.workspace.delete_requested.connect(self.delete_requested.emit)
        self.workspace.motd_refresh_requested.connect(self.motd_refresh_requested.emit)
        self.workspace.refine_requested.connect(self._handle_workspace_refine_requested)

    def set_motd(self, text: str) -> None:
        """Update the MOTD in the workspace header."""
        self.workspace.header.set_motd(text)

        # Note: start/stop/cancel signals from workspace are typically
        # connected directly by the Orchestrator (MainWindow), or via Intents.
        # We handle 'editNormalizedText' specifically because the wrapper expects it.

    def _handle_workspace_edit_requested(self, timestamp: str) -> None:
        """Resolve timestamp to ID and route to edit view."""
        if self.history_manager and timestamp:
            tid = self.history_manager.get_id_by_timestamp(timestamp)
            if tid is not None:
                self.edit_requested.emit(tid)

    def _handle_workspace_refine_requested(
        self, profile: str, text: str, timestamp: str
    ) -> None:
        """Resolve timestamp to ID and route to refine view."""
        if self.history_manager and timestamp:
            tid = self.history_manager.get_id_by_timestamp(timestamp)
            if tid is not None:
                self.refine_requested.emit(tid)

    def _handle_save_requested(self, text: str) -> None:
        """Adapt workspace save signal to view contract."""
        timestamp = self.workspace.content.get_timestamp()
        if self.history_manager and timestamp:
            entry_id = self.history_manager.get_id_by_timestamp(timestamp)
            if entry_id is not None:
                self.edit_normalized_text.emit(entry_id, text)

    # BaseView Implementation

    def get_view_id(self) -> str:
        return VIEW_TRANSCRIBE

    def get_capabilities(self) -> Capabilities:
        """
        Delegate capabilities determination to workspace state.
        For now, returns a reasonable default, or relies on WorkspaceControls availability.
        """
        from src.core.config_manager import ConfigManager

        # Simplification: The workspace controls its own buttons.
        # This contract might be for global menus/actions.
        state = self.workspace.get_state()
        # Even if text remains in the content buffer, IDLE state implies "no active transcript"
        # and should hide transcript-bound actions (Copy, Edit, Delete).
        has_text = (
            bool(self.workspace.content.get_text()) and state != WorkspaceState.IDLE
        )
        is_recording = state == WorkspaceState.RECORDING
        is_transcribing = state == WorkspaceState.TRANSCRIBING
        is_editing = state == WorkspaceState.EDITING
        refinement_enabled = ConfigManager.get_config_value("refinement", "enabled")

        return Capabilities(
            can_copy=has_text and not is_recording and not is_transcribing,
            can_edit=has_text
            and not is_recording
            and not is_transcribing
            and not is_editing,
            can_delete=has_text
            and not is_recording
            and not is_transcribing
            and not is_editing,
            can_refine=has_text
            and not is_recording
            and not is_transcribing
            and not is_editing
            and refinement_enabled,  # Refine available when enabled and in VIEWING/READY states
            can_move_to_project=False,
            can_preview=False,
            can_export=False,
            can_save=is_editing,
            can_discard=is_editing,  # Only show discard when editing
            can_cancel=is_recording,
            can_start_recording=not is_recording
            and not is_transcribing
            and not is_editing,
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
            # Consuming action: reset READY to IDLE
            if self.workspace.get_state() == WorkspaceState.READY:
                self.workspace.set_state(WorkspaceState.IDLE)
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
                            source=IntentSource.CONTROLS, transcript_id=str(tid)
                        )
                    )
        elif action_id == ActionId.SAVE:
            text = self.workspace.get_current_text()
            self.workspace.handle_intent(
                CommitEditsIntent(source=IntentSource.CONTROLS, content=text)
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
                self.workspace.refine_requested.emit("default", text, timestamp)

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
            else:
                self.workspace.set_state(WorkspaceState.READY)

    def hideEvent(self, event) -> None:
        """Reset state when navigating away."""
        super().hideEvent(event)
        current_state = self.workspace.get_state()
        if current_state in (
            WorkspaceState.READY,
            WorkspaceState.EDITING,
            WorkspaceState.VIEWING,
        ):
            self.workspace.set_state(WorkspaceState.IDLE)

    @pyqtSlot()
    def pause_visualization(self) -> None:
        """Pause the visualizer (e.g. during transcription) without changing state."""
        # We can hijack the workspace content directly if needed, or use a new method on workspace
        if hasattr(self.workspace, "content") and hasattr(
            self.workspace.content, "visualizer"
        ):
            visualizer = self.workspace.content.visualizer
            if hasattr(visualizer, "pause"):
                visualizer.pause()
            else:
                visualizer.stop()

    @pyqtSlot(str)
    def set_live_text(self, text: str) -> None:
        """Update the live text display."""
        self.workspace.set_live_text(text)

    @pyqtSlot(float)
    def set_audio_level(self, level: float) -> None:
        """Push audio level to visualizer."""
        self.workspace.add_audio_level(level)

    @pyqtSlot(list)
    def set_audio_spectrum(self, bands: list[float]) -> None:
        """Push FFT bands to visualizer."""
        self.workspace.add_audio_spectrum(bands)

    def load_transcript(self, text: str, timestamp: str) -> None:
        """Load a transcript for viewing/editing."""
        self.workspace.load_transcript(text, timestamp)

    def display_new_transcript(self, entry: HistoryEntry) -> None:
        """Display a newly created transcript with full metrics."""
        self.workspace.display_new_transcript(entry)
