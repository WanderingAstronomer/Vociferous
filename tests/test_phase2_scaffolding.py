"""
Verification tests for Phase 2 View Scaffolding.
"""

import pytest
from PyQt6.QtWidgets import QWidget

from ui.constants.view_ids import (
    VIEW_EDIT,
    VIEW_PROJECTS,
    VIEW_RECENT,
    VIEW_REFINE,
    VIEW_SEARCH,
    VIEW_SETTINGS,
    VIEW_TRANSCRIBE,
    VIEW_USER,
)
from ui.contracts.capabilities import ViewInterface
from ui.views.edit_view import EditView
from ui.views.projects_view import ProjectsView
from ui.views.recent_view import RecentView
from ui.views.refine_view import RefineView
from ui.views.search_view import SearchView
from ui.views.settings_view import SettingsView
from ui.views.transcribe_view import TranscribeView
from ui.views.user_view import UserView


@pytest.fixture
def views(qapp_session):
    """Fixture to provide instances of all views."""
    # Note: qapp_session fixture ensures QApplication exists
    return [
        TranscribeView(),
        RecentView(),
        ProjectsView(),
        SearchView(),
        RefineView(),
        EditView(),
        SettingsView(),
        UserView(),
    ]


def test_views_instantiation(views):
    """Test that all view classes can be instantiated."""
    for view in views:
        assert isinstance(view, QWidget)
        assert view is not None


def test_views_implement_interface(views):
    """Test that all view instances pass the ViewInterface check."""
    for view in views:
        # Runtime checkable protocol check
        assert isinstance(view, ViewInterface), f"{type(view).__name__} does not implement ViewInterface"
        
        # Explicit method checks just in case
        assert hasattr(view, 'get_capabilities')
        assert hasattr(view, 'get_selection')
        assert hasattr(view, 'get_view_id')
        assert hasattr(view, 'dispatch_action')


def test_view_ids(views):
    """Test that each view returns the correct view ID."""
    view_map = {
        TranscribeView: VIEW_TRANSCRIBE,
        RecentView: VIEW_RECENT,
        ProjectsView: VIEW_PROJECTS,
        SearchView: VIEW_SEARCH,
        RefineView: VIEW_REFINE,
        EditView: VIEW_EDIT,
        SettingsView: VIEW_SETTINGS,
        UserView: VIEW_USER,
    }

    for view in views:
        expected_id = view_map[type(view)]
        assert view.get_view_id() == expected_id

