"""
SearchView - Dedicated and powerful search interface.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import Qt, QSortFilterProxyModel, pyqtSlot, pyqtSignal, QSize, QRect
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QKeySequence
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QAbstractItemView,
    QWidget,
    QLineEdit,
    QLabel,
    QTableView,
    QHeaderView,
    QStyledItemDelegate,
)

from src.database.signal_bridge import DatabaseSignalBridge
from src.database.events import EntityChange
from src.ui.constants import Typography, Spacing
from src.ui.constants.view_ids import VIEW_SEARCH
from src.ui.contracts.capabilities import Capabilities, SelectionState, ActionId
from src.ui.views.base_view import BaseView
from src.ui.models import TranscriptionTableModel
from src.ui.widgets.transcript_preview_overlay import TranscriptPreviewOverlay

if TYPE_CHECKING:
    from src.database.history_manager import HistoryManager

logger = logging.getLogger(__name__)


class SearchProxyModel(QSortFilterProxyModel):
    """Proxy model for filtering transcription history."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setRecursiveFilteringEnabled(False)
        self.setFilterKeyColumn(-1)  # Search all columns
        self.setSortRole(Qt.ItemDataRole.UserRole)  # Sort by raw data
        self._search_pattern = ""

    def filterAcceptsRow(self, source_row: int, source_parent: Any) -> bool:
        if not self._search_pattern:
            return True

        model = self.sourceModel()
        for col in range(model.columnCount(source_parent)):
            index = model.index(source_row, col, source_parent)
            data = model.data(index, Qt.ItemDataRole.DisplayRole)
            if data and self._search_pattern.lower() in str(data).lower():
                return True
        return False


class SearchTextDelegate(QStyledItemDelegate):
    """Delegate to limit text row height to ~6 lines."""

    MAX_LINES = 6
    PADDING = 12

    def paint(self, painter, option, index):
        # Apply background color from model if present (for project coloring)
        bg_color = index.data(Qt.ItemDataRole.BackgroundRole)
        if bg_color and isinstance(bg_color, QColor) and bg_color.alpha() > 0:
            painter.fillRect(option.rect, bg_color)

        # Let default delegate handle selection background/focus
        # We enforce Top alignment for text to ensure we see the start
        option.displayAlignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        super().paint(painter, option, index)

    def sizeHint(self, option, index):
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        if not text:
            return super().sizeHint(option, index)

        # Get width from view if possible
        width = option.rect.width()
        if width <= 0:
            view = option.widget
            if hasattr(view, "columnWidth"):
                width = view.columnWidth(index.column())

        if width <= 0:
            return super().sizeHint(option, index)

        font = option.font
        fm = QFontMetrics(font)

        # Calculate bounding rect for wrapped text
        rect = fm.boundingRect(QRect(0, 0, width, 0), Qt.TextFlag.TextWordWrap, text)

        line_height = fm.lineSpacing()
        max_height = line_height * self.MAX_LINES

        # Clamp height
        height = min(rect.height(), max_height) + self.PADDING
        return QSize(width, height)


class SearchTableView(QTableView):
    """Custom table view for search results with standard keyboard actions."""

    def keyPressEvent(self, event) -> None:
        """Handle keyboard shortcuts for the table."""
        if event.matches(QKeySequence.StandardKey.Copy):
            # Find the SearchView parent to trigger the copy action
            parent = self.parent()
            while parent and not isinstance(parent, SearchView):
                parent = parent.parent()

            if parent:
                parent.dispatch_action(ActionId.COPY)
                event.accept()
                return

        super().keyPressEvent(event)


