"""
Tests for workspace geometry and layout invariants.

Verifies:
- Content expansion
- No nested scrolling
- Long transcript rendering
"""

import pytest
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QApplication, QScrollArea, QSizePolicy, QAbstractScrollArea

from src.ui.components.workspace.workspace import MainWorkspace
from src.ui.constants import WorkspaceState
from src.ui.widgets.workspace_panel import WorkspacePanel

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

    def test_content_expansion_geometry(self, qapp):
        """
        Test that content panel physically expands in the render tree.
        Validates Invariant 8.2: Content Area Expansion Rules.
        """
        workspace = MainWorkspace()
        workspace.resize(800, 800)
        workspace.show()
        qapp.processEvents()

        # Get geometry
        content_panel = workspace.content_panel
        content_h = content_panel.height()
        total_h = workspace.height()

        # Ratio-based assertion (Scale-Invariant)
        ratio = content_h / total_h
        expected_ratio = 0.55

        assert ratio >= expected_ratio, (
            f"Content panel height {content_h} is too small relative to window {total_h} (ratio {ratio:.2f}, expected >= {expected_ratio})"
        )

        workspace.close()

    def test_no_nested_scroll_areas(self, qapp):
        """
        Test that we don't have nested scroll areas in the content path.
        Validates Invariant 3.2.4: Nested scroll areas are prohibited.
        """
        workspace = MainWorkspace()
        workspace.show()
        qapp.processEvents()

        # Strict policy: Zero QScrollArea instances unless explicitly whitelisted.
        allowed_scroll_areas = {
            "contentPanelPainted"
        }  # The object name of the main content panel

        scroll_areas = workspace.findChildren(QScrollArea)
        violations = []

        for sa in scroll_areas:
            # Check allowance based on objectName
            if sa.objectName() not in allowed_scroll_areas:
                violations.append(f"{sa.objectName()} ({type(sa).__name__})")

        assert not violations, f"Found banned QScrollArea instances: {violations}"

        workspace.close()

    def test_long_transcript_rendering_geometry(self, qapp, qtbot):
        """
        Test rendering of a very long transcript validates single scroll surface.
        """
        workspace = MainWorkspace()
        workspace.resize(800, 600)

        # Use proper sync waiting for show
        with qtbot.waitExposed(workspace):
            workspace.show()

        # Generate long text
        long_text = "Line of text\n" * 5000

        workspace.load_transcript(long_text, "2023-01-01T12:00:00")

        # Force layout and ensure widget is visible
        workspace.update()
        workspace.repaint()
        QApplication.processEvents()
        qtbot.wait(200)

        # Check using public accessor
        panel = workspace.get_transcript_scroll_area()
        # The panel itself is a Container (QFrame), not the ScrollArea
        # We must find the VISIBLE scrollable widget (transcript_view is QTextBrowser)
        from PyQt6.QtWidgets import QTextBrowser

        scroll_area = panel.findChild(QTextBrowser, "transcriptView")
        assert scroll_area is not None, "No QTextBrowser found in content panel"

        # Ensure scroll_area is visible and has proper geometry
        assert scroll_area.isVisible(), (
            f"Scroll area is not visible (parent visible: {scroll_area.parent().isVisible()})"
        )
        assert scroll_area.height() > 0, (
            f"Scroll area has no height: {scroll_area.height()}"
        )

        # Robust check: Verify Content Size > Viewport Size
        # QAbstractScrollArea for text (QTextEdit) manages scrolling internally via document layout
        def check_layout():
            # Force document layout
            scroll_area.document().adjustSize()
            scroll_area.updateGeometry()
            doc_h = scroll_area.document().size().height()
            vp_h = scroll_area.viewport().height()
            text_len = len(scroll_area.toPlainText())
            assert doc_h > vp_h, (
                f"Document height {doc_h} <= Viewport {vp_h} (text length: {text_len}, lines: {text_len // 13})"
            )

        qtbot.waitUntil(check_layout, timeout=5000)

        workspace.close()
