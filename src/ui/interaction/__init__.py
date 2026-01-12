"""
Interaction layer for intent-driven UI semantics.

This module defines the vocabulary of user interactions as first-class
data types. Intents represent user desires; outcomes represent system
responses. The workspace interprets intents and produces outcomes.

Note: This layer is deliberately inert. Intents do not execute actions;
they name them. Execution remains in existing handlers until Phase 3.
"""

from ui.interaction.intents import (
    BeginRecordingIntent,
    CancelRecordingIntent,
    CommitEditsIntent,
    DeleteTranscriptIntent,
    DiscardEditsIntent,
    EditTranscriptIntent,
    IntentSource,
    InteractionIntent,
    StopRecordingIntent,
    ViewTranscriptIntent,
)
from ui.interaction.results import IntentOutcome, IntentResult

__all__ = [
    # Intent types
    "InteractionIntent",
    "IntentSource",
    "BeginRecordingIntent",
    "StopRecordingIntent",
    "ViewTranscriptIntent",
    "EditTranscriptIntent",
    "CommitEditsIntent",
    "DiscardEditsIntent",
    "DeleteTranscriptIntent",
    "CancelRecordingIntent",
    # Outcome types
    "IntentOutcome",
    "IntentResult",
]
