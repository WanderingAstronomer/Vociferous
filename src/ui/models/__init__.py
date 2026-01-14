"""
Model layer - Qt data models for transcription history.

Provides:
- TranscriptionModel: Core model with day-grouped hierarchy
- ProjectProxyModel: Filters by Project
"""

from ui.models.project_proxy import ProjectProxyModel
from ui.models.transcription_model import TranscriptionModel

__all__ = [
    "ProjectProxyModel",
    "TranscriptionModel",
]
