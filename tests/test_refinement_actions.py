"""
Tests for Refinement Actions, Queueing, and UI Interactions.
Covers recent fixes for Echoing, UI Blocking, and History Update.
"""

import pytest
from unittest.mock import MagicMock, call, patch
from PyQt6.QtCore import Qt, QThread
from src.ui.constants.view_ids import VIEW_HISTORY, VIEW_REFINE

# We need to import MainWindow to mock its parts, but dependent on imports
# so we might need to handle imports inside fixtures or patch extensively.


@pytest.fixture
def mock_mainwindow_full(qtbot):
    """
    Creates a MainWindow with mocked views and history manager,
    specifically designed to test _on_refinement_accepted and busy states.
    """
    from src.ui.components.main_window.main_window import MainWindow
    from PyQt6.QtWidgets import QWidget

    # Helper class for UI mocks to satisfy type checks (must be QWidget for addWidget)
    class MockWidget(QWidget):
        def __init__(self, *args, **kwargs):
            super().__init__()
            self.show_message = MagicMock()
            self.hide = MagicMock()
            self.intent_emitted = MagicMock()
            self.view_changed = MagicMock()
            self.intent_emitted.connect = MagicMock()
            self.view_changed.connect = MagicMock()
            self.set_active_view = MagicMock()
            # Mocks for ViewHost
            self.switch_to_view = MagicMock()
            self.register_view = MagicMock()

    # dependencies match standard construction
    history_mock = MagicMock()

    # We use new_callable to provide the QWidget-based mock
    with (
        patch(
            "src.ui.components.main_window.main_window.BlockingOverlay",
            new_callable=lambda: MockWidget,
        ),
        patch(
            "src.ui.components.main_window.main_window.IconRail",
            new_callable=lambda: MockWidget,
        ),
        patch(
            "src.ui.components.main_window.main_window.ActionDock",
            new_callable=lambda: MockWidget,
        ),
        patch(
            "src.ui.components.main_window.main_window.ViewHost",
            new_callable=lambda: MockWidget,
        ),
    ):
        # When MainWindow instantiates them, it gets our MockWidget instances
        window = MainWindow(history_manager=history_mock)
        qtbot.addWidget(window)

        # Access the instances (MainWindow stores them in attributes)
        # Note: patch return value is the CLASS, but we need the instance.
        # Since we used new_callable which returns a class (lambda),
        # accessing MockOverlay.return_value won't work as expected if we want the specific instance logic.
        # Instead, we should look at window._blocking_overlay, window.icon_rail, etc.

        window.mock_overlay = window._blocking_overlay
        window.mock_host = window.view_host

        window.view_history = MagicMock()
        window.view_refine = MagicMock()

        return window


def test_refinement_acceptance_refreshes_history(mock_mainwindow_full):
    """
    Verifies that accepting a refinement:
    1. Updates the DB (HistoryManager)
    2. Refreshes the HistoryView (Critical Fix)
    3. Switches view to History
    """
    window = mock_mainwindow_full
    transcript_id = 101
    new_text = "Refined content"

    # Act
    window._on_refinement_accepted(transcript_id, new_text)

    # Assert 1: DB Update
    window.history_manager.update_normalized_text.assert_called_with(
        transcript_id, new_text
    )

    # Note: UI Refresh is now handled reactively via DatabaseSignalBridge
    # when history_manager.update_normalized_text is called.
    # We no longer expect a manual call to view_history.refresh()

    # Assert 3: View Switch
    window.view_host.switch_to_view.assert_called_with(VIEW_HISTORY)


def test_blocking_overlay_activation(mock_mainwindow_full):
    """
    Verifies that set_app_busy toggles the BlockingOverlay and cursor.
    """
    window = mock_mainwindow_full
    overlay = window.mock_overlay

    # Act: Busy
    window.set_app_busy(True, "Loading...")

    # Assert: Shown with message (show_message takes message and optional title)
    overlay.show_message.assert_called_with("Loading...", title="System Busy")
    assert window.cursor().shape() == Qt.CursorShape.WaitCursor

    # Act: Not Busy
    window.set_app_busy(False)

    # Assert: Hidden
    overlay.hide.assert_called_once()
    assert window.cursor().shape() == Qt.CursorShape.ArrowCursor


def test_slm_runtime_ignores_requests_when_not_ready(qtbot):
    """SLMRuntime should not call the engine when not READY."""
    from src.services.slm_runtime import SLMRuntime, SLMState

    runtime = SLMRuntime()
    runtime._engine = MagicMock()

    # 1. Not ready
    runtime._state = SLMState.LOADING

    # Request refine
    runtime.refine_text("Original")

    # Engine should not be called when runtime is not READY
    runtime._engine.refine.assert_not_called()


def test_runtime_parameters_forwarded(qtbot):
    """SLMRuntime should forward the text to the engine for refinement."""
    from src.services.slm_runtime import SLMRuntime, SLMState

    runtime = SLMRuntime()
    runtime._engine = MagicMock()
    runtime._state = SLMState.READY

    # Ensure the thread pool runs tasks synchronously for this test
    runtime._thread_pool.start = lambda fn: fn()

    # Act
    runtime.refine_text("Text")

    # Assert: runtime passes the text to engine.refine
    runtime._engine.refine.assert_called_with("Text")



