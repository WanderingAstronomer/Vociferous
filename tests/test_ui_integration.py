"""
Integration tests for UI interactions.

These tests verify the actual UI flow including button clicks and signal emissions.
"""

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from ui.components.workspace import MainWorkspace
from ui.constants import WorkspaceState


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for Qt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_start_button_emits_signal(qapp):
    """Test that clicking Start button emits startRequested signal."""
    workspace = MainWorkspace()

    # Track signal emission
    signal_emitted = []
    workspace.startRequested.connect(lambda: signal_emitted.append(True))

    # Simulate button click (controls is the WorkspaceControls component)
    workspace.controls.primary_btn.click()

    # Process events to ensure signals are delivered
    qapp.processEvents()

    assert len(signal_emitted) == 1, "startRequested signal should be emitted once"
    assert workspace.get_state() == WorkspaceState.RECORDING


def test_stop_button_emits_signal(qapp):
    """Test that clicking Stop button emits stopRequested signal."""
    workspace = MainWorkspace()

    # Start recording first
    workspace.set_state(WorkspaceState.RECORDING)

    # Track signal emission
    signal_emitted = []
    workspace.stopRequested.connect(lambda: signal_emitted.append(True))

    # Simulate button click
    workspace.controls.primary_btn.click()

    # Process events
    qapp.processEvents()

    assert len(signal_emitted) == 1, "stopRequested signal should be emitted once"


def test_state_transition_sequence(qapp):
    """Test the full state transition sequence."""
    workspace = MainWorkspace()

    # Start in IDLE
    assert workspace.get_state() == WorkspaceState.IDLE

    # Click Start -> should go to RECORDING
    workspace.controls.primary_btn.click()
    qapp.processEvents()
    assert workspace.get_state() == WorkspaceState.RECORDING

    # Manually transition to transcribing (simulating backend)
    workspace.show_transcribing_status()
    qapp.processEvents()
    assert workspace.get_state() == WorkspaceState.RECORDING  # Still in recording state

    # Cleanup
    workspace.set_state(WorkspaceState.IDLE)


def test_double_start_button_click(qapp):
    """Test that double-clicking Start behaves correctly (first=start, second=stop)."""
    workspace = MainWorkspace()

    start_count = []
    stop_count = []
    workspace.startRequested.connect(lambda: start_count.append(True))
    workspace.stopRequested.connect(lambda: stop_count.append(True))

    # Click Start (should emit startRequested and change to RECORDING state)
    workspace.controls.primary_btn.click()
    qapp.processEvents()
    assert len(start_count) == 1, "First click should emit startRequested"
    assert workspace.get_state() == WorkspaceState.RECORDING

    # Click again while in RECORDING state (should emit stopRequested)
    workspace.controls.primary_btn.click()
    qapp.processEvents()
    assert len(stop_count) == 1, (
        "Second click should emit stopRequested (acts as Stop button)"
    )


def test_workspace_with_timeout(qapp):
    """Test that workspace operations complete without hanging."""
    workspace = MainWorkspace()

    # Set a timeout to prevent test from hanging forever
    timeout_triggered = [False]

    def timeout():
        timeout_triggered[0] = True
        qapp.quit()

    QTimer.singleShot(2000, timeout)  # 2 second timeout

    # Perform operations
    workspace.controls.primary_btn.click()
    qapp.processEvents()

    # If we get here without hanging, test passes
    assert not timeout_triggered[0], "Operation should not timeout"
