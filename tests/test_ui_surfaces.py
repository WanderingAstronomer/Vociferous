"""
Tests for Surface Owners: Title Bar.
"""

import pytest
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget
from PyQt6.QtCore import Qt
from src.ui.components.title_bar.title_bar import TitleBar

pytestmark = pytest.mark.ui_dependent


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    yield app


class TestTitleBarInvariants:
    def test_canonical_controls_exist(self, qapp, qtbot):
        """Invariant 9.2: Window controls always function."""
        win = QMainWindow()
        qtbot.addWidget(win)
        title_bar = TitleBar(win)
        win.setMenuWidget(
            title_bar
        )  # Or however it's attached, simpler to just parent it for test

        # Must show window for visibility
        win.show()
        qtbot.waitUntil(win.isVisible)

        assert title_bar.min_btn.isVisible()
        assert title_bar.max_btn.isVisible()
        assert title_bar.close_btn.isVisible()
        assert title_bar.close_btn.objectName() == "titleBarClose"

        # Test maximize toggle interaction logic (invariant 9.2.3)
        # Initially normal
        assert not (win.windowState() & Qt.WindowState.WindowMaximized)

        # Toggle via click (public interaction)
        qtbot.mouseClick(title_bar.max_btn, Qt.MouseButton.LeftButton)

        # Helper to check state
        def check_maximized():
            assert win.windowState() & Qt.WindowState.WindowMaximized

        qtbot.waitUntil(check_maximized)

        # Toggle back
        qtbot.mouseClick(title_bar.max_btn, Qt.MouseButton.LeftButton)

        def check_normalized():
            assert not (win.windowState() & Qt.WindowState.WindowMaximized)

        qtbot.waitUntil(check_normalized)

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
