"""
test_ui_contracts.py

Formal regression tests for UI contracts, constraints, and invariants.
These tests enforce structural rules (wrapping, alignment, layout hierarchy)
rather than appearance.
"""

from typing import cast
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QModelIndex, QRect, QSize, Qt
from PyQt6.QtGui import QFont, QFontMetrics, QPainter, QImage, QStandardItemModel
from PyQt6.QtWidgets import (
    QStyle,
    QStyleOptionViewItem,
    QWidget,
    QLabel,
    QBoxLayout,
    QFrame,
    QLineEdit,
    QPushButton,
)

from src.ui.views.search_view import SearchTextDelegate, SearchView
from src.ui.widgets.history_tree.history_tree_delegate import TreeHoverDelegate
from src.ui.widgets.hotkey_widget.hotkey_widget import HotkeyWidget
from src.ui.views.user_view import UserView
from src.ui.models import TranscriptionModel
from src.ui.components.workspace.content import WorkspaceContent
from src.ui.views.settings_view import SettingsView


class TestSearchViewConstraints:
    """Enforce text wrapping and layout limits in SearchView."""

    @pytest.fixture
    def delegate(self):
        return SearchTextDelegate()

    def test_max_lines_constant_exists(self, delegate):
        """MAX_LINES must be explicitly defined as 6."""
        assert hasattr(delegate, "MAX_LINES"), "MAX_LINES constant missing"
        assert delegate.MAX_LINES == 6, "MAX_LINES must be exactly 6"

    def test_text_wrapping_constraints(self, delegate):
        """
        Enforce that text row height never exceeds MAX_LINES.
        """
        # Mock option and widget
        option = QStyleOptionViewItem()
        option.font = QFont("Arial", 12)
        option.rect = QRect(0, 0, 200, 0)  # Fixed width

        # Helper to get height for text
        def get_height(text):
            index = MagicMock(spec=QModelIndex)
            index.data.return_value = text
            index.column.return_value = 0
            return delegate.sizeHint(option, index).height()

        fm = QFontMetrics(option.font)
        line_height = fm.lineSpacing()
        base_padding = delegate.PADDING

        # Case 1: Short text (1 lines)
        short_text = "Short text"
        h_short = get_height(short_text)
        # Should be roughly 1 line + padding
        expected_short = (
            fm.boundingRect(
                QRect(0, 0, 200, 0), Qt.TextFlag.TextWordWrap, short_text
            ).height()
            + base_padding
        )
        assert h_short == expected_short, "Short text should wrap naturally"

        # Case 2: Long text (> 6 lines)
        long_line = (
            "A very long line of text that will definitely resize wrapping. " * 3
        )
        long_text = "\n".join([long_line] * 10)

        h_long = get_height(long_text)
        max_allowed = (line_height * 6) + base_padding

        # Allow small pixel tolerance for font rendering diffs
        assert h_long <= max_allowed + 2, "Row height exceeded 6-line limit"

        # Verify it actually truncated (height should be strictly less than full height)
        full_height = (
            fm.boundingRect(
                QRect(0, 0, 200, 0), Qt.TextFlag.TextWordWrap, long_text
            ).height()
            + base_padding
        )
        assert h_long < full_height, "Row did not truncate long text"

    def test_text_top_alignment(self, delegate):
        """Enforce top alignment for readability."""
        option = QStyleOptionViewItem()

        # Need real model and index for C++ side
        model = QStandardItemModel()
        item = model.invisibleRootItem()
        index = model.indexFromItem(item)

        # We need a real painter for QStyledItemDelegate
        image = QImage(100, 100, QImage.Format.Format_ARGB32)
        painter = QPainter(image)
        try:
            delegate.paint(painter, option, index)
        finally:
            painter.end()

        assert option.displayAlignment & Qt.AlignmentFlag.AlignTop, (
            "Delegate must enforce Top alignment"
        )


