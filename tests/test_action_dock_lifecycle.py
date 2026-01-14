"""
Test ActionDock Lifecycle and Initialization

Invariants:
1. ActionDock MUST sync with default view on application boot
2. ActionDock buttons MUST appear immediately when app starts
3. ActionDock MUST update correctly on every view switch
4. Rapid view switching MUST maintain button consistency
"""

from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QApplication

from ui.components.action_dock import ActionDock
from ui.components.main_window.main_window import MainWindow
from ui.constants import WorkspaceState


class TestActionDockBootInitialization:
    """
    Critical Invariant: ActionDock buttons MUST be visible on application boot.
    
    Current Bug: TranscribeView is set as default but doesn't trigger view-change
    signal, so ActionDock never syncs with initial capabilities.
    
    Expected: ActionDock should show "Start Recording" button immediately on boot
    when TranscribeView is the default view in IDLE state.
    """
    
    def test_action_dock_syncs_on_boot(self, qapp, qtbot):
        """
        CRITICAL: ActionDock MUST display buttons for default view on boot.
        
        This test enforces that when MainWindow initializes with TranscribeView
        as the default view, the ActionDock immediately shows the appropriate
        buttons (e.g., "Start Recording" in IDLE state).
        """
        # Create MainWindow (which sets TranscribeView as default)
        mock_history = MagicMock()
        window = MainWindow()
        window.set_history_manager(mock_history)
        qtbot.addWidget(window)
        window.show()
        
        # Force event processing to ensure all initialization completes
        qtbot.waitExposed(window)
        QApplication.processEvents()
        
        # Verify ActionDock exists
        action_dock = window.action_dock
        assert action_dock is not None, "ActionDock not created"
        
        # Verify ActionDock has synced with default view
        # TranscribeView in IDLE state should show "Start Recording"
        start_recording_btn = action_dock.get_button("START_RECORDING")
        assert start_recording_btn is not None, "Start Recording button not found"
        assert start_recording_btn.isVisible(), \
            "Start Recording button not visible on boot (ActionDock not synced with default view)"
        
        # Verify no inappropriate buttons are visible in IDLE state
        stop_recording_btn = action_dock.get_button("STOP_RECORDING")
        assert not stop_recording_btn.isVisible(), \
            "Stop Recording button should not be visible in IDLE state"
        
        edit_btn = action_dock.get_button("EDIT")
        assert not edit_btn.isVisible(), \
            "Edit button should not be visible in IDLE state (no transcript)"
        
        window.close()
    
    def test_action_dock_updates_on_view_switch(self, qapp, qtbot):
        """
        ActionDock MUST update button visibility when switching views.
        
        Verifies that navigating from TranscribeView to HistoryView updates
        the ActionDock to show HistoryView's capabilities.
        """
        from ui.interaction.intents import NavigateIntent
        
        mock_history = MagicMock()
        window = MainWindow()
        window.set_history_manager(mock_history)
        qtbot.addWidget(window)
        window.show()
        qtbot.waitExposed(window)
        
        action_dock = window.action_dock
        
        # Initial state: TranscribeView IDLE shows "Start Recording"
        start_btn = action_dock.get_button("START_RECORDING")
        assert start_btn.isVisible(), "Start Recording not visible in TranscribeView IDLE"
        
        # Switch to HistoryView
        navigate_intent = NavigateIntent(target_view_id="history")
        window._on_interaction_intent(navigate_intent)
        QApplication.processEvents()
        
        # Verify ActionDock updated for HistoryView
        # HistoryView doesn't have recording capabilities
        assert not start_btn.isVisible(), \
            "Start Recording button should not be visible in HistoryView"
        
        # HistoryView might have different buttons (create project, etc.)
        # The key is that the buttons changed from TranscribeView
        
        # Switch back to TranscribeView
        navigate_back = NavigateIntent(target_view_id="transcribe")
        window._on_interaction_intent(navigate_back)
        QApplication.processEvents()
        
        # Verify buttons restored
        assert start_btn.isVisible(), \
            "Start Recording button should reappear when returning to TranscribeView"
        
        window.close()
    
    def test_rapid_view_switching_maintains_consistency(self, qapp, qtbot):
        """
        Rapid view switching MUST not leave ActionDock in stale state.
        
        Tests that switching views quickly doesn't cause button sync issues.
        """
        from ui.interaction.intents import NavigateIntent
        
        mock_history = MagicMock()
        window = MainWindow()
        window.set_history_manager(mock_history)
        qtbot.addWidget(window)
        window.show()
        qtbot.waitExposed(window)
        
        action_dock = window.action_dock
        view_host = window.view_host
        
        # Rapidly switch between views
        views = ["history", "settings", "transcribe", "projects", "transcribe"]
        for view_id in views:
            intent = NavigateIntent(target_view_id=view_id)
            window._on_interaction_intent(intent)
            QApplication.processEvents()
        
        # Final view is TranscribeView - verify correct buttons
        assert view_host.get_current_view_id() == "transcribe"
        
        start_btn = action_dock.get_button("START_RECORDING")
        assert start_btn.isVisible(), \
            "ActionDock lost sync during rapid view switching"
        
        window.close()


class TestActionDockStateTransitions:
    """
    ActionDock MUST update when workspace state changes within a view.
    
    Tests that state transitions (IDLE→RECORDING→VIEWING→EDITING) correctly
    update button visibility without requiring a view switch.
    """
    
    def test_action_dock_updates_on_state_change(self, qapp, qtbot):
        """
        ActionDock MUST respond to capabilities_changed signal from active view.
        
        When TranscribeView transitions from IDLE to RECORDING, ActionDock
        must update button visibility immediately.
        """
        mock_history = MagicMock()
        window = MainWindow()
        window.set_history_manager(mock_history)
        qtbot.addWidget(window)
        window.show()
        qtbot.waitExposed(window)
        
        action_dock = window.action_dock
        transcribe_view = window.view_transcribe
        
        # IDLE state: Start Recording visible
        start_btn = action_dock.get_button("START_RECORDING")
        stop_btn = action_dock.get_button("STOP_RECORDING")
        cancel_btn = action_dock.get_button("CANCEL")
        
        assert start_btn.isVisible(), "Start button not visible in IDLE"
        assert not stop_btn.isVisible(), "Stop button visible in IDLE (wrong)"
        assert not cancel_btn.isVisible(), "Cancel button visible in IDLE (wrong)"
        
        # Transition to RECORDING by directly calling the workspace
        # (In real app, this happens via ActionDock button or hotkey)
        transcribe_view.workspace.set_state(WorkspaceState.RECORDING)
        QApplication.processEvents()
        
        # Verify buttons updated for RECORDING state
        assert not start_btn.isVisible(), \
            "Start Recording button still visible during recording"
        assert stop_btn.isVisible(), \
            "Stop Recording button not visible during recording"
        assert cancel_btn.isVisible(), \
            "Cancel button not visible during recording"
        
        window.close()
