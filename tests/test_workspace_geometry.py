"""
Tests for workspace geometry and layout invariants.

Verifies:
- Content expansion
- No nested scrolling
- Long transcript rendering
"""

import pytest
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QApplication, QScrollArea, QSizePolicy

from ui.components.workspace.workspace import MainWorkspace
from ui.constants import WorkspaceState

# Mark entire module as UI-dependent
pytestmark = pytest.mark.ui_dependent


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for Qt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestWorkspaceGeometry:
    """Tests for workspace layout and geometry invariants."""

    def test_content_expansion(self, qapp):
        """Test that content panel expands to fill available space."""
        workspace = MainWorkspace()
        workspace.resize(800, 600)
        workspace.show()
        
        # Force layout
        qapp.processEvents()
        
        # Check size policy of content panel
        policy = workspace.content_panel.sizePolicy()
        assert policy.verticalPolicy() == QSizePolicy.Policy.Expanding
        
        # Check that content_panel takes up significant vertical space
        # Header ~50-80px, Controls ~80px, Space ~600
        # Content panel should be > 300px
        assert workspace.content_panel.height() > 300
        
        workspace.close()

    def test_no_nested_scroll_areas(self, qapp):
        """Test that we don't have nested scroll areas in the content path."""
        workspace = MainWorkspace()
        
        # Search for QScrollArea children
        scroll_areas = workspace.findChildren(QScrollArea)
        
        # We expect 0 scroll areas in the workspace structure itself
        # (QTextEdit/QTextBrowser inherit from QAbstractScrollArea, but they are not QScrollArea)
        # Note: findChildren(QScrollArea) *does* return QTextEdit/Browser because they inherit QAbstractScrollArea
        # wait, QTextEdit inherits QAbstractScrollArea directly, not QScrollArea.
        # QScrollArea inherits QAbstractScrollArea.
        # So specific QScrollArea check should return 0 if we removed the outer one.
        
        scroll_areas = [c for c in workspace.findChildren(QScrollArea) if c.objectName() == "workspaceScrollArea"]
        assert len(scroll_areas) == 0, "Found banned 'workspaceScrollArea'"
        
        # Verify content hierarchy
        # Workspace -> ContentPanel -> WorkspaceContent -> Stack -> QTextBrowser
        content_panel = workspace.content_panel
        assert content_panel.layout().count() > 0
        
        workspace_content = content_panel.layout().itemAt(0).widget()
        assert workspace_content.objectName() == "workspaceContent"

    def test_long_transcript_rendering(self, qapp):
        """Test rendering of a very long transcript."""
        workspace = MainWorkspace()
        workspace.resize(800, 600)
        workspace.show()
        
        # Generate long text
        long_text = "Line of text\n" * 1000
        
        workspace.load_transcript(long_text, "2023-01-01T12:00:00")
        qapp.processEvents()
        
        # Check state
        assert workspace.get_state() == WorkspaceState.VIEWING
        
        # Check that text widget expands
        text_browser = workspace.content.transcript_view
        
        # The browser should be visible
        assert text_browser.isVisible()
        
        # The browser should fill the content panel (roughly)
        panel_rect = workspace.content_panel.contentsRect()
        
        # Browser might be deeper in stack, so map coordinates
        mapped_pos = text_browser.mapTo(workspace.content_panel, text_browser.rect().topLeft())
        
        # It should start near top-left of panel
        assert mapped_pos.y() < 20 # allowance for margins
        
        # Height should be close to panel height
        diff = panel_rect.height() - text_browser.height()
        assert diff < 40, f"Lost {diff}px of vertical space (clipping risk)"
        
        workspace.close()

