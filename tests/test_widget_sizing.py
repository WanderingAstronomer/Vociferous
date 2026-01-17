"""
Test widget sizing compliance with Qt6 best practices.

Verifies all custom widgets implement sizeHint() and minimumSizeHint()
per Qt documentation requirements.

References:
    - layout.html § "Custom Widgets in Layouts"
    - qsizepolicy.html § "Policy enum"
"""

import pytest
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QWidget, QVBoxLayout


class TestWaveformVisualizerSizing:
    """Test WaveformVisualizer sizing API compliance."""

    def test_has_size_hint_method(self, qtbot):
        """Widget must implement sizeHint() method."""
        from src.ui.widgets.visualizers.waveform_visualizer.waveform_visualizer import (
            WaveformVisualizer,
        )

        visualizer = WaveformVisualizer()
        qtbot.addWidget(visualizer)

        # Verify method exists and is callable
        assert hasattr(visualizer, "sizeHint")
        assert callable(visualizer.sizeHint)

    def test_size_hint_returns_qsize(self, qtbot):
        """sizeHint() must return QSize instance."""
        from src.ui.widgets.visualizers.waveform_visualizer.waveform_visualizer import (
            WaveformVisualizer,
        )

        visualizer = WaveformVisualizer()
        qtbot.addWidget(visualizer)

        size_hint = visualizer.sizeHint()

        assert isinstance(size_hint, QSize)
        assert size_hint.isValid()

    def test_size_hint_returns_reasonable_dimensions(self, qtbot):
        """sizeHint() must return non-zero, reasonable dimensions."""
        from src.ui.widgets.visualizers.waveform_visualizer.waveform_visualizer import (
            WaveformVisualizer,
        )

        visualizer = WaveformVisualizer()
        qtbot.addWidget(visualizer)

        size_hint = visualizer.sizeHint()

        # WaveformVisualizer uses expanding width policy with max width
        # Height should be fixed at 130
        assert size_hint.height() == 130
        # Width can be very large (for expanding), so just check > 0
        assert size_hint.width() > 0

    def test_minimum_size_hint_method(self, qtbot):
        """Widget should implement minimumSizeHint() method."""
        from src.ui.widgets.visualizers.waveform_visualizer.waveform_visualizer import (
            WaveformVisualizer,
        )

        visualizer = WaveformVisualizer()
        qtbot.addWidget(visualizer)

        assert hasattr(visualizer, "minimumSizeHint")
        assert callable(visualizer.minimumSizeHint)

    def test_minimum_size_hint_smaller_than_size_hint(self, qtbot):
        """minimumSizeHint() must be <= sizeHint()."""
        from src.ui.widgets.visualizers.waveform_visualizer.waveform_visualizer import (
            WaveformVisualizer,
        )

        visualizer = WaveformVisualizer()
        qtbot.addWidget(visualizer)

        size_hint = visualizer.sizeHint()
        min_size_hint = visualizer.minimumSizeHint()

        assert isinstance(min_size_hint, QSize)
        assert min_size_hint.width() <= size_hint.width()
        assert min_size_hint.height() <= size_hint.height()


class TestBarSpectrumVisualizerSizing:
    """Test BarSpectrumVisualizer sizing API compliance."""

    def test_has_size_hint_method(self, qtbot):
        """Widget must implement sizeHint() method."""
        from src.ui.widgets.visualizers.bar_spectrum_visualizer.bar_spectrum_visualizer import (
            BarSpectrumVisualizer,
        )

        visualizer = BarSpectrumVisualizer()
        qtbot.addWidget(visualizer)

        assert hasattr(visualizer, "sizeHint")
        assert callable(visualizer.sizeHint)

    def test_size_hint_returns_qsize(self, qtbot):
        """sizeHint() must return QSize instance."""
        from src.ui.widgets.visualizers.bar_spectrum_visualizer.bar_spectrum_visualizer import (
            BarSpectrumVisualizer,
        )

        visualizer = BarSpectrumVisualizer()
        qtbot.addWidget(visualizer)

        size_hint = visualizer.sizeHint()

        assert isinstance(size_hint, QSize)
        assert size_hint.isValid()

    def test_size_hint_returns_reasonable_dimensions(self, qtbot):
        """sizeHint() must return non-zero, reasonable dimensions."""
        from src.ui.widgets.visualizers.bar_spectrum_visualizer.bar_spectrum_visualizer import (
            BarSpectrumVisualizer,
        )

        visualizer = BarSpectrumVisualizer()
        qtbot.addWidget(visualizer)

        size_hint = visualizer.sizeHint()

        assert size_hint.width() >= 100
        assert size_hint.height() >= 50
        assert size_hint.width() <= 1000
        assert size_hint.height() <= 500

    def test_minimum_size_hint_method(self, qtbot):
        """Widget should implement minimumSizeHint() method."""
        from src.ui.widgets.visualizers.bar_spectrum_visualizer.bar_spectrum_visualizer import (
            BarSpectrumVisualizer,
        )

        visualizer = BarSpectrumVisualizer()
        qtbot.addWidget(visualizer)

        assert hasattr(visualizer, "minimumSizeHint")
        assert callable(visualizer.minimumSizeHint)

    def test_minimum_size_hint_smaller_than_size_hint(self, qtbot):
        """minimumSizeHint() must be <= sizeHint()."""
        from src.ui.widgets.visualizers.bar_spectrum_visualizer.bar_spectrum_visualizer import (
            BarSpectrumVisualizer,
        )

        visualizer = BarSpectrumVisualizer()
        qtbot.addWidget(visualizer)

        size_hint = visualizer.sizeHint()
        min_size_hint = visualizer.minimumSizeHint()

        assert isinstance(min_size_hint, QSize)
        assert min_size_hint.width() <= size_hint.width()
        assert min_size_hint.height() <= size_hint.height()


