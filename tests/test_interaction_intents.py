"""
Tests for interaction intent vocabulary (Phase 2).

These tests verify:
- Intent construction and immutability
- IntentResult construction
- handle_intent() passthrough (no state assertions)

Per Phase 2 guidance: tests assert construction and passthrough only.
State transition assertions belong to Phase 3+.
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
        """ViewTranscriptIntent requires timestamp."""
        intent = ViewTranscriptIntent(timestamp="2026-01-11T12:00:00")
        assert intent.timestamp == "2026-01-11T12:00:00"

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
        intent = ViewTranscriptIntent(timestamp="2026-01-11T12:00:00")
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
