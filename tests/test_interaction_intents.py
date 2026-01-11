"""
Tests for interaction intent vocabulary (Phase 2).

These tests verify:
- Intent construction and immutability
- IntentResult construction
- handle_intent() passthrough (no state assertions)

Per Phase 2 guidance: tests assert construction and passthrough only.
State transition assertions belong to Phase 3+.

Test Tier: UI-Independent (Tier 1)
- Pure intent/result logic, minimal Qt widget usage
- Uses lightweight QApplication from conftest.py
- Run with: pytest -m "not ui_dependent"
"""

import pytest
from dataclasses import FrozenInstanceError

from ui.interaction import (
    InteractionIntent,
    BeginRecordingIntent,
    StopRecordingIntent,
    CancelRecordingIntent,
    ViewTranscriptIntent,
    EditTranscriptIntent,
    CommitEditsIntent,
    DiscardEditsIntent,
    DeleteTranscriptIntent,
    IntentOutcome,
    IntentResult,
)
from ui.interaction.intents import IntentSource


class TestIntentConstruction:
    """Test that intents can be constructed and are immutable."""

    def test_begin_recording_intent_construction(self):
        """BeginRecordingIntent can be constructed."""
        intent = BeginRecordingIntent()
        assert intent.source == IntentSource.CONTROLS

    def test_begin_recording_intent_with_source(self):
        """BeginRecordingIntent can specify source."""
        intent = BeginRecordingIntent(source=IntentSource.HOTKEY)
        assert intent.source == IntentSource.HOTKEY

    def test_stop_recording_intent_construction(self):
        """StopRecordingIntent can be constructed."""
        intent = StopRecordingIntent()
        assert isinstance(intent, InteractionIntent)

    def test_cancel_recording_intent_construction(self):
        """CancelRecordingIntent can be constructed."""
        intent = CancelRecordingIntent()
        assert isinstance(intent, InteractionIntent)

    def test_view_transcript_intent_construction(self):
        """ViewTranscriptIntent requires timestamp and text."""
        intent = ViewTranscriptIntent(timestamp="2026-01-11T12:00:00", text="Test text")
        assert intent.timestamp == "2026-01-11T12:00:00"
        assert intent.text == "Test text"

    def test_edit_transcript_intent_construction(self):
        """EditTranscriptIntent can be constructed."""
        intent = EditTranscriptIntent()
        assert isinstance(intent, InteractionIntent)

    def test_commit_edits_intent_construction(self):
        """CommitEditsIntent requires content."""
        intent = CommitEditsIntent(content="edited text")
        assert intent.content == "edited text"

    def test_discard_edits_intent_construction(self):
        """DiscardEditsIntent can be constructed."""
        intent = DiscardEditsIntent()
        assert isinstance(intent, InteractionIntent)

    def test_delete_transcript_intent_construction(self):
        """DeleteTranscriptIntent requires timestamp."""
        intent = DeleteTranscriptIntent(timestamp="2026-01-11T12:00:00")
        assert intent.timestamp == "2026-01-11T12:00:00"

    def test_intent_immutability(self):
        """Intents are frozen and cannot be mutated."""
        intent = BeginRecordingIntent()
        with pytest.raises(FrozenInstanceError):
            intent.source = IntentSource.SIDEBAR  # type: ignore


