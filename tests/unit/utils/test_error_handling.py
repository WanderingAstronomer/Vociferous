"""
Tests for error handling infrastructure.

Validates:
- ErrorLogger singleton and log file creation
- safe_slot decorator for error catching
- ErrorDialog creation and functionality
- Settings validation logic

Test Tier: UI-Dependent (Tier 2)
- Requires QApplication for ErrorDialog widget tests
- May fail with SIGABRT in headless environments
- Run with: pytest -m "ui_dependent"
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QApplication

# Mark entire module as UI-dependent
pytestmark = pytest.mark.ui_dependent


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for Qt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestErrorLogger:
    """Tests for ErrorLogger singleton."""

    def test_get_error_logger_returns_instance(self):
        """get_error_logger should return an ErrorLogger instance."""
        from src.ui.utils.error_handler import get_error_logger

        logger = get_error_logger()
        assert logger is not None

    def test_error_logger_is_singleton(self):
        """ErrorLogger should be a singleton."""
        from src.ui.utils.error_handler import get_error_logger

        logger1 = get_error_logger()
        logger2 = get_error_logger()
        assert logger1 is logger2

    def test_log_error_does_not_crash(self):
        """log_error should not crash on any input."""
        from src.ui.utils.error_handler import get_error_logger

        logger = get_error_logger()

        # Should not raise
        logger.log_error("Test error message")
        logger.log_error("Error with context", context="TestContext")
        logger.log_error("", context="Empty message")

    def test_log_exception_captures_traceback(self):
        """log_exception should capture exception traceback."""
        import sys

        from src.ui.utils.error_handler import get_error_logger

        logger = get_error_logger()

        try:
            raise ValueError("Test exception")
        except ValueError:
            exc_type, exc_value, exc_tb = sys.exc_info()
            # Should not raise
            tb_string = logger.log_exception(exc_type, exc_value, exc_tb)
            assert "ValueError" in tb_string
            assert "Test exception" in tb_string

    def test_get_log_path_returns_path(self):
        """get_log_file_path should return a Path object."""
        from src.ui.utils.error_handler import ErrorLogger

        path = ErrorLogger.get_log_file_path()
        assert isinstance(path, Path)
        assert path.suffix == ".log"


class TestSafeSlotDecorator:
    """Tests for safe_slot decorator."""

    def test_safe_slot_catches_exception(self):
        """safe_slot should catch and log exceptions."""
        from src.ui.utils.error_handler import safe_slot

        @safe_slot("test_context")
        def failing_function():
            raise RuntimeError("Intentional error")

        # Should not raise (decorator catches exceptions)
        with patch("src.ui.widgets.dialogs.error_dialog.show_error_dialog"):
            failing_function()

    def test_safe_slot_returns_none_on_exception(self):
        """safe_slot should return None when exception occurs."""
        from src.ui.utils.error_handler import safe_slot

        @safe_slot("test_context")
        def failing_function():
            raise RuntimeError("Intentional error")

        with patch("src.ui.widgets.dialogs.error_dialog.show_error_dialog"):
            result = failing_function()
        assert result is None

    def test_safe_slot_passes_through_return_value(self):
        """safe_slot should pass through return value on success."""
        from src.ui.utils.error_handler import safe_slot

        @safe_slot("test_context")
        def successful_function():
            return 42

        result = successful_function()
        assert result == 42

    def test_safe_slot_preserves_function_name(self):
        """safe_slot should preserve the wrapped function's name."""
        from src.ui.utils.error_handler import safe_slot

        @safe_slot("test_context")
        def my_named_function():
            pass

        assert my_named_function.__name__ == "my_named_function"


