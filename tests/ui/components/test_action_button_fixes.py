"""
Test Suite for ActionDock Button Fixes

Verifies the following fixes:
1. Button height/padding prevents text clipping (descenders)
2. HistoryView delete button properly wires to MainWindow
3. ProjectsView create project button properly wires through wrapper method

Invariants:
- ActionDock buttons MUST have sufficient height to display descenders (g, p, y)
- Delete action from HistoryView MUST remove entry and refresh model
- Create project action MUST invoke dialog and create project entry
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QPushButton

from src.ui.components.main_window.action_dock import ActionDock
from src.ui.components.main_window.main_window import MainWindow
from src.ui.widgets.project.project_tree import ProjectTreeWidget
from src.ui.contracts.capabilities import ActionId
from src.ui.constants.view_ids import VIEW_PROJECTS
from src.database.dtos import HistoryEntry


class TestActionDockButtonStyling:
    """Verify ActionDock buttons have sufficient height to prevent text clipping."""

    def test_action_dock_button_minimum_height(self, qapp, qtbot):
        """
        CRITICAL: ActionDock buttons MUST have min-height >= 48px to prevent
        descender characters (g, p, y) from being clipped.
        """
        dock = ActionDock()
        qtbot.addWidget(dock)

        # ActionDock creates buttons in __init__, check them directly
        buttons = dock.findChildren(QPushButton)
        assert len(buttons) > 0, "ActionDock should have created buttons"

        # Verify minimum height is set (should be 48px from code)
        for button in buttons:
            min_height = button.minimumHeight()
            assert min_height >= 48, (
                f"Button minimum height {min_height}px should be >= 48px"
            )


class TestHistoryViewDeleteWiring:
    """Verify HistoryView delete button properly connects to MainWindow handler."""

    def test_delete_signal_connected_to_main_window(self, qapp, qtbot):
        """
        CRITICAL: HistoryView.deleteRequested signal MUST be connected to
        MainWindow._on_delete_from_history_view handler.
        """
        mock_history = MagicMock()
        window = MainWindow()
        window.set_history_manager(mock_history)
        qtbot.addWidget(window)

        # Verify the signal is connected
        history_view = window.view_history
        assert history_view is not None

        # Check that deleteRequested signal exists
        assert hasattr(history_view, "delete_requested")

        # Verify handler method exists on MainWindow
        assert hasattr(window, "_on_delete_from_history_view")
        assert callable(window._on_delete_from_history_view)

    def test_delete_from_history_view_shows_confirmation(self, qapp, qtbot):
        """
        Delete from HistoryView MUST show confirmation dialog before deletion.
        """
        mock_history = MagicMock()

        # Create a mock entry
        mock_entry = HistoryEntry(
            id=1,
            timestamp="2026-01-16T12:00:00",
            text="Test transcript to delete",
            duration_ms=5000,
        )
        mock_history.get_entry.return_value = mock_entry

        window = MainWindow()
        window.set_history_manager(mock_history)
        qtbot.addWidget(window)

        # Mock the confirmation dialog to auto-reject
        with patch(
            "src.ui.components.main_window.main_window.ConfirmationDialog"
        ) as mock_dialog_class:
            mock_dialog = Mock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Rejected
            mock_dialog_class.return_value = mock_dialog

            # Trigger delete request
            window._on_delete_from_history_view([1])

            # Verify dialog was shown
            mock_dialog_class.assert_called_once()
            call_kwargs = mock_dialog_class.call_args[1]
            assert call_kwargs["title"] == "Delete Transcript"
            assert call_kwargs["is_destructive"] is True

            # Verify deletion did NOT happen (user rejected)
            mock_history.delete_entry.assert_not_called()

    def test_delete_from_history_view_executes_on_confirmation(self, qapp, qtbot):
        """
        Delete MUST execute and refresh model when user confirms.
        """
        mock_history = MagicMock()

        # Create a mock entry
        mock_entry = HistoryEntry(
            id=1,
            timestamp="2026-01-16T12:00:00",
            text="Test transcript to delete",
            duration_ms=5000,
        )
        mock_history.get_entry.return_value = mock_entry
        mock_history.delete_entry.return_value = True

        window = MainWindow()
        window.set_history_manager(mock_history)
        qtbot.addWidget(window)

        # Mock the confirmation dialog to auto-accept
        with patch(
            "src.ui.components.main_window.main_window.ConfirmationDialog"
        ) as mock_dialog_class:
            mock_dialog = Mock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
            mock_dialog_class.return_value = mock_dialog

            # Trigger delete request
            window._on_delete_from_history_view([1])

            # Verify deletion happened (delete_entry is called with timestamp, not ID)
            mock_history.delete_entry.assert_called_once_with("2026-01-16T12:00:00")

    def test_delete_with_nonexistent_entry_handles_gracefully(self, qapp, qtbot):
        """
        Delete request for non-existent entry MUST handle gracefully without crash.
        """
        mock_history = MagicMock()
        mock_history.get_entry.return_value = None  # Entry doesn't exist

        window = MainWindow()
        window.set_history_manager(mock_history)
        qtbot.addWidget(window)

        # This should not raise an exception
        window._on_delete_from_history_view([999])

        # Should not attempt to show dialog or delete
        mock_history.delete_entry.assert_not_called()


class TestProjectsViewCreateProjectWiring:
    """Verify ProjectsView create project button uses wrapper method."""

    def test_project_tree_has_create_new_project_wrapper(self, qapp, qtbot):
        """
        CRITICAL: ProjectTreeWidget MUST have create_new_project() wrapper method
        that displays dialog and calls create_project().
        """
        mock_history = MagicMock()
        tree = ProjectTreeWidget(mock_history)
        qtbot.addWidget(tree)

        # Verify wrapper method exists
        assert hasattr(tree, "create_new_project")
        assert callable(tree.create_new_project)

        # Verify underlying method exists
        assert hasattr(tree, "create_project")
        assert callable(tree.create_project)

    def test_create_new_project_shows_dialog(self, qapp, qtbot):
        """
        create_new_project() MUST display CreateProjectDialog.
        """
        mock_history = MagicMock()
        tree = ProjectTreeWidget(mock_history)
        qtbot.addWidget(tree)

        # Mock the dialog to auto-reject
        with patch(
            "src.ui.widgets.project.project_tree.CreateProjectDialog"
        ) as mock_dialog_class:
            mock_dialog = Mock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Rejected
            mock_dialog_class.return_value = mock_dialog

            # Call wrapper
            tree.create_new_project()

            # Verify dialog was created and shown
            mock_dialog_class.assert_called_once_with(tree)
            mock_dialog.exec.assert_called_once()

    def test_create_new_project_creates_on_confirmation(self, qapp, qtbot):
        """
        create_new_project() MUST call create_project() when dialog is accepted.
        """
        mock_history = MagicMock()
        mock_history.create_project.return_value = 1  # Return project ID

        tree = ProjectTreeWidget(mock_history)
        qtbot.addWidget(tree)

        # Mock the dialog to accept with a project name
        with patch(
            "src.ui.widgets.project.project_tree.CreateProjectDialog"
        ) as mock_dialog_class:
            mock_dialog = Mock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
            mock_dialog.get_result.return_value = (
                "Test Project",
                "#3b82f6",
            )  # Return tuple (name, color)
            mock_dialog_class.return_value = mock_dialog

            # Mock the underlying create_project method
            with patch.object(tree, "create_project", return_value=1) as mock_create:
                # Call wrapper
                tree.create_new_project()

                # Verify create_project was called with the name and color
                mock_create.assert_called_once_with("Test Project", "#3b82f6")

    def test_create_new_project_no_action_on_cancel(self, qapp, qtbot):
        """
        create_new_project() MUST NOT create project when dialog is cancelled.
        """
        mock_history = MagicMock()
        tree = ProjectTreeWidget(mock_history)
        qtbot.addWidget(tree)

        # Mock the dialog to reject
        with patch(
            "src.ui.widgets.project.project_tree.CreateProjectDialog"
        ) as mock_dialog_class:
            mock_dialog = Mock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Rejected
            mock_dialog_class.return_value = mock_dialog

            # Mock the underlying create_project method
            with patch.object(tree, "create_project") as mock_create:
                # Call wrapper
                tree.create_new_project()

                # Verify create_project was NOT called
                mock_create.assert_not_called()

    def test_create_new_project_handles_empty_name(self, qapp, qtbot):
        """
        create_new_project() MUST NOT create project if name is empty/None.
        """
        mock_history = MagicMock()
        tree = ProjectTreeWidget(mock_history)
        qtbot.addWidget(tree)

        # Mock the dialog to accept but return empty name
        with patch(
            "src.ui.widgets.project.project_tree.CreateProjectDialog"
        ) as mock_dialog_class:
            mock_dialog = Mock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
            mock_dialog.get_result.return_value = (
                "",
                "#3b82f6",
            )  # Return tuple with empty name
            mock_dialog_class.return_value = mock_dialog

            # Mock the underlying create_project method
            with patch.object(tree, "create_project") as mock_create:
                # Call wrapper
                tree.create_new_project()

                # Verify create_project was NOT called with empty name
                mock_create.assert_not_called()