class TestIntentResultConstruction:
    """Test IntentResult construction and helper methods."""

    def test_accepted_result_construction(self):
        """IntentResult with ACCEPTED outcome can be constructed."""
        intent = BeginRecordingIntent()
        result = IntentResult(outcome=IntentOutcome.ACCEPTED, intent=intent)
        assert result.outcome == IntentOutcome.ACCEPTED
        assert result.intent is intent
        assert result.reason is None

    def test_rejected_result_construction(self):
        """IntentResult with REJECTED outcome and reason."""
        intent = BeginRecordingIntent()
        result = IntentResult(
            outcome=IntentOutcome.REJECTED,
            intent=intent,
            reason="Cannot record in editing state",
        )
        assert result.outcome == IntentOutcome.REJECTED
        assert result.reason == "Cannot record in editing state"

    def test_deferred_result_construction(self):
        """IntentResult with DEFERRED outcome."""
        intent = EditTranscriptIntent()
        result = IntentResult(
            outcome=IntentOutcome.DEFERRED,
            intent=intent,
            reason="Transcription in progress",
        )
        assert result.outcome == IntentOutcome.DEFERRED
        assert result.is_pending()

    def test_no_op_result_construction(self):
        """IntentResult with NO_OP outcome."""
        intent = EditTranscriptIntent()
        result = IntentResult(
            outcome=IntentOutcome.NO_OP,
            intent=intent,
            reason="Already in edit mode",
        )
        assert result.outcome == IntentOutcome.NO_OP
        assert result.is_success()

    def test_result_helper_methods(self):
        """IntentResult helper methods work correctly."""
        intent = BeginRecordingIntent()

        accepted = IntentResult(outcome=IntentOutcome.ACCEPTED, intent=intent)
        assert accepted.is_success()
        assert not accepted.is_failure()
        assert not accepted.is_pending()

        rejected = IntentResult(outcome=IntentOutcome.REJECTED, intent=intent)
        assert not rejected.is_success()
        assert rejected.is_failure()
        assert not rejected.is_pending()

        deferred = IntentResult(outcome=IntentOutcome.DEFERRED, intent=intent)
        assert not deferred.is_success()
        assert not deferred.is_failure()
        assert deferred.is_pending()

    def test_result_has_timestamp(self):
        """IntentResult has automatic timestamp."""
        intent = BeginRecordingIntent()
        result = IntentResult(outcome=IntentOutcome.ACCEPTED, intent=intent)
        assert result.timestamp > 0


class TestIntentSourceEnum:
    """Test IntentSource enum values."""

    def test_all_sources_defined(self):
        """All expected intent sources are defined."""
        assert IntentSource.CONTROLS
        assert IntentSource.SIDEBAR
        assert IntentSource.HOTKEY
        assert IntentSource.CONTEXT_MENU
        assert IntentSource.INTERNAL


class TestHandleIntentPassthrough:
    """Test handle_intent() passthrough without state assertions.

    These tests verify that handle_intent() can be called and returns
    an IntentResult. They do NOT assert on state transitions—that is
    Phase 3+ work.
    """

    @pytest.fixture
    def workspace(self, qapp_session):
        """Create MainWorkspace instance for testing."""
        from ui.components.workspace import MainWorkspace
        w = MainWorkspace()
        return w

    def test_handle_begin_recording_returns_result(self, workspace):
        """handle_intent(BeginRecordingIntent) returns IntentResult."""
        intent = BeginRecordingIntent()
        result = workspace.handle_intent(intent)
        assert isinstance(result, IntentResult)
        assert result.intent is intent

    def test_handle_stop_recording_returns_result(self, workspace):
        """handle_intent(StopRecordingIntent) returns IntentResult."""
        intent = StopRecordingIntent()
        result = workspace.handle_intent(intent)
        assert isinstance(result, IntentResult)

    def test_handle_edit_returns_result(self, workspace):
        """handle_intent(EditTranscriptIntent) returns IntentResult."""
        intent = EditTranscriptIntent()
        result = workspace.handle_intent(intent)
        assert isinstance(result, IntentResult)

    def test_handle_commit_returns_result(self, workspace):
        """handle_intent(CommitEditsIntent) returns IntentResult."""
        intent = CommitEditsIntent(content="test")
        result = workspace.handle_intent(intent)
        assert isinstance(result, IntentResult)

    def test_handle_discard_returns_result(self, workspace):
        """handle_intent(DiscardEditsIntent) returns IntentResult."""
        intent = DiscardEditsIntent()
        result = workspace.handle_intent(intent)
        assert isinstance(result, IntentResult)

    def test_handle_delete_returns_result(self, workspace):
        """handle_intent(DeleteTranscriptIntent) returns IntentResult."""
        intent = DeleteTranscriptIntent(timestamp="2026-01-11T12:00:00")
        result = workspace.handle_intent(intent)
        assert isinstance(result, IntentResult)

    def test_handle_view_returns_result(self, workspace):
        """handle_intent(ViewTranscriptIntent) returns IntentResult."""
        intent = ViewTranscriptIntent(timestamp="2026-01-11T12:00:00", text="Test")
        result = workspace.handle_intent(intent)
        assert isinstance(result, IntentResult)

    def test_intent_processed_signal_emitted(self, workspace):
        """intentProcessed signal is emitted after handling."""
        intent = BeginRecordingIntent()
        
        received_results = []
        workspace.intentProcessed.connect(lambda r: received_results.append(r))
        
        workspace.handle_intent(intent)
        
        assert len(received_results) == 1
        assert received_results[0].intent is intent

