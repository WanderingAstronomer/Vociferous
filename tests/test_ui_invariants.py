"""
UI Invariants Tests.

Enforces the Vociferous UI Master Invariants via static analysis and runtime checks.
See: docs/agent_resources/agent_orders/vociferous_ui_master_invariants.md
"""

import os
import re
import pytest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication, QScrollArea, QAbstractScrollArea, QWidget, QLabel, QSizePolicy
from PyQt6.QtCore import Qt

from ui.components.main_window.main_window import MainWindow
from ui.components.title_bar import TitleBar
from ui.components.icon_rail import IconRail
from ui.components.workspace import MainWorkspace
from ui.widgets.metrics_strip import MetricsStrip
from ui.components.view_host import ViewHost
from ui.constants.view_ids import VIEW_TRANSCRIBE, VIEW_HISTORY

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
                        rel_path = os.path.relpath(os.path.join(root, filename), self.ROOT_DIR)
                        violations.append(f"Found banned file: {rel_path}")

        assert not violations, "\n".join(violations)

    def test_no_inline_hex_colors(self):
        """
        Invariant 2.1: Single Source of Truth for Visual Tokens.
        Fails if hard-coded hex colors appear in production widgets (src/ui).
        Excludes: src/ui/constants/*, src/ui/styles/*
        """
        import ast
        import re
        
        # Regex to find hex colors within string literals
        # Matches #RGB or #RRGGBB, followed by non-word char or end of string
        # to avoid matching #123456789 (random IDs)
        hex_pattern = re.compile(r'#[0-9a-fA-F]{3,6}\b')
        violations = []

        excluded_dirs = [
            os.path.join(self.UI_DIR, "constants"),
            os.path.join(self.UI_DIR, "styles"),
        ]

        for root, _, files in os.walk(self.UI_DIR):
            # Skip excluded directories
            if any(root.startswith(ex_dir) for ex_dir in excluded_dirs):
                continue
            
            # Skip __pycache__
            if "__pycache__" in root:
                continue

            for filename in files:
                if not filename.endswith(".py"):
                    continue
                
                filepath = os.path.join(root, filename)

                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        tree = ast.parse(f.read(), filename=filepath)
                except (SyntaxError, UnicodeDecodeError):
                    continue
                
                class StringVisitor(ast.NodeVisitor):
                    def visit_Constant(self, node):
                        if isinstance(node.value, str):
                            matches = hex_pattern.findall(node.value)
                            if matches:
                                # Filter out likely non-colors (e.g. #1 issue ref) if needed
                                # But for now, any look-alike is suspect in UI code
                                rel_path = os.path.relpath(filepath, TestStaticInvariants.ROOT_DIR)
                                violations.append(f"{rel_path}:{node.lineno} hex colors found {matches[:3]}...")
                        self.generic_visit(node)
                
                StringVisitor().visit(tree)

        assert not violations, (
            "Invariant 2.1 Violation: Hard-coded hex colors found in UI code.\n"
            "Use tokens from ui.constants.colors or ui.styles.theme instead.\n" + "\n".join(violations)
        )


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
            assert len(workspaces) == 1, f"Expected 1 MainWorkspace, found {len(workspaces)}"
            
            # 5. Metrics Strip
            metrics_strips = window.findChildren(MetricsStrip)
            assert len(metrics_strips) == 1, f"Expected 1 MetricsStrip, found {len(metrics_strips)}"
            
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
                        pytest.fail(f"Invariant 3.2 Violation: Nested scroll area found inside {sa.objectName()} -> {real_nested[0].objectName()}")
        
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
        
        assert len(scroll_areas) > 0, "MainWorkspace should have a ScrollArea (or QTextEdit)"
        
        # Heuristic: The largest one is likely the content
        main_scroll = max(scroll_areas, key=lambda w: w.height() * w.width() if w.isVisible() else 0)
        
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
            QSizePolicy.Policy.Ignored
        ]
        assert policy_enum in allowed_policies, f"Content widget must have vertical expansion policy. Got {policy_enum}"
        
        workspace.close()
        workspace.deleteLater()
