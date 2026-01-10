"""
Model layer - Qt data models for transcription history.

Provides:
- TranscriptionModel: Core model with day-grouped hierarchy
- FocusGroupProxyModel: Filters by focus group
"""

from ui.models.focus_group_proxy import FocusGroupProxyModel
from ui.models.transcription_model import TranscriptionModel

__all__ = [
    "FocusGroupProxyModel",
    "TranscriptionModel",
]