class TestEditIntentStateAssertions:
    """Phase 4: Tests with explicit state assertions for edit safety.
    
    These tests verify that illegal transitions are rejected and that
    legal ones preserve invariants.
    """
    
    @pytest.fixture
    def workspace(self, qapp_session):
        """Create MainWorkspace instance for testing."""
        from ui.components.workspace import MainWorkspace
        from ui.constants import WorkspaceState
        w = MainWorkspace()
        return w

    def test_edit_rejected_in_idle_no_transcript(self, workspace):
        """EditTranscriptIntent must be rejected in IDLE (no transcript)."""
        from ui.constants import WorkspaceState
        
        assert workspace.get_state() == WorkspaceState.IDLE
        
        intent = EditTranscriptIntent()
        result = workspace.handle_intent(intent)
        
        assert result.outcome == IntentOutcome.REJECTED
        assert workspace.get_state() == WorkspaceState.IDLE  # State unchanged

    def test_edit_rejected_in_recording(self, workspace):
        """EditTranscriptIntent must be rejected in RECORDING state."""
        from ui.constants import WorkspaceState
        
        # Enter recording state
        workspace.set_state(WorkspaceState.RECORDING)
        
        intent = EditTranscriptIntent()
        result = workspace.handle_intent(intent)
        
        assert result.outcome == IntentOutcome.REJECTED
        assert workspace.get_state() == WorkspaceState.RECORDING  # State unchanged

    def test_edit_accepted_in_viewing_with_transcript(self, workspace):
        """EditTranscriptIntent must be accepted in VIEWING with transcript loaded."""
        from ui.constants import WorkspaceState
        
        # Load a transcript (puts workspace in VIEWING state)
        workspace.load_transcript("Test transcript", "2026-01-11T12:00:00")
        assert workspace.get_state() == WorkspaceState.VIEWING
        
        intent = EditTranscriptIntent()
        result = workspace.handle_intent(intent)
        
        assert result.outcome == IntentOutcome.ACCEPTED
        assert workspace.get_state() == WorkspaceState.EDITING  # State changed

    def test_begin_recording_rejected_in_editing(self, workspace):
        """BeginRecordingIntent must be rejected in EDITING (Invariant 2)."""
        from ui.constants import WorkspaceState
        
        # Load transcript and enter editing
        workspace.load_transcript("Test transcript", "2026-01-11T12:00:00")
        workspace.set_state(WorkspaceState.EDITING)
        
        intent = BeginRecordingIntent()
        result = workspace.handle_intent(intent)
        
        assert result.outcome == IntentOutcome.REJECTED
        assert "editing" in result.reason.lower()
        assert workspace.get_state() == WorkspaceState.EDITING  # State unchanged

    def test_edit_no_op_when_already_editing(self, workspace):
        """EditTranscriptIntent should be NO_OP when already in EDITING."""
        from ui.constants import WorkspaceState
        
        # Load transcript and enter editing
        workspace.load_transcript("Test transcript", "2026-01-11T12:00:00")
        workspace.set_state(WorkspaceState.EDITING)
        
        intent = EditTranscriptIntent()
        result = workspace.handle_intent(intent)
        
        assert result.outcome == IntentOutcome.NO_OP
        assert workspace.get_state() == WorkspaceState.EDITING


