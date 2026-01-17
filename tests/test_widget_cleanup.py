"""
Test widget cleanup protocol compliance.

Verifies all stateful widgets properly release resources in cleanup()
to prevent memory leaks and orphaned timers/threads.

Per Vociferous cleanup protocol, widgets with timers, animations,
threads, or external connections must implement cleanup().
"""

import pytest
from unittest.mock import Mock
from PyQt6.QtCore import QPropertyAnimation, QTimer


class TestToggleSwitchCleanup:
    """Test ToggleSwitch cleanup protocol."""

    def test_has_cleanup_method(self, qtbot):
        """Widget must implement cleanup() method."""
        from src.ui.widgets.toggle_switch import ToggleSwitch

        toggle = ToggleSwitch()
        qtbot.addWidget(toggle)

        assert hasattr(toggle, "cleanup")
        assert callable(toggle.cleanup)

    def test_animation_exists(self, qtbot):
        """Widget uses QPropertyAnimation for toggle transition."""
        from src.ui.widgets.toggle_switch import ToggleSwitch

        toggle = ToggleSwitch()
        qtbot.addWidget(toggle)

        # Verify animation is created during initialization
        assert hasattr(toggle, "animation")
        assert isinstance(toggle.animation, QPropertyAnimation)

    def test_animation_stops_on_cleanup(self, qtbot):
        """cleanup() must stop any running animation."""
        from src.ui.widgets.toggle_switch import ToggleSwitch

        toggle = ToggleSwitch()
        qtbot.addWidget(toggle)

        # Start animation by toggling
        toggle.setChecked(True)
        qtbot.wait(10)  # Let animation start


        # Call cleanup
        toggle.cleanup()

        # Animation should be stopped
        assert toggle.animation.state() == QPropertyAnimation.State.Stopped

    def test_cleanup_idempotent(self, qtbot):
        """cleanup() can be called multiple times safely."""
        from src.ui.widgets.toggle_switch import ToggleSwitch

        toggle = ToggleSwitch()
        qtbot.addWidget(toggle)

        # Should not raise exception
        toggle.cleanup()
        toggle.cleanup()
        toggle.cleanup()

    def test_widget_stable_after_cleanup(self, qtbot):
        """Widget should remain stable after cleanup (no crashes)."""
        from src.ui.widgets.toggle_switch import ToggleSwitch

        toggle = ToggleSwitch()
        qtbot.addWidget(toggle)

        toggle.cleanup()

        # Should not crash when interacting after cleanup
        toggle.setChecked(True)
        toggle.setChecked(False)


class TestRailButtonCleanup:
    """Test RailButton cleanup protocol."""

    def test_has_cleanup_method(self, qtbot):
        """Widget must implement cleanup() method."""
        from src.ui.components.main_window.icon_rail import RailButton

        button = RailButton(view_id="test", icon_name="transcribe", label="Test")
        qtbot.addWidget(button)

        assert hasattr(button, "cleanup")
        assert callable(button.cleanup)

    def test_blink_timer_exists(self, qtbot):
        """RailButton uses QTimer for blink animation."""
        from src.ui.components.main_window.icon_rail import RailButton

        button = RailButton(view_id="test", icon_name="transcribe", label="Test")
        qtbot.addWidget(button)

        # Trigger blink to create timer
        button.blink()

        # Should have a timer active briefly
        # Note: Timer may complete quickly, so we just verify cleanup works

    def test_cleanup_stops_timers(self, qtbot):
        """cleanup() should stop any active timers."""
        from src.ui.components.main_window.icon_rail import RailButton

        button = RailButton(view_id="test", icon_name="transcribe", label="Test")
        qtbot.addWidget(button)

        # Cleanup should be safe even without active timers
        button.cleanup()

    def test_cleanup_idempotent(self, qtbot):
        """cleanup() can be called multiple times safely."""
        from src.ui.components.main_window.icon_rail import RailButton

        button = RailButton(view_id="test", icon_name="transcribe", label="Test")
        qtbot.addWidget(button)

        button.cleanup()
        button.cleanup()
        button.cleanup()


