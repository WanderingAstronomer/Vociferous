import pytest
from unittest.mock import MagicMock
from PyQt6.QtCore import QObject

from src.core.command_bus import CommandBus
from src.core.intents import InteractionIntent
from src.ui.interaction.intents import BeginRecordingIntent, ToggleRecordingIntent


def test_bus_dispatch_emits_signal(qtbot):
    """Verify CommandBus emits signal on dispatch."""
    bus = CommandBus()

    with qtbot.waitSignal(bus.intent_dispatched, timeout=1000) as blocker:
        intent = BeginRecordingIntent()
        bus.dispatch(intent)

    assert blocker.args[0] == intent


def test_bus_handler_execution():
    """Verify registered handlers are executed."""
    bus = CommandBus()
    handler_mock = MagicMock()

    bus.register_handler(ToggleRecordingIntent, handler_mock)

    intent = ToggleRecordingIntent()
    bus.dispatch(intent)

    handler_mock.assert_called_once_with(intent)


def test_coordinator_integration_stub(qtbot):
    """
    Verify Coordinator logic (stubbed) reacts to Bus.
    We mock the ApplicationCoordinator's minimal surface.
    """
    from src.core.application_coordinator import ApplicationCoordinator

    # We can't easily instantiate full Coordinator without full mocks (app, etc).
    # But we can test the wiring logic concept.

    bus = CommandBus()
    recipient = MagicMock()

    # Simulate Coordinator._on_intent
    bus.intent_dispatched.connect(recipient)

    intent = ToggleRecordingIntent()
    bus.dispatch(intent)

    recipient.assert_called_once_with(intent)