class TestFormatException:
    """Tests for exception formatting utility."""

    def test_format_exception_for_display(self):
        """format_exception_for_display should format exception nicely."""
        import sys

        from src.ui.utils.error_handler import format_exception_for_display

        try:
            raise ValueError("Test error")
        except ValueError:
            exc_type, exc_value, exc_tb = sys.exc_info()
            title, message, details = format_exception_for_display(
                exc_type, exc_value, exc_tb
            )

        assert "ValueError" in title
        assert "Test error" in message
        assert "Traceback" in details


class TestErrorDialog:
    """Tests for ErrorDialog widget."""

    def test_error_dialog_creation(self, qapp):
        """ErrorDialog should be creatable."""
        from src.ui.widgets.dialogs.error_dialog import ErrorDialog

        dialog = ErrorDialog(
            parent=None,
            title="Test Error",
            message="Something went wrong",
            details="Stack trace here",
        )

        assert dialog is not None

    def test_error_dialog_displays_message(self, qapp):
        """ErrorDialog should display the provided message."""
        from src.ui.widgets.dialogs.error_dialog import ErrorDialog
        from PyQt6.QtWidgets import QLabel

        dialog = ErrorDialog(
            parent=None,
            title="Test Error",
            message="Custom error message",
        )

        # Find the message label (it has objectName "errorDialogMessage")
        message_label = dialog.findChild(QLabel, "errorDialogMessage")
        assert message_label is not None
        assert message_label.text() == "Custom error message"

    def test_error_dialog_toggle_details(self, qapp):
        """ErrorDialog details section should toggle visibility."""
        from src.ui.widgets.dialogs.error_dialog import ErrorDialog
        from PyQt6.QtWidgets import QPushButton

        dialog = ErrorDialog(
            parent=None,
            title="Test Error",
            message="Error",
            details="Detailed stack trace",
        )
        dialog.show()  # Ensure widget is considered visible for child visibility checks

        # Initially hidden
        assert not dialog.details_container.isVisible()

        # Toggle via button click
        toggle_btn = dialog.findChild(QPushButton, "errorDialogToggle")
        assert toggle_btn is not None
        toggle_btn.click()
        assert dialog.details_container.isVisible()

        # Toggle again
        toggle_btn.click()
        assert not dialog.details_container.isVisible()

    def test_error_dialog_copy_to_clipboard(self, qapp):
        """ErrorDialog should copy details to clipboard."""
        from src.ui.widgets.dialogs.error_dialog import ErrorDialog
        from PyQt6.QtWidgets import QPushButton

        dialog = ErrorDialog(
            parent=None,
            title="Test Error",
            message="Error message",
            details="Stack trace details",
        )

        # Should not crash when clicked
        copy_btn = dialog.findChild(QPushButton, "errorDialogCopy")
        if copy_btn:  # might be None if no details? But we provided details.
            copy_btn.click()
        else:
            # If details present, button should be there
            assert False, "Copy button not found"

    def test_show_error_dialog_function(self, qapp):
        """show_error_dialog convenience function should work."""
        from src.ui.widgets.dialogs.error_dialog import show_error_dialog

        # Mock exec to prevent blocking
        with patch.object(
            __import__(
                "src.ui.widgets.dialogs.error_dialog", fromlist=["ErrorDialog"]
            ).ErrorDialog,
            "exec",
            return_value=None,
        ):
            # Should not crash
            show_error_dialog(
                title="Test",
                message="Test message",
                parent=None,
            )


