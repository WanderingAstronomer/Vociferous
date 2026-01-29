"""
Tests for UI Intent Propagation.

Verifies that user actions result in correct InteractionIntent objects
being emitted via the intent_dispatched signal.
"""

import pytest
import sys
import os
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

# Ensure we import modules the same way the app does (from src root)
if os.path.abspath("src") not in sys.path:
    sys.path.insert(0, os.path.abspath("src"))

from src.ui.components.main_window.main_window import MainWindow
from src.ui.interaction.intents import (
    BeginRecordingIntent,
    StopRecordingIntent,
    CancelRecordingIntent,
    InteractionIntent,
)


@pytest.fixture
def main_window(qtbot):
    """Fixture to provide a MainWindow instance."""
    # We mock history_manager and listener as they are dependencies
    from unittest.mock import MagicMock

    history = MagicMock()
    listener = MagicMock()

    window = MainWindow(history, listener)
    qtbot.addWidget(window)
    return window


class TestIntentPropagation:
    def test_start_recording_emits_intent(self, main_window, qtbot):
        """Verify starting recording emits BeginRecordingIntent."""

        # Verify signal existence
        assert hasattr(main_window, "intent_dispatched")

        # Test 1: Direct dispatch
        with qtbot.waitSignal(main_window.intent_dispatched) as blocker:
            main_window.dispatch_intent(BeginRecordingIntent())

        assert isinstance(blocker.args[0], BeginRecordingIntent)

        # Test 2: Legacy Backward Compatibility (Check that legacy signal ALSO fires)
        with qtbot.waitSignal(main_window.start_recording_requested) as legacy_blocker:
            main_window.dispatch_intent(BeginRecordingIntent())
        assert legacy_blocker.signal_triggered

    def test_stop_start_intent_flow(self, main_window, qtbot):
        """Verify the flow of intents for recording lifecycle."""
        pass
