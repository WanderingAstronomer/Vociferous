"""
Integration tests for Refinement subsystem.
Enforces ingress validation, engine orchestration, and persistence contracts.
(Agent Requirements 2, 3, 4)
"""

import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import Qt
from src.ui.constants.view_ids import VIEW_REFINE, VIEW_HISTORY

pytestmark = pytest.mark.ui_dependent


@pytest.fixture
def mock_mainwindow(qtbot):
    """Fixture to provide a MainWindow with mocked dependencies."""
    # We need to patch dependencies BEFORE importing MainWindow to avoid heavy lifting
    with (
        patch(
            "src.ui.components.main_window.main_window.ActionDock"
        ) as mock_dock_class,
        patch("src.ui.components.main_window.main_window.IconRail") as mock_rail_class,
        patch("src.ui.components.main_window.main_window.ViewHost") as mock_host_class,
    ):
        from PyQt6.QtWidgets import QWidget
        from PyQt6.QtCore import pyqtSignal

        # Helper class to combine QWidget spec with real signals
        class MockWidgetWithSignals(QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.intent_emitted = MagicMock()
                self.intent_emitted.connect = MagicMock()
                self.view_changed = MagicMock()
                self.view_changed.connect = MagicMock()

        # IconRail Mock
        mock_rail = MockWidgetWithSignals()
        mock_rail_class.return_value = mock_rail

        # ViewHost Mock
        mock_host = MockWidgetWithSignals()
        mock_host.switch_to_view = MagicMock()
        mock_host.register_view = MagicMock()  # Added
        mock_host.get_current_view_id = MagicMock()
        mock_host_class.return_value = mock_host

        # ActionDock Mock
        mock_dock = MockWidgetWithSignals()
        mock_dock.set_active_view = MagicMock()  # Added
        mock_dock_class.return_value = mock_dock

        from src.ui.components.main_window.main_window import MainWindow

        # Mock HistoryManager
        mock_hist = MagicMock()
        window = MainWindow(history_manager=mock_hist)
        qtbot.addWidget(window)
        return window


def test_ingress_fails_safely_on_invalid_id(mock_mainwindow, caplog):
    """
    Contract 2: Ingress with invalid transcript ID must not crash
    and should not switch view state effectively (or log warning).
    """
    mock_mainwindow.view_host = MagicMock()  # Mock the view host to check switching
    mock_mainwindow.history_manager.get_entry.return_value = None

    # Trigger refine request with invalid ID
    mock_mainwindow._on_refine_view_requested(9999)

    # Assert Warning Logged
    assert "Refine requested for missing ID 9999" in caplog.text

    # Assert View Switch did NOT happen (or happened but halted - logic depends on impl)
    # Our impl returns early:
    # if not entry: return
    mock_mainwindow.view_host.switch_to_view.assert_not_called()


def test_mainwindow_owned_engine_orchestration(mock_mainwindow, qtbot):
    """
    Contract 3: MainWindow owns the orchestration.
    It takes the request, loads the view, and provides for future execution.
    """
    # Setup Data
    mock_entry = MagicMock()
    mock_entry.text = "Original Text"
    mock_mainwindow.history_manager.get_entry.return_value = mock_entry

    # We want to verify view_refine methods are called
    mock_mainwindow.view_refine = MagicMock()

    # Patch refinement_requested to avoid side effects
    mock_mainwindow.refinement_requested = MagicMock()

    # Trigger 1: Ingress (Navigating to view)
    mock_mainwindow._on_refine_view_requested(123)

    # Assert 1: View Switch
    mock_mainwindow.view_host.switch_to_view.assert_called_with(VIEW_REFINE)

    # Assert 2: View Loaded with data
    mock_mainwindow.view_refine.load_transcript_by_id.assert_called_with(
        123, "Original Text"
    )

    # Assert 3: Ingress does NOT set loading True (Draft mode)
    mock_mainwindow.view_refine.set_loading.assert_not_called()

    # Trigger 2: Execution (User clicking Refine in view)
    mock_mainwindow._on_refinement_execution_requested(123, "BALANCED", "Instruction")

    # Assert 4: Orchestrator sets loading and emits signal
    mock_mainwindow.view_refine.set_loading.assert_called_with(True)
    mock_mainwindow.refinement_requested.emit.assert_called_with(
        123, "Original Text", "BALANCED", "Instruction"
    )

    # Trigger 3: Completion (Simulating backend result)
    mock_mainwindow.on_refinement_complete(123, "Refined Result")

    # Assert 5: View updated with comparison data
    mock_mainwindow.view_refine.set_comparison.assert_called_with(
        123, "Original Text", "Refined Result"
    )


def test_persistence_update_on_accept(mock_mainwindow):
    """
    Contract 4: Persistence mutation on Accept.
    Accepting refinement must update normalized_text and return to History.
    """
    tid = 101
    refined_text = "Refined Result"

    # Trigger the accepted signal handler directly
    mock_mainwindow._on_refinement_accepted(tid, refined_text)

    # Assert HistoryManager called
    mock_mainwindow.history_manager.update_normalized_text.assert_called_once_with(
        tid, refined_text
    )

    # Assert Navigation Return
    mock_mainwindow.view_host.switch_to_view.assert_called_with(VIEW_HISTORY)


def test_no_persistence_on_discard(mock_mainwindow):
    """
    Contract 4: No persistence mutation on Discard.
    """
    # Trigger discard
    mock_mainwindow._on_refinement_discarded()

    # Assert HistoryManager NOT called
    mock_mainwindow.history_manager.update_normalized_text.assert_not_called()

    # Assert Navigation Return
    mock_mainwindow.view_host.switch_to_view.assert_called_with(VIEW_HISTORY)
