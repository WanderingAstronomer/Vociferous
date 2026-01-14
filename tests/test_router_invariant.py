"""
Tests for ViewHost and Router Invariants (Agent 2).
"""

import pytest
from PyQt6.QtWidgets import QWidget, QApplication
from ui.components.view_host import ViewHost

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
    host.viewChanged.connect(lambda vid: signals.append(vid))
    
    # QStackedWidget defaults to index 0 on adding?
    # Usually yes. So "v1" might be current.
    assert host.get_current_view_id() == "v1"
    
    # Explicit switch to v2
    host.switch_to_view("v2")
    assert signals == ["v2"]
    assert host.get_current_view_id() == "v2"
    assert host.currentWidget() == view2
    
    # Explicit switch to v1
    host.switch_to_view("v1")
    assert signals == ["v2", "v1"]
    assert host.get_current_view_id() == "v1"
    assert host.currentWidget() == view1

def test_view_host_single_active_invariant(qapp):
    """Invariant: Only one view is active at a time."""
    host = ViewHost()
    view1 = QWidget()
    view2 = QWidget()
    
    host.register_view(view1, "v1")
    host.register_view(view2, "v2")
    
    # We need to show the host for visibility properties to be meaningful?
    # Not necessarily for QStackedWidget logic, but let's trust currentIndex.
    
    host.switch_to_view("v2")
    assert host.currentIndex() == 1
    
    # Verify mapping
    assert host.get_current_view_id() == "v2"
    
    # Check attempting to get invalid view
    host.switch_to_view("invalid")
    assert host.get_current_view_id() == "v2"  # Should remain on last valid

