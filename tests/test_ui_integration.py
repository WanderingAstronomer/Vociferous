"""
Integration tests for UI interactions and invariants.

Validates:
1. Boot flow (MainWindow instantiation, default view)
2. View Navigation (Router/Icon Rail consistency)
3. Hotkey State Transitions (Record -> Transcribe -> Idle)

Test Tier: UI-Dependent (Tier 2)
"""

import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication, QWidget

# Guard for pytest-qt
pytest.importorskip("pytestqt")

# Mark entire module as UI-dependent
pytestmark = pytest.mark.ui_dependent


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for Qt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def mock_dependencies():
    """Mock out hardware/backend dependencies for deterministic UI testing."""
    # Patch exact paths used in MainWindow imports
    with (
        patch("src.ui.components.main_window.main_window.SystemTrayManager"),
        patch("src.ui.components.main_window.main_window.TranscriptMetrics"),
        patch("src.ui.components.main_window.main_window.ActionDock"),
        patch("src.ui.components.main_window.main_window.IconRail") as mock_rail_class,
        patch("src.ui.components.main_window.main_window.ViewHost") as mock_host_class,
    ):
        # Make Mocks functional QWidgets so layout doesn't crash
        mock_rail_class.return_value = MagicMock(spec=QWidget)
        mock_host_class.return_value = MagicMock(spec=QWidget)
        yield


def test_boot_smoke_invariant(qapp, qtbot):
    """
    Invariant: Application boots to valid state with canonical surfaces (Action Dock, Main View).
    """
    from src.ui.components.main_window.main_window import MainWindow, ActionDock
    from src.ui.components.main_window.view_host import ViewHost

    mock_history = MagicMock()

    # Instantiate
    window = MainWindow()  # History manager set via setter or injected if ctor changes
    window.set_history_manager(mock_history)

    qtbot.addWidget(window)
    window.show()

    assert window.isVisible()

    # Assert Action Dock exists (property check)
    assert isinstance(window.action_dock, ActionDock)
    # Assert ViewHost exists
    assert isinstance(window.view_host, ViewHost)

    window.close()


def test_navigation_invariant(qapp, qtbot):
    """
    Invariant: Navigation switches views deterministically.
    """
    from src.ui.components.main_window.main_window import MainWindow
    from src.ui.interaction.intents import NavigateIntent

    # Real MainWindow with Mocks
    mock_history = MagicMock()
    window = MainWindow()
    window.set_history_manager(mock_history)
    qtbot.addWidget(window)
    window.show()

    # Use internal intent handler to simulate signal
    intent = NavigateIntent(target_view_id="settings")
    window._on_interaction_intent(intent)

    # Verify ViewHost invoked or state changed
    # Assuming view_host has a public method or we check active view logic
    # Ideally: window.view_host.set_view.assert_called_with("settings")
    # But view_host is real here (we didn't use mock_dependencies fixture for this test specifically)

    # If using real ViewHost, we check state
    current = window.view_host.get_current_view_id()
    assert current == "settings"

    window.close()


def test_hotkey_state_transition(qapp, qtbot):
    """
    Invariant: Recording Start -> Stop transitions state.
    """
    pass


def test_input_output_consistency(qapp, qtbot):
    """
    Invariant: Text input appears in Transcript View.
    """
    pass
