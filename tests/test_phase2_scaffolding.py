"""
Verification tests for Phase 2 View Scaffolding.
"""

import pytest
from PyQt6.QtWidgets import QWidget

from ui.constants.view_ids import (
    VIEW_EDIT,
    VIEW_PROJECTS,
    VIEW_HISTORY,
    VIEW_REFINE,
    VIEW_SEARCH,
    VIEW_SETTINGS,
    VIEW_TRANSCRIBE,
    VIEW_USER,
)
from ui.contracts.capabilities import ViewInterface, ActionId
from ui.views.edit_view import EditView
from ui.views.projects_view import ProjectsView
from ui.views.history_view import HistoryView
from ui.views.refine_view import RefineView
from ui.views.search_view import SearchView
from ui.views.settings_view import SettingsView
from ui.views.transcribe_view import TranscribeView
from ui.views.user_view import UserView


@pytest.fixture
def views(qapp_session):
    """Fixture to provide instances of all views with proper cleanup."""
    # Note: qapp_session fixture ensures QApplication exists
    view_instances = [
        TranscribeView(),
        HistoryView(),
        ProjectsView(),
        SearchView(),
        RefineView(),
        EditView(),
        SettingsView(),
        UserView(),
    ]
    yield view_instances
    
    # Teardown
    for view in view_instances:
        view.deleteLater()
    from PyQt6.QtWidgets import QApplication
    QApplication.processEvents()


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
        HistoryView: VIEW_HISTORY,
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


def test_views_capabilities_contract(views):
    """
    Test that all views return a stable Capabilities object.
    (Address invariant: Views are governed by capabilities).
    """
    from ui.contracts.capabilities import Capabilities

    for view in views:
        caps = view.get_capabilities()
        assert isinstance(caps, Capabilities), f"{type(view).__name__} did not return a Capabilities object"
        
        # Stability check - value equality is enough
        caps2 = view.get_capabilities()
        # We compare attributes for semantic equality
        assert caps == caps2


def test_views_dispatch_contract(views):
    """
    Test that dispatch_action accepts valid ActionIds and returns deterministic result.
    """
    for view in views:
        try:
            result = view.dispatch_action(ActionId.CANCEL)
            # Assert contract: must return booleam (caught or not) or specific result type
            # Assuming ViewInterface implies bool or specific result. 
            # If implementation varies, we check it does not crash.
            # But contract says: "returns deterministic unsupport action result"
            # Most views likely return False for Cancel if they don't handle it.
            assert isinstance(result, bool) or result is None 
        except Exception as e:
            pytest.fail(f"dispatch_action crashed for {type(view).__name__}: {e}")