class SearchView(BaseView):
    """View for searching through transcription history using a table interface."""

    # Signals for routing to other views
    edit_requested = pyqtSignal(int)  # transcript_id
    delete_requested = pyqtSignal(list)  # list of transcript_ids
    refine_requested = pyqtSignal(int)  # transcript_id

    def cleanup(self) -> None:
        """Disconnect global signals."""
        try:
            DatabaseSignalBridge().data_changed.disconnect(self._handle_data_changed)
        except (TypeError, RuntimeError):
            pass
        super().cleanup()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._history_manager: HistoryManager | None = None
        self._model: TranscriptionTableModel | None = None
        self._proxy: SearchProxyModel | None = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.S3, Spacing.S3, Spacing.S3, Spacing.S3)
        layout.setSpacing(Spacing.S2)

        # Header Banner
        header_label = QLabel("Search your transcripts")
        header_label.setObjectName("searchHeaderLabel")
        header_font = QFont()
        header_font.setPointSize(Typography.FONT_SIZE_MD)
        header_font.setWeight(QFont.Weight.DemiBold)
        header_label.setFont(header_font)
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header_label)
        layout.addSpacing(Spacing.HEADER_CONTROLS_GAP)

        # Search Bar
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Filter...")
        self._search_input.setFixedHeight(36)
        # Styling handled in unified_stylesheet.py (SearchView QLineEdit)
        self._search_input.textChanged.connect(self._on_search_text_changed)

        layout.addWidget(self._search_input)

        # Results Table
        self._table = SearchTableView()
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        self._table.setWordWrap(True)  # Enable word wrapping for variable height

        # Apply custom delegate for text column
        self._table.setItemDelegateForColumn(
            TranscriptionTableModel.COL_TEXT, SearchTextDelegate(self._table)
        )

        # Configure Header
        header = self._table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        # Configure Rows
        self._table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

        self._table.activated.connect(self._on_row_activated)

        layout.addWidget(self._table)

        # Overlay
        self._overlay = TranscriptPreviewOverlay(self)
        self._overlay.hide()
        self._overlay.closed.connect(self._on_overlay_closed)

    def set_history_manager(self, manager: HistoryManager) -> None:
        self._history_manager = manager
        self._model = TranscriptionTableModel(manager)
        self._proxy = SearchProxyModel()
        self._proxy.setSourceModel(self._model)
        self._table.setModel(self._proxy)

        # Connect to database updates
        DatabaseSignalBridge().data_changed.connect(self._handle_data_changed)

    @pyqtSlot(EntityChange)
    def _handle_data_changed(self, change: EntityChange) -> None:
        """Handle incoming surgical updates from the database."""
        if change.entity_type == "transcription":
            # SearchView re-runs search on any transcription change
            # for data consistency.
            self.refresh()

        # Configure column resize modes
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(
            TranscriptionTableModel.COL_ID, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(
            TranscriptionTableModel.COL_TIMESTAMP,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            TranscriptionTableModel.COL_PROJECT,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            TranscriptionTableModel.COL_DURATION,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            TranscriptionTableModel.COL_TEXT, QHeaderView.ResizeMode.Stretch
        )
        # Set maximum width to prevent content column from rendering off-screen
        header.setMaximumSectionSize(800)

        self._table.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )

    def refresh(self) -> None:
        """Reload the model state."""
        if self._model:
            self._model.refresh_from_manager()
            # If search is active, we might want to re-apply filter or ensure proxy updates
            if self._proxy:
                self._proxy.invalidateFilter()

    def get_view_id(self) -> str:
        return VIEW_SEARCH

    def get_capabilities(self) -> Capabilities:
        from src.core.config_manager import ConfigManager

        selection = self.get_selection()
        has_selection = bool(selection.selected_ids)
        refinement_enabled = ConfigManager.get_config_value("refinement", "enabled")

        return Capabilities(
            can_edit=has_selection,
            can_delete=has_selection,
            can_copy=has_selection,
            can_refine=has_selection and refinement_enabled,
        )

    def get_selection(self) -> SelectionState:
        if not self._table.selectionModel():
            return SelectionState()

        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return SelectionState()

        selected_ids = []
        primary_id = None

        for proxy_idx in indexes:
            source_idx = self._proxy.mapToSource(proxy_idx)
            t_id = source_idx.data(TranscriptionTableModel.IdRole)

            # Fallback using COL_ID if Role is not working as expected (safety)
            if t_id is None:
                idx = source_idx.siblingAtColumn(TranscriptionTableModel.COL_ID)
                t_id = idx.data(Qt.ItemDataRole.UserRole)

            if t_id is not None:
                selected_ids.append(t_id)
                if primary_id is None:
                    primary_id = t_id

        if selected_ids:
            return SelectionState(
                selected_ids=tuple(selected_ids), primary_id=primary_id
            )

        return SelectionState()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._overlay.isVisible():
            self._update_overlay_geometry()

    def _update_overlay_geometry(self) -> None:
        margin = 24
        rect = self.rect().adjusted(margin, margin, -margin, -margin)
        self._overlay.setGeometry(rect)

    @pyqtSlot(str)
    def _on_search_text_changed(self, text: str) -> None:
        if self._proxy:
            # Store pattern and invalidate filter to trigger filterAcceptsRow
            self._proxy._search_pattern = text
            self._proxy.invalidateFilter()

    def _on_row_activated(self, index) -> None:
        # Check validity
        if not index.isValid():
            return
        source_idx = self._proxy.mapToSource(index)

        full_text = source_idx.data(TranscriptionTableModel.FullTextRole)
        timestamp = source_idx.data(TranscriptionTableModel.TimestampRole)

        if full_text:
            self._update_overlay_geometry()
            self._overlay.show_transcript(full_text, title=f"Transcript {timestamp}")

    def _on_overlay_closed(self) -> None:
        self._table.setFocus()

    def _on_selection_changed(self) -> None:
        self.capabilities_changed.emit()

    def dispatch_action(self, action_id: ActionId) -> None:
        """Handle actions dispatched by ActionDock."""
        selection = self.get_selection()
        if not selection.has_selection or selection.primary_id is None:
            return

        transcript_id = selection.primary_id

        if action_id == ActionId.COPY:
            entry = self._history_manager.get_entry(transcript_id)
            if entry:
                from src.ui.utils.clipboard_utils import copy_text

                copy_text(entry.text)

        elif action_id == ActionId.EDIT:
            # Emit signal to route to EditView
            if hasattr(self, "edit_requested"):
                self.edit_requested.emit(transcript_id)

        elif action_id == ActionId.DELETE:
            # Emit signal for deletion
            if hasattr(self, "delete_requested"):
                self.delete_requested.emit(list(selection.selected_ids))

        elif action_id == ActionId.REFINE:
            # Emit signal to route to RefineView
            if hasattr(self, "refine_requested"):
                self.refine_requested.emit(transcript_id)

    def update_transcript(self, timestamp: str, text: str) -> None:
        """Update a single transcript in the model without resetting."""
        # For now, simplistic refresh. Optimization can come later.
        self.refresh()