class TestCommitIntentStateAssertions:
    """Phase 4: Tests for CommitEditsIntent state assertions."""
    
    @pytest.fixture
    def workspace(self, qapp_session):
        """Create MainWorkspace instance for testing."""
        from ui.components.workspace import MainWorkspace
        w = MainWorkspace()
        return w

    def test_commit_accepted_in_editing(self, workspace):
        """CommitEditsIntent must be accepted in EDITING and transition to VIEWING."""
        from ui.constants import WorkspaceState
        
        # Load transcript and enter editing
        workspace.load_transcript("Original text", "2026-01-11T12:00:00")
        edit_result = workspace.handle_intent(EditTranscriptIntent())
        assert edit_result.outcome == IntentOutcome.ACCEPTED
        assert workspace.get_state() == WorkspaceState.EDITING
        
        # Now commit
        intent = CommitEditsIntent(content="Edited text")
        result = workspace.handle_intent(intent)
        
        assert result.outcome == IntentOutcome.ACCEPTED
        assert workspace.get_state() == WorkspaceState.VIEWING
        assert not workspace.has_unsaved_changes()

    def test_commit_rejected_when_not_editing(self, workspace):
        """CommitEditsIntent must be rejected when not in EDITING state."""
        from ui.constants import WorkspaceState
        
        # Start in IDLE
        assert workspace.get_state() == WorkspaceState.IDLE
        
        intent = CommitEditsIntent(content="Some text")
        result = workspace.handle_intent(intent)
        
        assert result.outcome == IntentOutcome.REJECTED
        assert workspace.get_state() == WorkspaceState.IDLE

    def test_commit_rejected_in_viewing(self, workspace):
        """CommitEditsIntent must be rejected in VIEWING state."""
        from ui.constants import WorkspaceState
        
        # Load transcript (goes to VIEWING)
        workspace.load_transcript("Test text", "2026-01-11T12:00:00")
        assert workspace.get_state() == WorkspaceState.VIEWING
        
        intent = CommitEditsIntent(content="Edited text")
        result = workspace.handle_intent(intent)
        
        assert result.outcome == IntentOutcome.REJECTED
        assert workspace.get_state() == WorkspaceState.VIEWING

    def test_commit_emits_save_requested_signal(self, workspace):
        """CommitEditsIntent should emit saveRequested signal with content."""
        from ui.constants import WorkspaceState
        
        # Load transcript and enter editing
        workspace.load_transcript("Original", "2026-01-11T12:00:00")
        workspace.handle_intent(EditTranscriptIntent())
        
        # Track signal
        saved_content = []
        workspace.saveRequested.connect(lambda text: saved_content.append(text))
        
        # Commit with new text
        intent = CommitEditsIntent(content="New content")
        result = workspace.handle_intent(intent)
        
        assert result.outcome == IntentOutcome.ACCEPTED
        assert len(saved_content) == 1
        assert saved_content[0] == "New content"


