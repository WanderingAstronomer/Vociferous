"""
Tests for Icon Rail specific invariants.
Reviewing Invariant Section 7.
"""

import pytest
from unittest.mock import Mock
from PyQt6.QtCore import Qt, QTimer, QEventLoop
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QAbstractItemView,
    QListView,
    QTreeView,
)

from src.ui.components.main_window.icon_rail import IconRail, RailButton, RAIL_WIDTH
from src.ui.constants.view_ids import VIEW_TRANSCRIBE, VIEW_HISTORY, VIEW_PROJECTS
from src.ui.interaction.intents import NavigateIntent

# Mark UI dependent
pytestmark = pytest.mark.ui_dependent


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    yield app


class TestIconRailInvariants:
    def test_canonical_composition_no_lists(self, qapp):
        """
        Invariant 7.2: Canonical Composition.
        The Icon Rail does not contain list or tree widgets.
        """
        rail = IconRail()
        rail.show()
        qapp.processEvents()

        # Check direct children and deep children
        # We enforce "no list/tree widgets"
        banned_types = (QListView, QTreeView, QAbstractItemView)
        for child in rail.findChildren(QWidget):
            if isinstance(child, banned_types):
                pytest.fail(
                    f"Icon Rail contains banned widget type: {type(child).__name__}"
                )

        # Also verify width is fixed (Invariant 7.2.3: Width is constant)
        # Note: We check fixed width constraints, not actual width which may vary with DPI
        assert rail.minimumWidth() == rail.maximumWidth()
        assert rail.minimumWidth() == RAIL_WIDTH

        rail.close()

    def test_active_indication_from_state(self, qapp):
        """
        Invariant 7.4: Active Indication.
        Exactly one icon is rendered as active, dervied from external set_active_view.
        """
        rail = IconRail()
        rail.show()
        qapp.processEvents()

        # Simulate router update
        rail.set_active_view(VIEW_TRANSCRIBE)

        # Public contract query
        active_id = rail.get_active_view_id()
        assert active_id == VIEW_TRANSCRIBE

        # Switch to another
        rail.set_active_view(VIEW_HISTORY)
        assert rail.get_active_view_id() == VIEW_HISTORY

        # Switch to view NOT on rail (e.g. some random string)
        # Policy: If view is not on rail, no button should be active.
        rail.set_active_view("UNKNOWN_VIEW_ID")
        assert rail.get_active_view_id() is None

        rail.close()

    def test_blink_signal_behavior(self, qapp, qtbot):
        """
        Invariant 7.5: View Switch Blink Signal.
        Newly active icon performs a single blink animation.
        """
        rail = IconRail()
        rail.show()
        qapp.processEvents()

        # 1. Trigger activation
        # We need access to the button to connect to its signal,
        # or we verify checks on the rail.
        # Since 'blink' is on the button, we need to find the button.
        # But we shouldn't rely on private _button_group.
        # However, for verification of *internal animation behavior*, getting the button via findChild is acceptable.

        rail.set_active_view(VIEW_PROJECTS)

        # Find the button for projects
        target_btn = None
        for btn in rail.findChildren(RailButton):
            if btn.view_id == VIEW_PROJECTS:
                target_btn = btn
                break
        assert target_btn is not None

        # Spy on the signal
        with qtbot.waitSignal(target_btn.blink_finished, timeout=1000):
            target_btn.blink()

        # Property should be inactive after signal completion
        assert target_btn.property("blink") == "inactive"

        rail.close()

    def test_navigation_intent_emission(self, qapp, qtbot):
        """
        Invariant 7.6: Interaction Semantics.
        """
        rail = IconRail()
        rail.show()
        qapp.processEvents()

        with qtbot.waitSignal(rail.intent_emitted) as blocker:
            # Click the History button
            # Need to find it
            target_btn = None
            for btn in rail.findChildren(RailButton):
                if btn.view_id == VIEW_HISTORY:
                    target_btn = btn
                    break

            assert target_btn is not None
            qtbot.mouseClick(target_btn, Qt.MouseButton.LeftButton)

        intent = blocker.args[0]
        assert isinstance(intent, NavigateIntent)
        assert intent.target_view_id == VIEW_HISTORY

        rail.close()
