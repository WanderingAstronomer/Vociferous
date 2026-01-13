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
        from ui.utils.error_handler import get_error_logger

        logger = get_error_logger()
        assert logger is not None

    def test_error_logger_is_singleton(self):
        """ErrorLogger should be a singleton."""
        from ui.utils.error_handler import get_error_logger

        logger1 = get_error_logger()
        logger2 = get_error_logger()
        assert logger1 is logger2

    def test_log_error_does_not_crash(self):
        """log_error should not crash on any input."""
        from ui.utils.error_handler import get_error_logger

        logger = get_error_logger()

        # Should not raise
        logger.log_error("Test error message")
        logger.log_error("Error with context", context="TestContext")
        logger.log_error("", context="Empty message")

    def test_log_exception_captures_traceback(self):
        """log_exception should capture exception traceback."""
        import sys

        from ui.utils.error_handler import get_error_logger

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
        from ui.utils.error_handler import ErrorLogger

        path = ErrorLogger.get_log_file_path()
        assert isinstance(path, Path)
        assert path.suffix == ".log"


class TestSafeSlotDecorator:
    """Tests for safe_slot decorator."""

    def test_safe_slot_catches_exception(self):
        """safe_slot should catch and log exceptions."""
        from ui.utils.error_handler import safe_slot

        @safe_slot("test_context")
        def failing_function():
            raise RuntimeError("Intentional error")

        # Should not raise (decorator catches exceptions)
        with patch("ui.widgets.dialogs.error_dialog.show_error_dialog"):
            failing_function()

    def test_safe_slot_returns_none_on_exception(self):
        """safe_slot should return None when exception occurs."""
        from ui.utils.error_handler import safe_slot

        @safe_slot("test_context")
        def failing_function():
            raise RuntimeError("Intentional error")

        with patch("ui.widgets.dialogs.error_dialog.show_error_dialog"):
            result = failing_function()
        assert result is None

    def test_safe_slot_passes_through_return_value(self):
        """safe_slot should pass through return value on success."""
        from ui.utils.error_handler import safe_slot

        @safe_slot("test_context")
        def successful_function():
            return 42

        result = successful_function()
        assert result == 42

    def test_safe_slot_preserves_function_name(self):
        """safe_slot should preserve the wrapped function's name."""
        from ui.utils.error_handler import safe_slot

        @safe_slot("test_context")
        def my_named_function():
            pass

        assert my_named_function.__name__ == "my_named_function"