class TestDiscardIntentStateAssertions:
    """Phase 4: Tests for DiscardEditsIntent state assertions."""
    
    @pytest.fixture
    def workspace(self, qapp_session):
        """Create MainWorkspace instance for testing."""
        from ui.components.workspace import MainWorkspace
        w = MainWorkspace()
        return w

    def test_discard_accepted_in_editing(self, workspace):
        """DiscardEditsIntent must be accepted in EDITING and transition to VIEWING."""
        from ui.constants import WorkspaceState
        
        # Load transcript and enter editing
        workspace.load_transcript("Original text", "2026-01-11T12:00:00")
        edit_result = workspace.handle_intent(EditTranscriptIntent())
        assert edit_result.outcome == IntentOutcome.ACCEPTED
        assert workspace.get_state() == WorkspaceState.EDITING
        
        # Now discard
        intent = DiscardEditsIntent()
        result = workspace.handle_intent(intent)
        
        assert result.outcome == IntentOutcome.ACCEPTED
        assert workspace.get_state() == WorkspaceState.VIEWING
        assert not workspace.has_unsaved_changes()

    def test_discard_no_op_when_not_editing(self, workspace):
        """DiscardEditsIntent should be NO_OP when not in EDITING state."""
        from ui.constants import WorkspaceState
        
        # Start in IDLE
        assert workspace.get_state() == WorkspaceState.IDLE
        
        intent = DiscardEditsIntent()
        result = workspace.handle_intent(intent)
        
        assert result.outcome == IntentOutcome.NO_OP
        assert workspace.get_state() == WorkspaceState.IDLE

    def test_discard_no_op_in_viewing(self, workspace):
        """DiscardEditsIntent should be NO_OP in VIEWING state."""
        from ui.constants import WorkspaceState
        
        # Load transcript (goes to VIEWING)
        workspace.load_transcript("Test text", "2026-01-11T12:00:00")
        assert workspace.get_state() == WorkspaceState.VIEWING
        
        intent = DiscardEditsIntent()
        result = workspace.handle_intent(intent)
        
        assert result.outcome == IntentOutcome.NO_OP
        assert workspace.get_state() == WorkspaceState.VIEWING

    def test_discard_does_not_emit_save_signal(self, workspace):
        """DiscardEditsIntent should NOT emit saveRequested signal."""
        from ui.constants import WorkspaceState
        
        # Load transcript and enter editing
        workspace.load_transcript("Original", "2026-01-11T12:00:00")
        workspace.handle_intent(EditTranscriptIntent())
        
        # Track signal - should not be called
        saved_content = []
        workspace.saveRequested.connect(lambda text: saved_content.append(text))
        
        # Discard
        intent = DiscardEditsIntent()
        result = workspace.handle_intent(intent)
        
        assert result.outcome == IntentOutcome.ACCEPTED
        assert len(saved_content) == 0  # Signal should NOT fire


