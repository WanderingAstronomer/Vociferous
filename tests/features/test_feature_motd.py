import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QWidget, QPushButton
from PyQt6.QtCore import Qt

from src.ui.components.workspace.header import WorkspaceHeader, _balance_motd_text
from src.ui.constants import WorkspaceState


class TestMOTDFeature:
    """Tests for the MOTD Refresh UI and Logic."""

    @pytest.fixture
    def header(self, qtbot, config_manager):
        """Fixture for WorkspaceHeader."""
        # Enable refinement so refresh button is visible in IDLE
        config_manager.set_config_value(True, "refinement", "enabled")
        widget = WorkspaceHeader()
        qtbot.addWidget(widget)
        widget.show()
        return widget

    def test_refresh_button_exists(self, header):
        """Verify the refresh button is in the UI."""
        assert hasattr(header, "refresh_button")
        assert isinstance(header.refresh_button, QPushButton)
        # Check icon is set (path string)
        assert not header.refresh_button.icon().isNull()

    def test_refresh_signal_propagation(self, header, qtbot):
        """Verify clicking the button emits the correct signal."""
        with qtbot.waitSignal(header.request_motd_refresh) as blocker:
            header.refresh_button.click()
        assert blocker.signal_triggered

    def test_visibility_logic(self, header):
        """Verify button is only visible in IDLE state."""
        # Setup IDLE
        header.set_state(WorkspaceState.IDLE)
        header.update_for_idle()
        assert header.refresh_button.isVisible()

        # Setup RECORDING
        header.set_state(WorkspaceState.RECORDING)
        header.update_for_recording()
        assert not header.refresh_button.isVisible()

        # Setup TRANSCRIBING (Visual state only)
        header.update_for_transcribing()
        assert not header.refresh_button.isVisible()

    def test_motd_chamber_logic(self):
        """
        Verify the Zero-Latency "Chamber" Logic:
        1. If stored in state -> Show Immediate -> Clear State.
        2. Always trigger generation for NEXT time.
        """
        from src.core.application_coordinator import ApplicationCoordinator
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        coordinator = ApplicationCoordinator(app)

        # Inject mocks
        coordinator.state_manager = MagicMock()
        coordinator.main_window = MagicMock()
        coordinator.slm_service = MagicMock()

        # Mock ConfigManager to return True for enablement
        with patch("src.core.application_coordinator.ConfigManager") as mock_config:
            mock_config.get_config_value.return_value = True

            # Case A: Chamber has MOTD
            coordinator.state_manager.get.return_value = "Cached Wisdom"

            # Run the handler
            coordinator._handle_motd_refresh()

            # Assertions
            coordinator.main_window.set_motd.assert_called_with("Cached Wisdom")
            coordinator.state_manager.set.assert_called_with("motd", None)  # Consumed
            coordinator.slm_service.generate_motd.assert_called()  # Refill request fired

            # Reset
            coordinator.main_window.reset_mock()
            coordinator.state_manager.reset_mock()
            coordinator.slm_service.reset_mock()

            # Case B: Chamber empty
            coordinator.state_manager.get.return_value = None

            # Run the handler
            coordinator._handle_motd_refresh()

            # Should not set MOTD (or set "fetching" if uncommented, but currently logic says consume cached only)
            coordinator.main_window.set_motd.assert_not_called()
            coordinator.slm_service.generate_motd.assert_called()

        coordinator.cleanup()

    def test_balancing_logic(self):
        """Verify _balance_motd_text behavior with various lengths."""
        # Short text should remain on one line (under 28 words)
        short = "This is a short sentence under twenty-eight words which should definitely stay on one single line for the user to read comfortably."
        assert _balance_motd_text(short) == short

        # Check a specific threshold: 31 words like the example in the prompt
        # "Today is the quiet moment before the keynote, where words find their harmony in the hum of the device, just as whispers of inspiration blend into a chorus in our minds."
        prompt_example = "Today is the quiet moment before the keynote, where words find their harmony in the hum of the device, just as whispers of inspiration blend into a chorus in our minds."
        # Word count is 31. Char count is ~194.
        # Should be 2 lines now (was 3).
        balanced = _balance_motd_text(prompt_example)
        assert len(balanced.split("\n")) == 2

        # Text over 240 chars should be 3 lines
        very_long = " ".join(["word"] * 60)  # 60 * 5 = 300 chars
        assert len(_balance_motd_text(very_long).split("\n")) == 3

        # Text over 420 chars should be 4 lines
        ultra_long = " ".join(["word"] * 90)  # 90 * 5 = 450 chars
        assert len(_balance_motd_text(ultra_long).split("\n")) == 4


class TestMOTDTextBalancing:
    """Tests for MOTD text balancing functionality."""

    def test_short_text_unchanged(self):
        """Short text should not be modified."""
        text = "Hello world"
        result = _balance_motd_text(text)
        assert result == text

    def test_long_text_balanced(self):
        """Long text should be balanced across lines."""
        # Need > 28 words to trigger balancing
        text = "As words bloom in the fertile terrain of digital terrain, Vociferous nurtures connections with the universe, transforming every single deep thought into tangible reality one keystroke at a time for all of humanity to witness."
        # Word count is 37. Chars ~231.
        # Should be 2 lines (under 240 chars).
        result = _balance_motd_text(text)
        lines = result.split("\n")
        assert len(lines) == 2

        # Check that lines have roughly equal word counts
        word_counts = [len(line.split()) for line in lines]
        assert max(word_counts) - min(word_counts) <= 3

    def test_custom_max_lines(self):
        """Test with custom maximum lines."""
        text = "This is a long sentence with many words that should be split across multiple lines for better readability and visual balance."
        result = _balance_motd_text(text, max_lines=3)
        lines = result.split("\n")
        assert len(lines) == 3

        # Check word distribution
        word_counts = [len(line.split()) for line in lines]
        # Should be roughly balanced
        assert max(word_counts) - min(word_counts) <= 2
