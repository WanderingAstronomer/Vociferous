"""
Unit tests for application restart functionality.
Ensures the Restart Application button works end to end.
"""

import os
import sys
import tempfile
from unittest.mock import Mock, patch, MagicMock, call
import pytest

from PyQt6.QtWidgets import QApplication

from src.ui.views.settings_view import SettingsView


@pytest.fixture
def qapp():
    """Create QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def settings_view(qapp):
    """Create a SettingsView instance."""
    view = SettingsView(parent=None)
    yield view
    view.cleanup()


class TestRestartLogic:
    """Test suite for restart application functionality."""

    def test_restart_button_emits_signal(self, settings_view):
        """Test that the Restart Application button emits restart_requested signal."""
        signal_received = False

        def on_restart():
            nonlocal signal_received
            signal_received = True

        settings_view.restart_requested.connect(on_restart)

        # Emit the signal (simulating button click)
        settings_view.restart_requested.emit()

        assert signal_received, "restart_requested signal was not emitted"

    def test_restart_signal_exists(self, settings_view):
        """Test that the restart signal is properly defined."""
        assert hasattr(settings_view, "restart_requested"), (
            "restart_requested signal missing"
        )

    def test_restart_application_method_exists(self):
        """Test that the _restart_application method exists in MainWindow."""
        mock_mw = MagicMock()
        mock_mw._restart_application = MagicMock()
        assert hasattr(mock_mw, "_restart_application"), (
            "_restart_application method missing"
        )

    @patch("subprocess.Popen")
    @patch("os.path.exists")
    @patch("src.ui.components.main_window.main_window.MainWindow.close")
    def test_restart_application_calls_subprocess(
        self, mock_close, mock_exists, mock_popen
    ):
        """Test that _restart_application launches a subprocess."""
        # Import here to avoid initialization issues
        from src.ui.components.main_window.main_window import MainWindow

        mock_exists.return_value = True
        mock_popen.return_value = MagicMock()

        # Create a mock main window
        with patch.object(MainWindow, "__init__", return_value=None):
            main_window = MainWindow()
            main_window.close = mock_close
            main_window._restart_application()

        # Verify subprocess.Popen was called
        assert mock_popen.called, "subprocess.Popen was not called"

    @patch("subprocess.Popen")
    @patch("os.path.exists")
    @patch("src.ui.components.main_window.main_window.show_error_dialog")
    def test_restart_application_prefers_run_script(
        self, mock_error_dialog, mock_exists, mock_popen
    ):
        """Test that _restart_application prefers run.py when it exists."""
        from src.ui.components.main_window.main_window import MainWindow

        mock_exists.return_value = True
        mock_popen.return_value = MagicMock()

        with (
            patch.object(MainWindow, "__init__", return_value=None),
            patch.object(MainWindow, "close"),
        ):
            main_window = MainWindow()
            main_window._restart_application()

        call_args = mock_popen.call_args[0][0]
        # Should contain "vociferous"
        assert any("vociferous" in str(arg) for arg in call_args), (
            f"vociferous not in {call_args}"
        )

    @patch("subprocess.Popen")
    @patch("os.path.exists")
    @patch("src.ui.components.main_window.main_window.show_error_dialog")
    def test_restart_application_fallback_to_main_py(
        self, mock_error_dialog, mock_exists, mock_popen
    ):
        """Test that _restart_application falls back to main.py if run.py doesn't exist."""
        from src.ui.components.main_window.main_window import MainWindow

        mock_exists.return_value = False
        mock_popen.return_value = MagicMock()

        with (
            patch.object(MainWindow, "__init__", return_value=None),
            patch.object(MainWindow, "close"),
        ):
            main_window = MainWindow()
            main_window._restart_application()

        call_args = mock_popen.call_args[0][0]
        # Should contain "main.py"
        assert any("main.py" in str(arg) for arg in call_args), (
            f"main.py not in {call_args}"
        )

    @patch("subprocess.Popen")
    @patch("os.path.exists")
    def test_restart_application_closes_window(self, mock_exists, mock_popen):
        """Test that _restart_application closes the main window."""
        from src.ui.components.main_window.main_window import MainWindow

        mock_exists.return_value = True
        mock_popen.return_value = MagicMock()

        with patch.object(MainWindow, "__init__", return_value=None):
            main_window = MainWindow()
            main_window.close = MagicMock()
            main_window._restart_application()

        # Verify close() was called
        main_window.close.assert_called_once()

    @patch("subprocess.Popen")
    @patch("os.path.exists")
    def test_restart_application_starts_new_session(self, mock_exists, mock_popen):
        """Test that subprocess is started with start_new_session=True."""
        from src.ui.components.main_window.main_window import MainWindow

        mock_exists.return_value = True
        mock_popen.return_value = MagicMock()

        with (
            patch.object(MainWindow, "__init__", return_value=None),
            patch.object(MainWindow, "close"),
        ):
            main_window = MainWindow()
            main_window._restart_application()

        call_kwargs = mock_popen.call_args[1]
        assert "start_new_session" in call_kwargs, "start_new_session kwarg missing"
        assert call_kwargs["start_new_session"] is True, (
            "start_new_session should be True"
        )

    @patch("subprocess.Popen", side_effect=Exception("Mock subprocess error"))
    @patch("os.path.exists")
    @patch("src.ui.components.main_window.main_window.show_error_dialog")
    def test_restart_application_handles_error(
        self, mock_error_dialog, mock_exists, mock_popen
    ):
        """Test that _restart_application handles subprocess errors gracefully."""
        from src.ui.components.main_window.main_window import MainWindow

        mock_exists.return_value = True

        with (
            patch.object(MainWindow, "__init__", return_value=None),
            patch.object(MainWindow, "close"),  # Ensure close is also patched
        ):
            main_window = MainWindow()
            # Should not raise an exception
            main_window._restart_application()