class TestViewIntentStateAssertions:
    """Phase 5: Tests for ViewTranscriptIntent state assertions."""
    
    @pytest.fixture
    def workspace(self, qapp_session):
        """Create MainWorkspace instance for testing."""
        from ui.components.workspace import MainWorkspace
        w = MainWorkspace()
        return w

    def test_view_accepted_in_idle_transitions_to_viewing(self, workspace):
        """ViewTranscriptIntent in IDLE with text transitions to VIEWING."""
        from ui.constants import WorkspaceState
        
        assert workspace.get_state() == WorkspaceState.IDLE
        
        intent = ViewTranscriptIntent(timestamp="2026-01-11T12:00:00", text="Test text")
        result = workspace.handle_intent(intent)
        
        assert result.outcome == IntentOutcome.ACCEPTED
        assert workspace.get_state() == WorkspaceState.VIEWING
        assert not workspace.has_unsaved_changes()

    def test_view_accepted_in_viewing_switches_transcript(self, workspace):
        """ViewTranscriptIntent in VIEWING switches to different transcript."""
        from ui.constants import WorkspaceState
        
        # First view
        workspace.handle_intent(ViewTranscriptIntent(
            timestamp="2026-01-11T12:00:00", text="First"
        ))
        assert workspace.get_state() == WorkspaceState.VIEWING
        
        # Switch to different transcript
        intent = ViewTranscriptIntent(timestamp="2026-01-11T13:00:00", text="Second")
        result = workspace.handle_intent(intent)
        
        assert result.outcome == IntentOutcome.ACCEPTED
        assert workspace.get_state() == WorkspaceState.VIEWING

    def test_view_rejected_in_recording(self, workspace):
        """ViewTranscriptIntent must be rejected in RECORDING state."""
        from ui.constants import WorkspaceState
        
        # Enter recording
        workspace.handle_intent(BeginRecordingIntent())
        assert workspace.get_state() == WorkspaceState.RECORDING
        
        intent = ViewTranscriptIntent(timestamp="2026-01-11T12:00:00", text="Test")
        result = workspace.handle_intent(intent)
        
        assert result.outcome == IntentOutcome.REJECTED
        assert workspace.get_state() == WorkspaceState.RECORDING

    def test_view_rejected_in_editing_with_unsaved_changes(self, workspace):
        """ViewTranscriptIntent rejected in EDITING with unsaved changes (Invariant 3)."""
        from ui.constants import WorkspaceState
        
        # Load transcript and enter editing
        workspace.load_transcript("Original", "2026-01-11T12:00:00")
        workspace.handle_intent(EditTranscriptIntent())
        assert workspace.get_state() == WorkspaceState.EDITING
        # Qt textChanged fires, so has_unsaved_changes is True
        
        # Try to view different transcript
        intent = ViewTranscriptIntent(timestamp="2026-01-11T13:00:00", text="Other")
        result = workspace.handle_intent(intent)
        
        assert result.outcome == IntentOutcome.REJECTED
        assert workspace.get_state() == WorkspaceState.EDITING

    def test_view_with_empty_text_stays_idle(self, workspace):
        """ViewTranscriptIntent with empty text results in IDLE state."""
        from ui.constants import WorkspaceState
        
        intent = ViewTranscriptIntent(timestamp="2026-01-11T12:00:00", text="")
        result = workspace.handle_intent(intent)
        
        assert result.outcome == IntentOutcome.ACCEPTED
        assert workspace.get_state() == WorkspaceState.IDLE

    def test_view_rejected_without_timestamp(self, workspace):
        """ViewTranscriptIntent rejected without timestamp."""
        intent = ViewTranscriptIntent(timestamp="", text="Test")
        result = workspace.handle_intent(intent)
        
        assert result.outcome == IntentOutcome.REJECTED


class TestDeleteIntentStateAssertions:
    """Phase 5: Tests for DeleteTranscriptIntent state assertions."""
    
    @pytest.fixture
    def workspace(self, qapp_session):
        """Create MainWorkspace instance for testing."""
        from ui.components.workspace import MainWorkspace
        w = MainWorkspace()
        return w

    def test_delete_accepted_in_viewing_emits_signal(self, workspace):
        """DeleteTranscriptIntent in VIEWING emits deleteRequested signal."""
        from ui.constants import WorkspaceState
        
        # Load transcript to enter VIEWING
        workspace.load_transcript("Test text", "2026-01-11T12:00:00")
        assert workspace.get_state() == WorkspaceState.VIEWING
        
        # Track signal
        delete_requested = []
        workspace.deleteRequested.connect(lambda: delete_requested.append(True))
        
        intent = DeleteTranscriptIntent(timestamp="2026-01-11T12:00:00")
        result = workspace.handle_intent(intent)
        
        assert result.outcome == IntentOutcome.ACCEPTED
        assert len(delete_requested) == 1
        # State should NOT change yet (until clear_transcript is called)
        assert workspace.get_state() == WorkspaceState.VIEWING

    def test_delete_rejected_in_idle(self, workspace):
        """DeleteTranscriptIntent rejected in IDLE state."""
        from ui.constants import WorkspaceState
        
        assert workspace.get_state() == WorkspaceState.IDLE
        
        intent = DeleteTranscriptIntent(timestamp="2026-01-11T12:00:00")
        result = workspace.handle_intent(intent)
        
        assert result.outcome == IntentOutcome.REJECTED
        assert "idle" in result.reason.lower()

    def test_delete_rejected_in_recording(self, workspace):
        """DeleteTranscriptIntent rejected in RECORDING state."""
        from ui.constants import WorkspaceState
        
        workspace.handle_intent(BeginRecordingIntent())
        assert workspace.get_state() == WorkspaceState.RECORDING
        
        intent = DeleteTranscriptIntent(timestamp="2026-01-11T12:00:00")
        result = workspace.handle_intent(intent)
        
        assert result.outcome == IntentOutcome.REJECTED
        assert workspace.get_state() == WorkspaceState.RECORDING

    def test_delete_rejected_in_editing(self, workspace):
        """DeleteTranscriptIntent rejected in EDITING state."""
        from ui.constants import WorkspaceState
        
        workspace.load_transcript("Test", "2026-01-11T12:00:00")
        workspace.handle_intent(EditTranscriptIntent())
        assert workspace.get_state() == WorkspaceState.EDITING
        
        intent = DeleteTranscriptIntent(timestamp="2026-01-11T12:00:00")
        result = workspace.handle_intent(intent)
        
        assert result.outcome == IntentOutcome.REJECTED
        assert workspace.get_state() == WorkspaceState.EDITING

    def test_clear_transcript_transitions_to_idle(self, workspace):
        """clear_transcript() transitions to IDLE after confirmed delete."""
        from ui.constants import WorkspaceState
        
        workspace.load_transcript("Test", "2026-01-11T12:00:00")
        assert workspace.get_state() == WorkspaceState.VIEWING
        
        # Delete intent accepted (emits signal, no state change)
        workspace.handle_intent(DeleteTranscriptIntent(timestamp="2026-01-11T12:00:00"))
        assert workspace.get_state() == WorkspaceState.VIEWING
        
        # Now simulate MainWindow calling clear_transcript after confirmation
        workspace.clear_transcript()
        
        assert workspace.get_state() == WorkspaceState.IDLE
        assert not workspace.has_unsaved_changes()