class TestSafeCallback:
    """Tests for safe_callback utility function."""

    def test_safe_callback_catches_exception(self):
        """safe_callback should catch and log exceptions."""
        from src.ui.utils.error_handler import safe_callback

        def failing_callback():
            raise RuntimeError("Intentional callback error")

        wrapped = safe_callback(failing_callback, "test_callback")
        # Should not raise
        result = wrapped()
        assert result is None

    def test_safe_callback_passes_arguments(self):
        """safe_callback should pass through arguments."""
        from src.ui.utils.error_handler import safe_callback

        def add_callback(a, b):
            return a + b

        wrapped = safe_callback(add_callback, "add_callback")
        result = wrapped(2, 3)
        assert result == 5

    def test_safe_callback_preserves_name(self):
        """safe_callback should preserve function name."""
        from src.ui.utils.error_handler import safe_callback

        def my_callback():
            pass

        wrapped = safe_callback(my_callback, "test")
        assert wrapped.__name__ == "my_callback"

    def test_safe_callback_with_lambda(self):
        """safe_callback should work with lambdas."""
        from src.ui.utils.error_handler import safe_callback

        wrapped = safe_callback(lambda x: x * 2, "double_lambda")
        assert wrapped(5) == 10

    def test_safe_callback_lambda_exception(self):
        """safe_callback should catch lambda exceptions."""
        from src.ui.utils.error_handler import safe_callback

        wrapped = safe_callback(lambda: 1 / 0, "div_zero_lambda")
        # Should not raise
        result = wrapped()
        assert result is None


class TestSafeSlotSilent:
    """Tests for safe_slot_silent decorator."""

    def test_safe_slot_silent_catches_exception(self):
        """safe_slot_silent should catch exceptions without dialog."""
        from src.ui.utils.error_handler import safe_slot_silent

        @safe_slot_silent("test_silent")
        def failing_function():
            raise RuntimeError("Intentional error")

        # Should not raise, and should not try to show dialog
        result = failing_function()
        assert result is None

    def test_safe_slot_silent_passes_return_value(self):
        """safe_slot_silent should pass through return value on success."""
        from src.ui.utils.error_handler import safe_slot_silent

        @safe_slot_silent("test_silent")
        def successful_function():
            return "success"

        result = successful_function()
        assert result == "success"


class TestErrorPathIntegration:
    """Integration tests for error handling in real components."""

    def test_project_proxy_filter_handles_invalid_index(self, qapp):
        """ProjectProxyModel should handle invalid indices gracefully."""
        from PyQt6.QtCore import QModelIndex

        from src.ui.models.project_proxy import ProjectProxyModel

        proxy = ProjectProxyModel()
        proxy.set_project_id(None)

        # Should not crash with no source model
        result = proxy.filterAcceptsRow(0, QModelIndex())
        assert result is True  # Default to showing on error

    def test_key_listener_callback_error_isolation(self):
        """KeyListener should isolate callback errors."""
        from src.input_handler.listener import KeyListener

        listener = KeyListener()

        error_raised = []

        def failing_callback():
            error_raised.append(True)
            raise RuntimeError("Callback error")

        def success_callback():
            error_raised.append(False)

        listener.add_callback("on_activate", failing_callback)
        listener.add_callback("on_activate", success_callback)

        # Should not crash, and should continue to second callback
        listener._trigger_callbacks("on_activate")

        # Both callbacks should have been attempted
        assert len(error_raised) == 2
        assert error_raised[0] is True  # First one raised
        assert error_raised[1] is False  # Second one succeeded

        listener.stop()

    def test_history_tree_view_handles_invalid_model(self, qapp):
        """HistoryTreeView should handle operations with no model."""
        from src.ui.widgets.history_tree.history_tree_view import HistoryTreeView

        view = HistoryTreeView()

        # Should not crash with no model
        assert view.entry_count() == 0
        view._emit_count()

    def test_transcription_model_handles_corrupted_data(self, qapp):
        """TranscriptionModel should handle corrupted index data."""
        from PyQt6.QtCore import QModelIndex

        from src.ui.models.transcription_model import TranscriptionModel

        # Create a mock history manager
        mock_manager = MagicMock()
        mock_manager.get_recent.return_value = []
        mock_manager.get_project_colors.return_value = {}

        model = TranscriptionModel(mock_manager)

        # data() should handle invalid index gracefully
        invalid_index = QModelIndex()
        result = model.data(invalid_index)
        assert result is None

        # rowCount should handle None parent
        count = model.rowCount(None)
        assert count == 0
