"""
Tests for ViewHost and Router Invariants (Agent 2).
"""

import pytest
from PyQt6.QtWidgets import QWidget, QApplication
from src.ui.components.main_window.view_host import ViewHost

pytestmark = pytest.mark.ui_dependent


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_view_host_routing_signals(qapp):
    """Test that ViewHost emits correct signals on view switch."""
    host = ViewHost()

    view1 = QWidget()
    view2 = QWidget()

    host.register_view(view1, "v1")
    host.register_view(view2, "v2")

    # Capture signals
    signals = []
    host.view_changed.connect(lambda vid: signals.append(vid))

    # Enforce deterministic starting state
    # ViewHost now always emits view_changed to ensure observers sync,
    # even when switching to the already-current view
    host.switch_to_view("v1")
    assert signals == ["v1"], (
        "ViewHost emits signal on switch_to_view, even if already current"
    )

    assert host.get_current_view_id() == "v1"

    # Explicit switch to v2
    host.switch_to_view("v2")
    qapp.processEvents()
    assert signals == ["v1", "v2"]
    assert host.get_current_view_id() == "v2"
    assert host.currentWidget() == view2

    # Explicit switch to v1
    host.switch_to_view("v1")
    qapp.processEvents()
    assert signals == ["v1", "v2", "v1"]
    assert host.get_current_view_id() == "v1"
    assert host.currentWidget() == view1

    host.deleteLater()
    qapp.processEvents()


def test_view_host_initial_state_deterministic(qapp):
    """
    Invariant: Router state must be deterministic upon initialization.
    First registered view should become active automatically.
    """
    host = ViewHost()
    v1 = QWidget()
    v2 = QWidget()

    # Before registration, no view? or None?
    # host.get_current_view_id() might raise or return None

    host.register_view(v1, "initial_view")
    assert host.get_current_view_id() == "initial_view", (
        "First registered view must be active by default"
    )

    host.register_view(v2, "second_view")
    assert host.get_current_view_id() == "initial_view", (
        "Registration of subsequent views must not change active view"
    )


def test_view_host_single_active_invariant(qapp):
    """Invariant: Only one view is active at a time."""
    host = ViewHost()
    view1 = QWidget()
    view2 = QWidget()

    host.register_view(view1, "v1")
    host.register_view(view2, "v2")
    host.switch_to_view("v1")

    # We need to show the host for visibility properties to be meaningful?
    # Not necessarily for QStackedWidget logic, but let's trust currentIndex.

    host.switch_to_view("v2")
    assert host.currentIndex() == 1

    # Verify mapping
    assert host.get_current_view_id() == "v2"

    # Check attempting to get invalid view
    host.switch_to_view("invalid")
    assert host.get_current_view_id() == "v2"  # Should remain on last valid