class TestPhase4StoppingCondition:
    """Tests verifying Phase 4 stopping condition is met.
    
    Stopping condition: Editing is impossible to exit without
    explicit terminal intent (CommitEditsIntent or DiscardEditsIntent).
    """
    
    @pytest.fixture
    def workspace(self, qapp_session):
        """Create MainWorkspace instance for testing."""
        from ui.components.workspace import MainWorkspace
        w = MainWorkspace()
        return w

    def test_only_terminal_intents_exit_editing(self, workspace):
        """Only CommitEditsIntent and DiscardEditsIntent can exit EDITING."""
        from ui.constants import WorkspaceState
        
        # Setup: enter editing
        workspace.load_transcript("Test text", "2026-01-11T12:00:00")
        workspace.handle_intent(EditTranscriptIntent())
        assert workspace.get_state() == WorkspaceState.EDITING
        
        # Try BeginRecordingIntent - should be REJECTED
        result = workspace.handle_intent(BeginRecordingIntent())
        assert result.outcome == IntentOutcome.REJECTED
        assert workspace.get_state() == WorkspaceState.EDITING
        
        # Try ViewTranscriptIntent - should be REJECTED (unsaved changes)
        result = workspace.handle_intent(ViewTranscriptIntent(timestamp="other", text="Other"))
        assert result.outcome == IntentOutcome.REJECTED
        assert workspace.get_state() == WorkspaceState.EDITING
        
        # Try EditTranscriptIntent - should be NO_OP
        result = workspace.handle_intent(EditTranscriptIntent())
        assert result.outcome == IntentOutcome.NO_OP
        assert workspace.get_state() == WorkspaceState.EDITING
        
        # CommitEditsIntent exits to VIEWING
        result = workspace.handle_intent(CommitEditsIntent(content="text"))
        assert result.outcome == IntentOutcome.ACCEPTED
        assert workspace.get_state() == WorkspaceState.VIEWING
        
        # Re-enter editing and test discard
        workspace.handle_intent(EditTranscriptIntent())
        assert workspace.get_state() == WorkspaceState.EDITING
        
        # DiscardEditsIntent exits to VIEWING
        result = workspace.handle_intent(DiscardEditsIntent())
        assert result.outcome == IntentOutcome.ACCEPTED
        assert workspace.get_state() == WorkspaceState.VIEWING

    def test_invariant_5_unsaved_changes_cleared_by_terminal(self, workspace):
        """Terminal intents must clear _has_unsaved_changes."""
        from ui.constants import WorkspaceState
        
        # Setup: enter editing and simulate text change
        workspace.load_transcript("Original", "2026-01-11T12:00:00")
        workspace.handle_intent(EditTranscriptIntent())
        # Qt textChanged fires on edit mode entry, so unsaved is True
        
        # Commit should clear it
        workspace.handle_intent(CommitEditsIntent(content="changed"))
        assert not workspace.has_unsaved_changes()
        
        # Re-enter and test discard
        workspace.handle_intent(EditTranscriptIntent())
        # Discard should also clear it
        workspace.handle_intent(DiscardEditsIntent())
        assert not workspace.has_unsaved_changes()