class TestToggleSwitchSizing:
    """Test ToggleSwitch sizing API compliance."""

    def test_has_size_hint_method(self, qtbot):
        """Widget must implement sizeHint() method."""
        from src.ui.widgets.toggle_switch import ToggleSwitch

        toggle = ToggleSwitch()
        qtbot.addWidget(toggle)

        assert hasattr(toggle, "sizeHint")
        assert callable(toggle.sizeHint)

    def test_size_hint_returns_qsize(self, qtbot):
        """sizeHint() must return QSize instance."""
        from src.ui.widgets.toggle_switch import ToggleSwitch

        toggle = ToggleSwitch()
        qtbot.addWidget(toggle)

        size_hint = toggle.sizeHint()

        assert isinstance(size_hint, QSize)
        assert size_hint.isValid()

    def test_size_hint_matches_fixed_size(self, qtbot):
        """sizeHint() should match the fixed size set in __init__."""
        from src.ui.widgets.toggle_switch import ToggleSwitch

        toggle = ToggleSwitch()
        qtbot.addWidget(toggle)

        size_hint = toggle.sizeHint()

        # ToggleSwitch uses setFixedSize(50, 24)
        assert size_hint.width() == 50
        assert size_hint.height() == 24

    def test_minimum_size_hint_method(self, qtbot):
        """Widget should implement minimumSizeHint() method."""
        from src.ui.widgets.toggle_switch import ToggleSwitch

        toggle = ToggleSwitch()
        qtbot.addWidget(toggle)

        assert hasattr(toggle, "minimumSizeHint")
        assert callable(toggle.minimumSizeHint)


class TestRailButtonSizing:
    """Test RailButton sizing API compliance."""

    def test_has_size_hint_method(self, qtbot):
        """Widget must implement sizeHint() method."""
        from src.ui.components.main_window.icon_rail import RailButton

        button = RailButton(view_id="transcribe", icon_name="transcribe", label="Transcribe")
        qtbot.addWidget(button)

        assert hasattr(button, "sizeHint")
        assert callable(button.sizeHint)

    def test_size_hint_returns_qsize(self, qtbot):
        """sizeHint() must return QSize instance."""
        from src.ui.components.main_window.icon_rail import RailButton

        button = RailButton(view_id="transcribe", icon_name="transcribe", label="Transcribe")
        qtbot.addWidget(button)

        size_hint = button.sizeHint()

        assert isinstance(size_hint, QSize)
        assert size_hint.isValid()

    def test_size_hint_square_dimensions(self, qtbot):
        """RailButton should return square dimensions."""
        from src.ui.components.main_window.icon_rail import RailButton

        button = RailButton(view_id="transcribe", icon_name="transcribe", label="Transcribe")
        qtbot.addWidget(button)

        size_hint = button.sizeHint()

        # RailButton uses setFixedHeight(110) and should be square
        assert size_hint.width() == 110
        assert size_hint.height() == 110

    def test_minimum_size_hint_method(self, qtbot):
        """Widget should implement minimumSizeHint() method."""
        from src.ui.components.main_window.icon_rail import RailButton

        button = RailButton(view_id="transcribe", icon_name="transcribe", label="Transcribe")
        qtbot.addWidget(button)

        assert hasattr(button, "minimumSizeHint")
        assert callable(button.minimumSizeHint)