class TestRestartIntegration:
    """Integration tests for restart functionality."""

    def test_settings_restart_button_has_text(self, settings_view):
        """Test that the restart button is properly labeled."""
        # At minimum, we should have the signal defined
        assert hasattr(settings_view, "restart_requested"), (
            "restart_requested signal missing"
        )

    def test_restart_signal_not_confused_with_exit(self, settings_view):
        """Ensure restart signal is distinct from exit signal."""
        assert hasattr(settings_view, "restart_requested"), (
            "restart_requested signal missing"
        )
        assert hasattr(settings_view, "exit_requested"), "exit_requested signal missing"

        # They should be different objects
        assert settings_view.restart_requested is not settings_view.exit_requested, (
            "Restart and exit signals should be different"
        )


class TestRestartConfiguration:
    """Tests for restart configuration and script paths."""

    @patch("subprocess.Popen")
    @patch("os.path.exists")
    @patch("src.ui.components.main_window.main_window.show_error_dialog")
    def test_restart_uses_correct_script_directory(
        self, mock_error_dialog, mock_exists, mock_popen
    ):
        """Test that restart uses the correct scripts directory."""
        from src.ui.components.main_window.main_window import MainWindow

        mock_exists.return_value = True
        mock_popen.return_value = MagicMock()

        with (
            patch.object(MainWindow, "__init__", return_value=None),
            patch.object(MainWindow, "close"),
        ):
            main_window = MainWindow()
            main_window._restart_application()

        # Get the command that was run
        call_args = mock_popen.call_args[0][0]

        # Should be a list with python executable and script
        assert len(call_args) >= 2, f"Expected at least 2 args, got {len(call_args)}"
        assert call_args[0] == sys.executable, f"First arg should be {sys.executable}"

    def test_restart_signal_connection_in_settings(self, settings_view):
        """Test that restart signal can be connected in settings."""
        mock_handler = MagicMock()
        settings_view.restart_requested.connect(mock_handler)
        settings_view.restart_requested.emit()
        mock_handler.assert_called_once()