class TestPhase5AuthorityConsolidation:
    """Tests verifying Phase 5 authority consolidation is complete.
    
    Stopping condition: No external component mutates workspace state
    directly. All user-initiated state changes flow through handle_intent().
    """
    
    @pytest.fixture
    def workspace(self, qapp_session):
        """Create MainWorkspace instance for testing."""
        from ui.components.workspace import MainWorkspace
        w = MainWorkspace()
        return w

    def test_view_intent_is_authoritative(self, workspace):
        """ViewTranscriptIntent controls all view transitions."""
        from ui.constants import WorkspaceState
        
        # IDLE → VIEWING via intent
        result = workspace.handle_intent(ViewTranscriptIntent(
            timestamp="2026-01-11T12:00:00", text="Test"
        ))
        assert result.outcome == IntentOutcome.ACCEPTED
        assert workspace.get_state() == WorkspaceState.VIEWING
        
        # VIEWING → VIEWING (different transcript) via intent
        result = workspace.handle_intent(ViewTranscriptIntent(
            timestamp="2026-01-11T13:00:00", text="Other"
        ))
        assert result.outcome == IntentOutcome.ACCEPTED
        assert workspace.get_state() == WorkspaceState.VIEWING

    def test_delete_intent_validates_but_defers_state_change(self, workspace):
        """DeleteTranscriptIntent validates but doesn't change state directly."""
        from ui.constants import WorkspaceState
        
        workspace.load_transcript("Test", "2026-01-11T12:00:00")
        assert workspace.get_state() == WorkspaceState.VIEWING
        
        # Delete intent accepted but state unchanged
        result = workspace.handle_intent(DeleteTranscriptIntent(
            timestamp="2026-01-11T12:00:00"
        ))
        assert result.outcome == IntentOutcome.ACCEPTED
        assert workspace.get_state() == WorkspaceState.VIEWING  # Still viewing
        
        # State changes only via clear_transcript
        workspace.clear_transcript()
        assert workspace.get_state() == WorkspaceState.IDLE

    def test_all_destructive_click_routes_through_intents(self, workspace):
        """_on_destructive_click routes all cases through intent layer."""
        from ui.constants import WorkspaceState
        
        # RECORDING → cancel via intent
        workspace.handle_intent(BeginRecordingIntent())
        assert workspace.get_state() == WorkspaceState.RECORDING
        
        cancel_emitted = []
        workspace.cancelRequested.connect(lambda: cancel_emitted.append(True))
        workspace._on_destructive_click()
        
        assert len(cancel_emitted) == 1
        assert workspace.get_state() == WorkspaceState.IDLE
        
        # VIEWING → delete via intent
        workspace.handle_intent(ViewTranscriptIntent(
            timestamp="2026-01-11T12:00:00", text="Test"
        ))
        assert workspace.get_state() == WorkspaceState.VIEWING
        
        delete_emitted = []
        workspace.deleteRequested.connect(lambda: delete_emitted.append(True))
        workspace._on_destructive_click()
        
        assert len(delete_emitted) == 1
        # State still VIEWING (waiting for confirmation)
        assert workspace.get_state() == WorkspaceState.VIEWING