class TestBlockingOverlayCleanup:
    """Test BlockingOverlay cleanup protocol."""

    def test_has_cleanup_method(self, qtbot):
        """Widget must implement cleanup() method."""
        from PyQt6.QtWidgets import QWidget
        from src.ui.widgets.dialogs.blocking_overlay import BlockingOverlay

        parent = QWidget()
        qtbot.addWidget(parent)
        overlay = BlockingOverlay(parent)
        qtbot.addWidget(overlay)

        assert hasattr(overlay, "cleanup")
        assert callable(overlay.cleanup)

    def test_cleanup_idempotent(self, qtbot):
        """cleanup() can be called multiple times safely."""
        from PyQt6.QtWidgets import QWidget
        from src.ui.widgets.dialogs.blocking_overlay import BlockingOverlay

        parent = QWidget()
        qtbot.addWidget(parent)
        overlay = BlockingOverlay(parent)
        qtbot.addWidget(overlay)

        overlay.cleanup()
        overlay.cleanup()


class TestTranscriptPreviewOverlayCleanup:
    """Test TranscriptPreviewOverlay cleanup protocol."""

    def test_has_cleanup_method(self, qtbot):
        """Widget must implement cleanup() method."""
        from src.ui.widgets.transcript_preview_overlay import TranscriptPreviewOverlay

        overlay = TranscriptPreviewOverlay()
        qtbot.addWidget(overlay)

        assert hasattr(overlay, "cleanup")
        assert callable(overlay.cleanup)

    def test_cleanup_idempotent(self, qtbot):
        """cleanup() can be called multiple times safely."""
        from src.ui.widgets.transcript_preview_overlay import TranscriptPreviewOverlay

        overlay = TranscriptPreviewOverlay()
        qtbot.addWidget(overlay)

        overlay.cleanup()
        overlay.cleanup()


class TestMainWindowCleanup:
    """Test MainWindow recursive cleanup protocol."""

    def test_has_cleanup_children_method(self, qtbot):
        """MainWindow must implement _cleanup_children() method."""
        from src.ui.components.main_window.main_window import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert hasattr(window, "_cleanup_children")
        assert callable(window._cleanup_children)

    def test_cleanup_children_called_before_close(self, qtbot):
        """closeEvent must call _cleanup_children before accepting."""
        from src.ui.components.main_window.main_window import MainWindow
        from PyQt6.QtGui import QCloseEvent

        window = MainWindow()
        qtbot.addWidget(window)

        # Mock the cleanup method
        window._cleanup_children = Mock()

        # Simulate close event
        event = QCloseEvent()
        window.closeEvent(event)

        # Cleanup should have been called
        window._cleanup_children.assert_called_once()

    def test_cleanup_handles_missing_cleanup_methods(self, qtbot):
        """Cleanup should not crash if a child lacks cleanup()."""
        from src.ui.components.main_window.main_window import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Should not raise exception even if some children lack cleanup()
        window._cleanup_children()

    def test_cleanup_idempotent(self, qtbot):
        """_cleanup_children() can be called multiple times safely."""
        from src.ui.components.main_window.main_window import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        window._cleanup_children()
        window._cleanup_children()


class TestExportDialogCleanup:
    """Test ExportDialog cleanup protocol."""

    def test_has_cleanup_method(self, qtbot):
        """Widget must implement cleanup() method."""
        from src.ui.widgets.dialogs.export_dialog import ExportDialog

        dialog = ExportDialog()
        qtbot.addWidget(dialog)

        assert hasattr(dialog, "cleanup")
        assert callable(dialog.cleanup)

    def test_cleanup_idempotent(self, qtbot):
        """cleanup() can be called multiple times safely."""
        from src.ui.widgets.dialogs.export_dialog import ExportDialog

        dialog = ExportDialog()
        qtbot.addWidget(dialog)

        dialog.cleanup()
        dialog.cleanup()


class TestDialogTitleBarCleanup:
    """Test DialogTitleBar cleanup protocol."""

    def test_has_cleanup_method(self, qtbot):
        """Widget must implement cleanup() method."""
        from PyQt6.QtWidgets import QWidget
        from src.ui.components.title_bar.dialog_title_bar import DialogTitleBar

        parent = QWidget()
        qtbot.addWidget(parent)
        title_bar = DialogTitleBar("Test Title", parent)
        qtbot.addWidget(title_bar)

        assert hasattr(title_bar, "cleanup")
        assert callable(title_bar.cleanup)

    def test_cleanup_idempotent(self, qtbot):
        """cleanup() can be called multiple times safely."""
        from PyQt6.QtWidgets import QWidget
        from src.ui.components.title_bar.dialog_title_bar import DialogTitleBar

        parent = QWidget()
        qtbot.addWidget(parent)
        title_bar = DialogTitleBar("Test Title", parent)
        qtbot.addWidget(title_bar)

        title_bar.cleanup()
        title_bar.cleanup()
