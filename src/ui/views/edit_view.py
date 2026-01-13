"""
EditView - Ephemeral editor view.
"""

from __future__ import annotations

from ui.constants.view_ids import VIEW_EDIT
from ui.views.base_view import BaseView


class EditView(BaseView):
    """View for editing transcription text."""

    def get_view_id(self) -> str:
        return VIEW_EDIT
