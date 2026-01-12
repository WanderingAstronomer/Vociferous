"""
Collapsible section widget.

A header with toggle that expands/collapses content area.
Used in sidebar for Focus Groups and Transcripts sections.
"""

from PyQt6.QtCore import QEvent, QObject, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont, QMouseEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.constants import (
    HEADER_TO_LIST_GAP,
    QT_WIDGET_MAX_HEIGHT,
    SECTION_HEADER_HEIGHT,
    SECTION_HEADER_PADDING_H,
    SECTION_HEADER_PADDING_V,
    Typography,
)


class HeaderClickFilter(QObject):
    """Event filter to capture header clicks without overriding mousePressEvent."""

    clicked = pyqtSignal(QMouseEvent)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress:
            self.clicked.emit(event)
            return True
        return super().eventFilter(obj, event)


class CollapsibleSection(QWidget):
    """
    A collapsible section with header and content area.

    Header shows title, optional count, and optional action button.
    Content area expands/collapses on click.
    """

    toggled = pyqtSignal(bool)  # Emitted when collapsed state changes
    actionClicked = pyqtSignal()  # Emitted when header action button clicked

    def __init__(
        self,
        title: str,
        parent: QWidget | None = None,
        initially_collapsed: bool = False,
        show_action_button: bool = False,
        action_text: str = "+",
    ) -> None:
        super().__init__(parent)
        self._collapsed = initially_collapsed
        self._title = title
        self._count = 0
        self._show_action_button = show_action_button
        self._action_text = action_text
        self._disabled = False

        # Styles are applied at app level via generate_unified_stylesheet()

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create header and content layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(HEADER_TO_LIST_GAP)

        # Header widget
        self.header = QWidget()
        self.header.setObjectName("sectionHeader")
        self.header.setFixedHeight(SECTION_HEADER_HEIGHT)
        self.header.setCursor(Qt.CursorShape.PointingHandCursor)

        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(
            SECTION_HEADER_PADDING_H,
            SECTION_HEADER_PADDING_V,
            SECTION_HEADER_PADDING_H,
            SECTION_HEADER_PADDING_V,
        )
        header_layout.setSpacing(8)
        header_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Title with proper hierarchy font (left-aligned)
        self.title_label = QLabel(self._title)
        self.title_label.setObjectName("sectionHeaderLabel")
        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )
        title_font = QFont()
        title_font.setPointSize(Typography.SECTION_HEADER_SIZE)
        title_font.setWeight(QFont.Weight.DemiBold)
        self.title_label.setFont(title_font)

        # Count (right-aligned)
        self.count_label = QLabel("")
        self.count_label.setObjectName("sectionHeaderLabel")
        self.count_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        count_font = QFont()
        count_font.setPointSize(Typography.SECTION_HEADER_SIZE)
        self.count_label.setFont(count_font)

        self._update_styling()

        header_layout.addWidget(self.title_label, 1)
        header_layout.addWidget(self.count_label)

        # Optional action button (e.g., "+" for creating new items)
        self.action_button: QPushButton | None = None
        if self._show_action_button:
            self.action_button = QPushButton(self._action_text)
            self.action_button.setObjectName("sectionActionButton")
            self.action_button.setFixedSize(24, 24)
            self.action_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.action_button.clicked.connect(self._on_action_clicked)
            header_layout.addWidget(
                self.action_button, alignment=Qt.AlignmentFlag.AlignVCenter
            )

        # Make entire header clickable using event filter
        self._header_click_filter = HeaderClickFilter(self.header)
        self._header_click_filter.clicked.connect(self._on_header_click)
        self.header.installEventFilter(self._header_click_filter)

        layout.addWidget(self.header)

        # Content area (will hold the list)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)

        layout.addWidget(self.content, 1)

        # Set initial visibility
        self.content.setVisible(not self._collapsed)

        # Constrain max height when collapsed
        if self._collapsed:
            self.setMaximumHeight(SECTION_HEADER_HEIGHT)

    def toggle(self) -> None:
        """Toggle collapsed state."""
        self._collapsed = not self._collapsed
        self.content.setVisible(not self._collapsed)

        # Constrain max height when collapsed to prevent stretch space allocation
        if self._collapsed:
            self.setMaximumHeight(SECTION_HEADER_HEIGHT)
        else:
            self.setMaximumHeight(QT_WIDGET_MAX_HEIGHT)

        self._update_styling()
        self.toggled.emit(self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        """Set collapsed state without animation."""
        if self._collapsed != collapsed:
            self._collapsed = collapsed
            self.content.setVisible(not self._collapsed)

            # Constrain max height when collapsed
            if self._collapsed:
                self.setMaximumHeight(SECTION_HEADER_HEIGHT)
            else:
                self.setMaximumHeight(QT_WIDGET_MAX_HEIGHT)

            self._update_styling()

    def is_collapsed(self) -> bool:
        """Return current collapsed state."""
        return self._collapsed

    def is_expanded(self) -> bool:
        """Return True when content is visible (inverse of collapsed)."""
        return not self._collapsed

    def set_disabled(self, disabled: bool) -> None:
        """Set disabled state (grayed out, not expandable)."""
        self._disabled = disabled
        if disabled and not self._collapsed:
            self.set_collapsed(True)
        self._update_styling()

    def is_disabled(self) -> bool:
        """Return current disabled state."""
        return self._disabled

    @pyqtSlot(QMouseEvent)
    def _on_header_click(self, event: QMouseEvent) -> None:
        """Handle header click, avoiding action button area."""
        if self._disabled:
            return
        # Check if click is over the action button
        if self.action_button and self.action_button.geometry().contains(event.pos()):
            return
        self.toggle()

    @pyqtSlot()
    def _on_action_clicked(self) -> None:
        """Handle action button click."""
        self.actionClicked.emit()

    def set_count(self, count: int) -> None:
        """Update the count display."""
        self._count = count
        if count > 0:
            self.count_label.setText(str(count))
            self.count_label.setVisible(True)
        else:
            self.count_label.setText("")
            self.count_label.setVisible(False)

    def _update_styling(self) -> None:
        """Update header style based on collapsed/disabled state."""
        if self._disabled:
            self.title_label.setProperty("sectionState", "disabled")
            self.header.setCursor(Qt.CursorShape.ArrowCursor)
        elif self._collapsed:
            self.title_label.setProperty("sectionState", "collapsed")
            self.header.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.title_label.setProperty("sectionState", "expanded")
            self.header.setCursor(Qt.CursorShape.PointingHandCursor)

        # Refresh style
        self.title_label.style().unpolish(self.title_label)
        self.title_label.style().polish(self.title_label)

    def cleanup(self) -> None:
        """Clean up resources before destruction."""
        try:
            # Remove event filter
            if hasattr(self, "_header_click_filter") and self._header_click_filter:
                self.header.removeEventFilter(self._header_click_filter)
        except Exception:
            pass
