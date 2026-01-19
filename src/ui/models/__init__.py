"""
Model layer - Qt data models for transcription history.

Provides:
- TranscriptionModel: Core model with day-grouped hierarchy
- ProjectProxyModel: Filters by Project
- TranscriptionTableModel: Flat model for table views
"""

from src.ui.models.project_proxy import ProjectProxyModel
from src.ui.models.transcription_model import TranscriptionModel
from src.ui.models.table_model import TranscriptionTableModel

__all__ = [
    "ProjectProxyModel",
    "TranscriptionModel",
    "TranscriptionTableModel",
]
