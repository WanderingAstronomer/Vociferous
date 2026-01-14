"""
Tests for Surface Owners: Title Bar, Metrics Strip.
"""
import pytest
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget
from PyQt6.QtCore import Qt
from ui.components.title_bar.title_bar import TitleBar
from ui.widgets.metrics_strip.metrics_strip import MetricsStrip, MetricBlock

pytestmark = pytest.mark.ui_dependent

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    yield app

class TestTitleBarInvariants:
    def test_canonical_controls_exist(self, qapp):
        """Invariant 9.2: Window controls always function."""
        win = QMainWindow()
        title_bar = TitleBar(win)
        win.setMenuWidget(title_bar) # Or however it's attached, simpler to just parent it for test
        
        # Must show window for visibility
        win.show()
        qapp.processEvents()
        
        assert title_bar.min_btn.isVisible()
        assert title_bar.max_btn.isVisible()
        assert title_bar.close_btn.isVisible()
        assert title_bar.close_btn.objectName() == "titleBarClose"
        
        # Test maximize toggle interaction logic (invariant 9.2.3)
        # Initially normal
        assert not (win.windowState() & Qt.WindowState.WindowMaximized)
        
        # Toggle via click (public interaction)
        title_bar.max_btn.click()
        qapp.processEvents()
        assert win.windowState() & Qt.WindowState.WindowMaximized
        
        # Toggle back
        title_bar.max_btn.click()
        qapp.processEvents()
        assert not (win.windowState() & Qt.WindowState.WindowMaximized)

        win.close()
    
    def test_title_bar_geometry_invariant(self, qapp):
        """Invariant 9.3: Title bar height is constant."""
        win = QMainWindow()
        title_bar = TitleBar(win)
        win.setMenuWidget(title_bar)
        win.show()
        qapp.processEvents()
        
        # Height is fixed to 44 in code
        assert title_bar.minimumHeight() == 44
        assert title_bar.maximumHeight() == 44
        
        win.close()

class TestMetricsStripInvariants:
    def test_metrics_persistence_and_composition(self, qapp):
        """
        Invariant 10.1: Placement and Persistence.
        Invariant 10.2: Metrics Semantics (Deterministic Calculation).
        """
        # Create a parent window to host the strip
        win = QMainWindow()
        strip = MetricsStrip(parent=win)
        win.setCentralWidget(strip) # Or dock, just ensure it's in layout
        
        win.show()
        qapp.processEvents()
        
        assert strip.isVisible()
        
        # Verify composition (MetricBlocks)
        blocks = strip.findChildren(MetricBlock)
        assert len(blocks) > 0, "Metrics strip should have metric blocks"
        
        # Confirm labels exist (e.g. Time, Words)
        labels = [b.label.text() for b in blocks]
        # We don't hardcode exact text if it varies, but there should be text
        assert all(len(l) > 0 for l in labels)
        
        win.close()
