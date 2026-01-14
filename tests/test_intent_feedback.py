"""
Tests for IntentFeedbackHandler (Phase 6: Intent Outcome Visibility).

These tests verify that:
1. The handler consumes IntentResult objects (not workspace state)
2. REJECTED outcomes produce appropriate user messages
3. ACCEPTED and NO_OP outcomes are silent
4. Developer logging works correctly
"""

from unittest.mock import MagicMock, patch

import pytest

from ui.components.main_window.intent_feedback import IntentFeedbackHandler
from ui.interaction import (
    BeginRecordingIntent,
    CancelRecordingIntent,
    CommitEditsIntent,
    DeleteTranscriptIntent,
    DiscardEditsIntent,
    EditTranscriptIntent,
    IntentOutcome,
    IntentResult,
    StopRecordingIntent,
    ViewTranscriptIntent,
)


class TestIntentFeedbackMapping:
    """Test outcome-to-feedback mapping logic."""

    @pytest.fixture
    def mock_status_bar(self):
        """Create a mock status bar."""
        mock = MagicMock()
        # Mock the show/hide methods added in status bar visibility changes
        mock.show = MagicMock()
        mock.hide = MagicMock()
        # Configure parent to NOT have _status_label, so fallback to showMessage
        mock_parent = MagicMock(spec=[])  # Empty spec means no attributes
        mock.parent = MagicMock(return_value=mock_parent)
        return mock

    @pytest.fixture
    def handler(self, mock_status_bar):
        """Create IntentFeedbackHandler with mock status bar."""
        return IntentFeedbackHandler(mock_status_bar)

    # ACCEPTED outcomes should be silent

    def test_accepted_outcome_is_silent(self, handler, mock_status_bar):
        """ACCEPTED outcomes should not show any message."""
        result = IntentResult(
            outcome=IntentOutcome.ACCEPTED,
            intent=BeginRecordingIntent(),
        )

        handler.on_intent_processed(result)

        mock_status_bar.showMessage.assert_not_called()

    # NO_OP outcomes should be silent

    def test_no_op_outcome_is_silent(self, handler, mock_status_bar):
        """NO_OP outcomes should not show any message."""
        result = IntentResult(
            outcome=IntentOutcome.NO_OP,
            intent=EditTranscriptIntent(transcript_id=1),
            reason="Already editing",
        )

        handler.on_intent_processed(result)

        mock_status_bar.showMessage.assert_not_called()

    # REJECTED outcomes with user-facing messages

    def test_begin_recording_rejected_editing_shows_message(
        self, handler, mock_status_bar
    ):
        """BeginRecordingIntent rejected due to editing shows helpful message."""
        result = IntentResult(
            outcome=IntentOutcome.REJECTED,
            intent=BeginRecordingIntent(),
            reason="Currently editing",
        )

        handler.on_intent_processed(result)

        mock_status_bar.showMessage.assert_called_once()
        message = mock_status_bar.showMessage.call_args[0][0]
        assert "finish" in message.lower() or "discard" in message.lower()
        assert "edit" in message.lower()

    def test_view_transcript_rejected_unsaved_shows_message(
        self, handler, mock_status_bar
    ):
        """ViewTranscriptIntent rejected due to unsaved changes shows message."""
        result = IntentResult(
            outcome=IntentOutcome.REJECTED,
            intent=ViewTranscriptIntent(timestamp="test", text="test"),
            reason="Unsaved changes exist",
        )

        handler.on_intent_processed(result)

        mock_status_bar.showMessage.assert_called_once()
        message = mock_status_bar.showMessage.call_args[0][0]
        assert "save" in message.lower() or "discard" in message.lower()

    def test_view_transcript_rejected_recording_shows_message(
        self, handler, mock_status_bar
    ):
        """ViewTranscriptIntent rejected during recording shows message."""
        result = IntentResult(
            outcome=IntentOutcome.REJECTED,
            intent=ViewTranscriptIntent(timestamp="test", text="test"),
            reason="Cannot view while recording",
        )

        handler.on_intent_processed(result)

        mock_status_bar.showMessage.assert_called_once()
        message = mock_status_bar.showMessage.call_args[0][0]
        assert "recording" in message.lower()

    # REJECTED outcomes that should be silent (button shouldn't be visible)

    def test_stop_recording_rejected_is_silent(self, handler, mock_status_bar):
        """StopRecordingIntent rejected should be silent (button not visible)."""
        result = IntentResult(
            outcome=IntentOutcome.REJECTED,
            intent=StopRecordingIntent(),
            reason="Not recording",
        )

        handler.on_intent_processed(result)

        mock_status_bar.showMessage.assert_not_called()

    def test_commit_edits_rejected_is_silent(self, handler, mock_status_bar):
        """CommitEditsIntent rejected should be silent (button not visible)."""
        result = IntentResult(
            outcome=IntentOutcome.REJECTED,
            intent=CommitEditsIntent(content=""),
            reason="Not editing",
        )

        handler.on_intent_processed(result)

        mock_status_bar.showMessage.assert_not_called()

    def test_delete_rejected_not_viewing_is_silent(self, handler, mock_status_bar):
        """DeleteTranscriptIntent rejected in idle should be silent."""
        result = IntentResult(
            outcome=IntentOutcome.REJECTED,
            intent=DeleteTranscriptIntent(timestamp="test"),
            reason="Cannot delete in idle state",
        )

        handler.on_intent_processed(result)

        mock_status_bar.showMessage.assert_not_called()