class TestTranscriptPreviewOverlaySizing:
    """Test TranscriptPreviewOverlay sizing API compliance."""

    def test_has_size_hint_method(self, qtbot):
        """Widget must implement sizeHint() method."""
        from src.ui.widgets.transcript_preview_overlay import TranscriptPreviewOverlay

        overlay = TranscriptPreviewOverlay()
        qtbot.addWidget(overlay)

        assert hasattr(overlay, "sizeHint")
        assert callable(overlay.sizeHint)

    def test_size_hint_returns_qsize(self, qtbot):
        """sizeHint() must return QSize instance."""
        from src.ui.widgets.transcript_preview_overlay import TranscriptPreviewOverlay

        overlay = TranscriptPreviewOverlay()
        qtbot.addWidget(overlay)

        size_hint = overlay.sizeHint()

        assert isinstance(size_hint, QSize)
        assert size_hint.isValid()

    def test_size_hint_returns_reasonable_dimensions(self, qtbot):
        """sizeHint() must return reasonable overlay dimensions."""
        from src.ui.widgets.transcript_preview_overlay import TranscriptPreviewOverlay

        overlay = TranscriptPreviewOverlay()
        qtbot.addWidget(overlay)

        size_hint = overlay.sizeHint()

        # Overlay should be larger than 200x100 but not massive
        assert size_hint.width() >= 200
        assert size_hint.height() >= 100
        assert size_hint.width() <= 1000
        assert size_hint.height() <= 800

    def test_minimum_size_hint_method(self, qtbot):
        """Widget should implement minimumSizeHint() method."""
        from src.ui.widgets.transcript_preview_overlay import TranscriptPreviewOverlay

        overlay = TranscriptPreviewOverlay()
        qtbot.addWidget(overlay)

        assert hasattr(overlay, "minimumSizeHint")
        assert callable(overlay.minimumSizeHint)


class TestHistoryTreeViewSizing:
    """Test HistoryTreeView sizing API compliance."""

    def test_has_size_hint_method(self, qtbot):
        """Widget must implement sizeHint() method."""
        from src.ui.widgets.history_tree.history_tree_view import HistoryTreeView

        tree = HistoryTreeView()
        qtbot.addWidget(tree)

        assert hasattr(tree, "sizeHint")
        assert callable(tree.sizeHint)

    def test_size_hint_returns_qsize(self, qtbot):
        """sizeHint() must return QSize instance."""
        from src.ui.widgets.history_tree.history_tree_view import HistoryTreeView

        tree = HistoryTreeView()
        qtbot.addWidget(tree)

        size_hint = tree.sizeHint()

        assert isinstance(size_hint, QSize)
        assert size_hint.isValid()

    def test_size_hint_returns_reasonable_dimensions(self, qtbot):
        """sizeHint() must return reasonable tree dimensions."""
        from src.ui.widgets.history_tree.history_tree_view import HistoryTreeView

        tree = HistoryTreeView()
        qtbot.addWidget(tree)

        size_hint = tree.sizeHint()

        # Tree view should prefer vertical space
        assert size_hint.width() >= 150
        assert size_hint.height() >= 150
        assert size_hint.width() <= 800
        assert size_hint.height() <= 1000

    def test_minimum_size_hint_method(self, qtbot):
        """Widget should implement minimumSizeHint() method."""
        from src.ui.widgets.history_tree.history_tree_view import HistoryTreeView

        tree = HistoryTreeView()
        qtbot.addWidget(tree)

        assert hasattr(tree, "minimumSizeHint")
        assert callable(tree.minimumSizeHint)


class TestBlockingOverlaySizing:
    """Test BlockingOverlay sizing API compliance."""

    def test_has_size_hint_method(self, qtbot):
        """Widget must implement sizeHint() method."""
        from src.ui.widgets.dialogs.blocking_overlay import BlockingOverlay

        parent = QWidget()
        qtbot.addWidget(parent)
        overlay = BlockingOverlay(parent)
        qtbot.addWidget(overlay)

        assert hasattr(overlay, "sizeHint")
        assert callable(overlay.sizeHint)

    def test_size_hint_returns_qsize(self, qtbot):
        """sizeHint() must return QSize instance."""
        from src.ui.widgets.dialogs.blocking_overlay import BlockingOverlay

        parent = QWidget()
        qtbot.addWidget(parent)
        overlay = BlockingOverlay(parent)
        qtbot.addWidget(overlay)

        size_hint = overlay.sizeHint()

        assert isinstance(size_hint, QSize)
        assert size_hint.isValid()

    def test_minimum_size_hint_method(self, qtbot):
        """Widget should implement minimumSizeHint() method."""
        from src.ui.widgets.dialogs.blocking_overlay import BlockingOverlay

        parent = QWidget()
        qtbot.addWidget(parent)
        overlay = BlockingOverlay(parent)
        qtbot.addWidget(overlay)

        assert hasattr(overlay, "minimumSizeHint")
        assert callable(overlay.minimumSizeHint)
