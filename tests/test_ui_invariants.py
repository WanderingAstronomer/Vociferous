"""
UI Invariants Tests.

Enforces the Vociferous UI Master Invariants via static analysis and runtime checks.
See: docs/agent_resources/agent_orders/vociferous_ui_master_invariants.md
"""

import os
import re
import pytest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import (
    QApplication,
    QScrollArea,
    QAbstractScrollArea,
    QWidget,
    QLabel,
    QSizePolicy,
)
from PyQt6.QtCore import Qt

from src.ui.components.main_window.main_window import MainWindow
from src.ui.components.title_bar import TitleBar
from src.ui.components.main_window.icon_rail import IconRail
from src.ui.components.workspace import MainWorkspace
from src.ui.components.main_window.view_host import ViewHost
from src.ui.constants.view_ids import VIEW_TRANSCRIBE, VIEW_HISTORY

# Mark entire module as UI-dependent
pytestmark = pytest.mark.ui_dependent


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for Qt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestStaticInvariants:
    """Static analysis tests for code structure and drift prevention."""

    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
    UI_DIR = os.path.join(ROOT_DIR, "ui")

    def test_no_parallel_implementations(self):
        """
        Invariant 1.3: No Parallel Production Implementations.
        Fails if any file ends with '_new.py' or contains 'delegate_new'.
        """
        banned_patterns = [r"_new\.py$", r"delegate_new"]
        violations = []

        for root, _, files in os.walk(self.ROOT_DIR):
            for filename in files:
                for pattern in banned_patterns:
                    if re.search(pattern, filename):
                        rel_path = os.path.relpath(
                            os.path.join(root, filename), self.ROOT_DIR
                        )
                        violations.append(f"Found banned file: {rel_path}")

        assert not violations, "\n".join(violations)

    def test_no_inline_hex_colors(self):
        """
        Invariant 2.1: Single Source of Truth for Visual Tokens.
        Fails if hard-coded hex colors appear in production widgets (src/ui).
        Excludes: src/ui/constants/*, src/ui/styles/*, and legacy widgets

        Refactored to run as a subprocess to prevent AST-related fatal aborts
        in the main test process.
        """
        import subprocess
        import sys

        script_path = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "verify_ui_colors.py"
        )

        # Ensure script exists
        assert os.path.exists(script_path), (
            f"Verification script not found: {script_path}"
        )

        # Run the script in a subprocess
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),  # Run from root
        )

        if result.returncode != 0:
            pytest.fail(f"AST Scan Failed:\n{result.stdout}\n{result.stderr}")


class TestRuntimeInvariants:
    """Runtime tests for object graph, ownership, and layout rules."""

    def test_surface_owners_instantiated_once(self, qapp):
        """
        Invariant 1.1: Single Ownership Per Surface.
        Invariant 14.1: Deterministic Composition Tests.
        Assert canonical surface owners are instantiated exactly once in MainWindow.
        """
        mock_history = MagicMock()

        try:
            window = MainWindow(history_manager=mock_history)
        except TypeError:
            window = MainWindow()

        try:
            # 1. Title Bar
            title_bars = window.findChildren(TitleBar)
            assert len(title_bars) == 1, f"Expected 1 TitleBar, found {len(title_bars)}"

            # 2. Icon Rail
            icon_rails = window.findChildren(IconRail)
            assert len(icon_rails) == 1, f"Expected 1 IconRail, found {len(icon_rails)}"

            # 3. View Host
            view_hosts = window.findChildren(ViewHost)
            assert len(view_hosts) == 1, f"Expected 1 ViewHost, found {len(view_hosts)}"

            # 4. Main Workspace (Should be somewhere in views)
            workspaces = window.findChildren(MainWorkspace)
            assert len(workspaces) == 1, (
                f"Expected 1 MainWorkspace, found {len(workspaces)}"
            )

        finally:
            window.close()
            window.deleteLater()

    def test_router_single_active_view(self, qapp):
        """
        Invariant 6.1: View Identity and Routing.
        Invariant 14.1: View router activates only one view at a time.
        """
        host = ViewHost()

        # create mock views
        view1 = QLabel("View 1")
        view2 = QLabel("View 2")

        host.register_view(view1, VIEW_TRANSCRIBE)
        host.register_view(view2, VIEW_HISTORY)

        # Activate view 1
        host.switch_to_view(VIEW_TRANSCRIBE)
        assert host.currentWidget() == view1
        # StackedWidget hides others automatically, but let's verify logic
        assert host.count() == 2

        # Activate view 2
        host.switch_to_view(VIEW_HISTORY)
        assert host.currentWidget() == view2

    def test_no_nested_scroll_areas(self, qapp):
        """
        Invariant 3.2: Scroll Area Rules.
        Nested scroll areas are prohibited in the workspace content path.
        """
        workspace = MainWorkspace()

        scroll_areas = workspace.findChildren(QScrollArea)

        for sa in scroll_areas:
            content = sa.widget()
            if content:
                nested_sas = content.findChildren(QScrollArea)
                if nested_sas:
                    real_nested = [n for n in nested_sas if n is not sa]
                    if real_nested:
                        pytest.fail(
                            f"Invariant 3.2 Violation: Nested scroll area found inside {sa.objectName()} -> {real_nested[0].objectName()}"
                        )

        workspace.close()
        workspace.deleteLater()

    def test_long_transcript_no_clipping(self, qapp):
        """
        Invariant 14.2: Geometry Regression Tests.
        Asserts that very long transcripts expand the content area and do not clip.
        """
        workspace = MainWorkspace()
        workspace.resize(800, 600)

        long_text = "Line\n" * 1000
        timestamp = "2023-01-01_12-00-00"

        workspace.load_transcript(long_text, timestamp)

        # Find the content display widget (QAbstractScrollArea covers QTextEdit, QScrollArea, etc.)
        scroll_areas = workspace.findChildren(QAbstractScrollArea)

        assert len(scroll_areas) > 0, (
            "MainWorkspace should have a ScrollArea (or QTextEdit)"
        )

        # Heuristic: The largest one is likely the content
        main_scroll = max(
            scroll_areas, key=lambda w: w.height() * w.width() if w.isVisible() else 0
        )

        if isinstance(main_scroll, QScrollArea):
            assert main_scroll.widgetResizable(), "Scroll area must be resizable"
            content_widget = main_scroll.widget()
        else:
            # QTextEdit/Browser
            content_widget = main_scroll

        assert content_widget is not None, "Scroll area must have a content widget"

        # Check size policy to ensure it expands
        policy_enum = content_widget.sizePolicy().verticalPolicy()
        allowed_policies = [
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.MinimumExpanding,
            QSizePolicy.Policy.Ignored,
        ]
        assert policy_enum in allowed_policies, (
            f"Content widget must have vertical expansion policy. Got {policy_enum}"
        )

        workspace.close()
        workspace.deleteLater()

    def test_refinement_status_message_handling(self, qapp):
        """Test that MainWindow.on_refinement_status_message calls IntentFeedbackHandler correctly."""
        from unittest.mock import MagicMock

        # Create MainWindow with mocked dependencies
        mock_history = MagicMock()
        window = MainWindow(history_manager=mock_history)

        # Mock the intent_feedback to verify the call
        window._intent_feedback = MagicMock()

        # Call the method
        test_message = "Test refinement status"
        window.on_refinement_status_message(test_message)

        # Assert that the handler's method was called with the message
        window._intent_feedback.on_refinement_status_message.assert_called_once_with(
            test_message
        )

        window.close()
        window.deleteLater()
