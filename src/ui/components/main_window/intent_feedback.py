"""
IntentFeedbackHandler - Presentation layer for intent outcomes.

Phase 6: Maps IntentResult outcomes to user-visible feedback.
This component consumes IntentResult objects directly and NEVER inspects workspace state.

Architecture:
    User Action → handle_intent() → IntentResult → intentProcessed signal → here → status bar
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QTimer, pyqtSlot

from ui.interaction import (
    IntentOutcome,
    IntentResult,
    BeginRecordingIntent,
    StopRecordingIntent,
    CancelRecordingIntent,
    ViewTranscriptIntent,
    EditTranscriptIntent,
    CommitEditsIntent,
    DiscardEditsIntent,
    DeleteTranscriptIntent,
)

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QStatusBar

logger = logging.getLogger(__name__)


class IntentFeedbackHandler(QObject):
    """Maps intent outcomes to user feedback.
    
    Phase 6 constraints:
    - Consumes IntentResult only, never inspects workspace state
    - All feedback is non-modal (status bar messages)
    - ACCEPTED outcomes are silent by default
    - REJECTED outcomes produce informative messages
    - NO_OP outcomes are silent
    
    Usage:
        handler = IntentFeedbackHandler(status_bar)
        workspace.intentProcessed.connect(handler.on_intent_processed)
    """
    
    # Message display duration in milliseconds
    MESSAGE_DURATION_MS = 4000
    
    def __init__(self, status_bar: QStatusBar, parent: QObject | None = None):
        super().__init__(parent)
        self._status_bar = status_bar
        self._debug_logging = False
    
    def set_debug_logging(self, enabled: bool) -> None:
        """Enable or disable verbose debug logging of intent outcomes."""
        self._debug_logging = enabled
    
    @pyqtSlot(object)
    def on_intent_processed(self, result: IntentResult) -> None:
        """Handle an intent result and provide appropriate feedback.
        
        This is the main entry point, connected to workspace.intentProcessed signal.
        """
        # Developer-facing observability
        self._log_intent_result(result)
        
        # User-facing feedback based on outcome
        match result.outcome:
            case IntentOutcome.ACCEPTED:
                self._handle_accepted(result)
            case IntentOutcome.REJECTED:
                self._handle_rejected(result)
            case IntentOutcome.NO_OP:
                self._handle_no_op(result)
            case IntentOutcome.DEFERRED:
                self._handle_deferred(result)
    
    def _log_intent_result(self, result: IntentResult) -> None:
        """Structured logging for developer observability."""
        intent_name = type(result.intent).__name__
        outcome_name = result.outcome.name
        
        match result.outcome:
            case IntentOutcome.ACCEPTED:
                if self._debug_logging:
                    logger.debug("Intent %s: %s", intent_name, outcome_name)
            case IntentOutcome.REJECTED:
                logger.info(
                    "Intent %s: %s - %s",
                    intent_name,
                    outcome_name,
                    result.reason or "no reason"
                )
            case IntentOutcome.NO_OP:
                if self._debug_logging:
                    logger.debug(
                        "Intent %s: %s - %s",
                        intent_name,
                        outcome_name,
                        result.reason or "already in target state"
                    )
            case IntentOutcome.DEFERRED:
                if self._debug_logging:
                    logger.debug(
                        "Intent %s: %s - %s",
                        intent_name,
                        outcome_name,
                        result.reason or "awaiting input"
                    )
    
    def _handle_accepted(self, result: IntentResult) -> None:
        """Handle ACCEPTED outcome - silent by default."""
        # Success is expected; no interruption needed.
        # Exception: Could add brief indicators for recording state changes.
        pass
    
    def _handle_rejected(self, result: IntentResult) -> None:
        """Handle REJECTED outcome - always provide feedback."""
        message = self._get_rejection_message(result)
        if message:
            self._show_status_message(message)
    
    def _handle_no_op(self, result: IntentResult) -> None:
        """Handle NO_OP outcome - silent."""
        # Idempotent operations are user-friendly; no feedback needed.
        pass
    
    def _handle_deferred(self, result: IntentResult) -> None:
        """Handle DEFERRED outcome - reserved for future use."""
        # Not currently used. When implemented, this would trigger
        # appropriate UI for gathering additional input.
        pass
    
    def _get_rejection_message(self, result: IntentResult) -> str | None:
        """Map a rejected intent to a user-friendly message.
        
        Returns None if the rejection should be silent (e.g., button shouldn't
        have been visible in the first place).
        """
        intent = result.intent
        reason = result.reason or ""
        
        # Recording rejections
        match intent:
            case BeginRecordingIntent():
                if "editing" in reason.lower():
                    return "Finish or discard edits before recording"
                if "recording" in reason.lower():
                    return None  # Already recording - button state handles this
                return f"Cannot start recording: {reason}"
            
            case StopRecordingIntent():
                return None  # Button shouldn't be visible if not recording
            
            case CancelRecordingIntent():
                return None  # Button shouldn't be visible if not recording
            
            # View/navigation rejections
            case ViewTranscriptIntent():
                if "unsaved" in reason.lower():
                    return "Save or discard changes first"
                if "recording" in reason.lower():
                    return "Stop recording to view transcripts"
                return f"Cannot view transcript: {reason}"
            
            # Edit rejections
            case EditTranscriptIntent():
                if "recording" in reason.lower():
                    return "Stop recording to edit"
                if "no transcript" in reason.lower():
                    return None  # Button shouldn't be visible
                return f"Cannot edit: {reason}"
            
            case CommitEditsIntent():
                return None  # Button shouldn't be visible if not editing
            
            case DiscardEditsIntent():
                return None  # Button shouldn't be visible if not editing
            
            # Delete rejections
            case DeleteTranscriptIntent():
                if "editing" in reason.lower():
                    return "Finish or discard edits before deleting"
                return None  # Button shouldn't be visible if not viewing
            
            case _:
                # Unknown intent type - show generic message
                return f"Action not available: {reason}" if reason else None
    
    def _show_status_message(self, message: str) -> None:
        """Display a message in the status bar."""
        self._status_bar.showMessage(message, self.MESSAGE_DURATION_MS)