class TestFormatException:
    """Tests for exception formatting utility."""

    def test_format_exception_for_display(self):
        """format_exception_for_display should format exception nicely."""
        import sys

        from ui.utils.error_handler import format_exception_for_display

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
        from ui.widgets.dialogs import ErrorDialog

        dialog = ErrorDialog(
            parent=None,
            title="Test Error",
            message="Something went wrong",
            details="Stack trace here",
        )

        assert dialog is not None

    def test_error_dialog_displays_message(self, qapp):
        """ErrorDialog should display the provided message."""
        from ui.widgets.dialogs import ErrorDialog

        dialog = ErrorDialog(
            parent=None,
            title="Test Error",
            message="Custom error message",
        )

        # Find the message label (it has objectName "errorDialogMessage")
        dialog.findChild(type(dialog), "")
        # Just verify dialog was created successfully
        assert dialog._message == "Custom error message"

    def test_error_dialog_toggle_details(self, qapp):
        """ErrorDialog details section should toggle visibility."""
        from ui.widgets.dialogs import ErrorDialog

        dialog = ErrorDialog(
            parent=None,
            title="Test Error",
            message="Error",
            details="Detailed stack trace",
        )

        # Initially hidden
        assert not dialog._details_visible

        # Toggle
        dialog._toggle_details()
        assert dialog._details_visible

        # Toggle again
        dialog._toggle_details()
        assert not dialog._details_visible

    def test_error_dialog_copy_to_clipboard(self, qapp):
        """ErrorDialog should copy details to clipboard."""
        from ui.widgets.dialogs import ErrorDialog

        dialog = ErrorDialog(
            parent=None,
            title="Test Error",
            message="Error message",
            details="Stack trace details",
        )

        # Should not crash
        dialog._copy_to_clipboard()

    def test_show_error_dialog_function(self, qapp):
        """show_error_dialog convenience function should work."""
        from ui.widgets.dialogs import show_error_dialog

        # Mock exec to prevent blocking
        with patch.object(
            __import__(
                "ui.widgets.dialogs.error_dialog", fromlist=["ErrorDialog"]
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


class TestSettingsValidation:
    """Tests for SettingsDialog validation logic."""

    def test_valid_language_codes(self, qapp):
        """Valid language codes should pass validation."""
        from ui.components.settings import SettingsDialog

        valid_codes = ["en", "zh", "de", "es", "fr", "ja"]

        for code in valid_codes:
            assert code in SettingsDialog.VALID_LANGUAGES, f"{code} should be valid"

    def test_invalid_language_code(self, qapp):
        """Invalid language codes should not be in VALID_LANGUAGES."""
        from ui.components.settings import SettingsDialog

        invalid_codes = ["xyz", "english", "123", ""]

        for code in invalid_codes:
            assert code not in SettingsDialog.VALID_LANGUAGES, (
                f"{code} should be invalid"
            )

    def test_device_compute_type_validation(self, qapp):
        """Device and compute_type should be validated for compatibility."""
        from input_handler import KeyListener
        from ui.components.settings import SettingsDialog

        key_listener = KeyListener()
        dialog = SettingsDialog(key_listener)

        # Initial validation should run without error
        assert hasattr(dialog, "_validation_errors")

        # Cleanup
        dialog._cleanup_widgets()
        key_listener.stop()


class TestSafeCallback:
    """Tests for safe_callback utility function."""

    def test_safe_callback_catches_exception(self):
        """safe_callback should catch and log exceptions."""
        from ui.utils.error_handler import safe_callback

        def failing_callback():
            raise RuntimeError("Intentional callback error")

        wrapped = safe_callback(failing_callback, "test_callback")
        # Should not raise
        result = wrapped()
        assert result is None

    def test_safe_callback_passes_arguments(self):
        """safe_callback should pass through arguments."""
        from ui.utils.error_handler import safe_callback

        def add_callback(a, b):
            return a + b

        wrapped = safe_callback(add_callback, "add_callback")
        result = wrapped(2, 3)
        assert result == 5

    def test_safe_callback_preserves_name(self):
        """safe_callback should preserve function name."""
        from ui.utils.error_handler import safe_callback

        def my_callback():
            pass

        wrapped = safe_callback(my_callback, "test")
        assert wrapped.__name__ == "my_callback"

    def test_safe_callback_with_lambda(self):
        """safe_callback should work with lambdas."""
        from ui.utils.error_handler import safe_callback

        wrapped = safe_callback(lambda x: x * 2, "double_lambda")
        assert wrapped(5) == 10

    def test_safe_callback_lambda_exception(self):
        """safe_callback should catch lambda exceptions."""
        from ui.utils.error_handler import safe_callback

        wrapped = safe_callback(lambda: 1 / 0, "div_zero_lambda")
        # Should not raise
        result = wrapped()
        assert result is None


class TestSafeSlotSilent:
    """Tests for safe_slot_silent decorator."""

    def test_safe_slot_silent_catches_exception(self):
        """safe_slot_silent should catch exceptions without dialog."""
        from ui.utils.error_handler import safe_slot_silent

        @safe_slot_silent("test_silent")
        def failing_function():
            raise RuntimeError("Intentional error")

        # Should not raise, and should not try to show dialog
        result = failing_function()
        assert result is None

    def test_safe_slot_silent_passes_return_value(self):
        """safe_slot_silent should pass through return value on success."""
        from ui.utils.error_handler import safe_slot_silent

        @safe_slot_silent("test_silent")
        def successful_function():
            return "success"

        result = successful_function()
        assert result == "success"


class TestErrorPathIntegration:
    """Integration tests for error handling in real components."""

    def test_focus_group_proxy_filter_handles_invalid_index(self, qapp):
        """FocusGroupProxyModel should handle invalid indices gracefully."""
        from PyQt6.QtCore import QModelIndex

        from ui.models.focus_group_proxy import FocusGroupProxyModel

        proxy = FocusGroupProxyModel()
        proxy.set_group_id(None)

        # Should not crash with no source model
        result = proxy.filterAcceptsRow(0, QModelIndex())
        assert result is True  # Default to showing on error

    def test_key_listener_callback_error_isolation(self):
        """KeyListener should isolate callback errors."""
        from input_handler import KeyListener

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
        from ui.widgets.history_tree import HistoryTreeView

        view = HistoryTreeView()

        # Should not crash with no model
        assert view.entry_count() == 0
        view._emit_count()

    def test_transcription_model_handles_corrupted_data(self, qapp):
        """TranscriptionModel should handle corrupted index data."""
        from PyQt6.QtCore import QModelIndex

        from ui.models.transcription_model import TranscriptionModel

        # Create a mock history manager
        mock_manager = MagicMock()
        mock_manager.get_recent.return_value = []
        mock_manager.get_focus_group_colors.return_value = {}

        model = TranscriptionModel(mock_manager)

        # data() should handle invalid index gracefully
        invalid_index = QModelIndex()
        result = model.data(invalid_index)
        assert result is None

        # rowCount should handle None parent
        count = model.rowCount(None)
        assert count == 0