class TestHistoryViewAlignment:
    """Enforce alignment contracts for HistoryView."""

    def test_date_header_centered(self, qtbot):
        """
        Date headers must be centered.
        """
        delegate = TreeHoverDelegate()
        painter = MagicMock(spec=QPainter)
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, 100, 30)

        index = MagicMock(spec=QModelIndex)
        index.data.side_effect = (
            lambda role: "Today"
            if role == Qt.ItemDataRole.DisplayRole
            else True
            if role == TranscriptionModel.IsHeaderRole
            else None
        )

        # Capture drawText calls
        delegate.paint(painter, option, index)

        # Verify drawText called with AlignCenter
        # We need to find the call that draws the text
        draw_text_calls = [
            call for call in painter.drawText.mock_calls if "Today" in str(call)
        ]

        assert draw_text_calls, "drawText not called for header"

        args = draw_text_calls[0].args
        flags = args[1]

        assert flags & Qt.AlignmentFlag.AlignCenter, "Header must use AlignCenter"
        assert not (flags & Qt.AlignmentFlag.AlignLeft), "Header must NOT use AlignLeft"


class TestHotkeyWidgetIntegrity:
    """Enforce layout integrity for the Hotkey Widget."""

    @pytest.fixture
    def widget(self, qtbot):
        mock_listener = MagicMock()
        widget = HotkeyWidget(mock_listener)
        qtbot.addWidget(widget)
        return widget

    def test_no_layout_clipping(self, widget):
        """
        Assert layout has 0 margins to prevent clipping in small containers.
        """
        layout = widget.layout()
        margins = layout.contentsMargins()
        assert margins.left() == 0
        assert margins.top() == 0
        assert margins.right() == 0
        assert margins.bottom() == 0

        # Inner row layout
        row = layout.itemAt(0).layout()
        row_margins = row.contentsMargins()
        assert row_margins.top() == 0
        assert row_margins.bottom() == 0


class TestUserViewStructure:
    """Enforce structural organization of User View metrics."""

    @pytest.fixture
    def user_view(self, qtbot):
        view = UserView()
        qtbot.addWidget(view)
        return view

    def test_metrics_grouping(self, user_view):
        """
        Metrics must be grouped semantically, not a flat list.
        """
        # Access the private method to generate metrics, or inspect the layout
        # We can inspect the children of the metrics section.

        # Find the metrics section (it has header "Lifetime Statistics")
        # Since we don't have easy IDs for sections, we look for
        # objects with objectName "metricCard" and check their hierarchy

        cards = user_view.findChildren(QFrame, "metricCard")
        assert len(cards) >= 5, "Should have at least 5 metrics"

        # Verify hierarchy: Cards should NOT be direct children of the main section layout
        # They should be nested in grouped layouts/widgets.

        # Pick a card
        card = cards[0]
        card.parentWidget()  # This is likely a wrapper or the group widget

        # If flat, parent might be the section or scroll area content.
        # If grouped, parent should be a group widget.

        # Check if cards share the same immediate parent
        parents = {c.parentWidget() for c in cards}
        assert len(parents) > 1, (
            "All cards share the same parent, implying a flat layout. They must be grouped."
        )

    def test_headline_metrics_differentiation(self, user_view):
        """
        Headline metrics (Productivity) must be visually distinct.
        """
        # We defined 'highlight=True' for time_saved and total_words
        saved_val = user_view.metric_labels.get("time_saved")
        count_val = user_view.metric_labels.get("total_transcriptions")

        assert saved_val is not None
        assert count_val is not None

        # Check font size in stylesheet or font object
        # Since we set stylesheet directly:
        style_saved = saved_val.styleSheet()
        style_count = count_val.styleSheet()

        # Simple string check for font size difference
        # Saved should be larger (48px vs XXL)
        assert "48px" in style_saved, "Headline metric should use 48px font"
        assert "48px" not in style_count, "Secondary metric should not use large font"
