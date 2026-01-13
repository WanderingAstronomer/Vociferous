"""
SearchView - Dedicated search interface table.
"""

from __future__ import annotations

from ui.constants.view_ids import VIEW_SEARCH
from ui.views.base_view import BaseView


class SearchView(BaseView):
    """View for searching through transcription history."""

    def get_view_id(self) -> str:
        return VIEW_SEARCH