class TestIntentFeedbackLogging:
    """Test developer-facing logging."""

    @pytest.fixture
    def mock_status_bar(self):
        return MagicMock()

    @pytest.fixture
    def handler(self, mock_status_bar):
        handler = IntentFeedbackHandler(mock_status_bar)
        handler.set_debug_logging(True)
        return handler

    def test_rejected_intent_logs_at_info(self, handler, mock_status_bar):
        """REJECTED intents should log at INFO level."""
        result = IntentResult(
            outcome=IntentOutcome.REJECTED,
            intent=BeginRecordingIntent(),
            reason="Test rejection",
        )

        with patch("ui.components.main_window.intent_feedback.logger") as mock_logger:
            handler.on_intent_processed(result)
            mock_logger.info.assert_called_once()

    def test_accepted_intent_logs_at_debug_when_enabled(self, handler, mock_status_bar):
        """ACCEPTED intents should log at DEBUG level when debug enabled."""
        result = IntentResult(
            outcome=IntentOutcome.ACCEPTED,
            intent=BeginRecordingIntent(),
        )

        with patch("ui.components.main_window.intent_feedback.logger") as mock_logger:
            handler.on_intent_processed(result)
            mock_logger.debug.assert_called_once()

    def test_accepted_intent_silent_when_debug_disabled(self, mock_status_bar):
        """ACCEPTED intents should not log when debug disabled."""
        handler = IntentFeedbackHandler(mock_status_bar)
        handler.set_debug_logging(False)  # Explicit disable

        result = IntentResult(
            outcome=IntentOutcome.ACCEPTED,
            intent=BeginRecordingIntent(),
        )

        with patch("ui.components.main_window.intent_feedback.logger") as mock_logger:
            handler.on_intent_processed(result)
            mock_logger.debug.assert_not_called()


class TestPhase6Constraints:
    """Verify Phase 6 constraints are maintained."""

    @pytest.fixture
    def mock_status_bar(self):
        """Create a mock status bar."""
        mock = MagicMock()
        # Mock the show/hide methods added in status bar visibility changes
        mock.show = MagicMock()
        mock.hide = MagicMock()
        # Configure parent to NOT have _status_label, so fallback to showMessage
        mock_parent = MagicMock(spec=[])  # Empty spec means no attributes
        mock.parent = MagicMock(return_value=mock_parent)
        return mock

    @pytest.fixture
    def handler(self, mock_status_bar):
        return IntentFeedbackHandler(mock_status_bar)

    def test_handler_never_queries_workspace_state(self, handler, mock_status_bar):
        """Handler must consume IntentResult only, never inspect workspace state.

        This test verifies the handler has no reference to workspace.
        The handler receives IntentResult objects and nothing else.
        """
        # Handler should not have any workspace reference
        assert not hasattr(handler, "workspace")
        assert not hasattr(handler, "_workspace")

        # Process a result - should work without any workspace
        result = IntentResult(
            outcome=IntentOutcome.REJECTED,
            intent=ViewTranscriptIntent(timestamp="test", text="test"),
            reason="Unsaved changes exist",
        )
        handler.on_intent_processed(result)

        # Should have shown message based solely on IntentResult
        mock_status_bar.showMessage.assert_called_once()

    def test_all_feedback_is_non_modal(self, handler, mock_status_bar):
        """All feedback should use status bar (non-modal), never dialogs."""
        # Process multiple rejection types
        rejections = [
            IntentResult(
                outcome=IntentOutcome.REJECTED,
                intent=BeginRecordingIntent(),
                reason="Currently editing",
            ),
            IntentResult(
                outcome=IntentOutcome.REJECTED,
                intent=ViewTranscriptIntent(timestamp="t", text="t"),
                reason="Unsaved changes",
            ),
        ]

        for result in rejections:
            handler.on_intent_processed(result)

        # All calls should be to showMessage (non-modal)
        assert mock_status_bar.showMessage.call_count == 2

        # Verify duration is set (auto-dismiss)
        for call in mock_status_bar.showMessage.call_args_list:
            args = call[0]
            assert len(args) == 2  # message, duration
            assert args[1] > 0  # duration > 0 means auto-dismiss
