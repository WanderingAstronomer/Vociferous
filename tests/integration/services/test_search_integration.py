import pytest
from unittest.mock import MagicMock
from PyQt6.QtCore import Qt
from src.ui.components.main_window.main_window import MainWindow
from src.ui.views.search_view import SearchView
from src.database.history_manager import HistoryManager


@pytest.fixture
def mock_history_manager():
    return MagicMock(spec=HistoryManager)


def test_search_view_is_wired_in_main_window(qtbot, mock_history_manager):
    """
    Test that SearchView is correctly instantiated and wired in MainWindow.
    This test reproduces the 'unwired' issue.
    """
    window = MainWindow(history_manager=mock_history_manager)
    qtbot.addWidget(window)

    # Check that history_manager was passed to SearchView
    assert window.view_search._history_manager == mock_history_manager, (
        "HistoryManager should be injected into SearchView"
    )

    # Check that model is initialized
    assert window.view_search._model is not None, (
        "TranscriptionModel should be initialized in SearchView"
    )


def test_search_view_signals_are_connected(qtbot, mock_history_manager):
    """
    Test that SearchView signals are connected to MainWindow slots.
    """
    window = MainWindow(history_manager=mock_history_manager)
    qtbot.addWidget(window)

    # We can check connections by inspecting the receivers or triggering signals
    # Using receiver count is a bit implementation-specific but reliable for basic checks

    # edit_requested -> _on_edit_view_requested
    assert window.view_search.receivers(window.view_search.edit_requested) > 0, (
        "edit_requested signal should be connected"
    )

    # delete_requested -> ?
    assert window.view_search.receivers(window.view_search.delete_requested) > 0, (
        "delete_requested signal should be connected"
    )

    # refine_requested -> _on_refine_view_requested
    assert window.view_search.receivers(window.view_search.refine_requested) > 0, (
        "refine_requested signal should be connected"
    )
