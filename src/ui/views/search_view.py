"""
SearchView - Dedicated and powerful search interface.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import Qt, QSortFilterProxyModel, QSize, pyqtSlot, QRegularExpression
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QVBoxLayout, QTableView, QHeaderView, QAbstractItemView, QWidget,
    QLineEdit, QHBoxLayout, QLabel, QFrame
)

from ui.constants import Colors, Typography
from ui.constants.view_ids import VIEW_SEARCH
from ui.contracts.capabilities import Capabilities, SelectionState, ActionId
from ui.views.base_view import BaseView
from ui.models import TranscriptionModel
from ui.widgets.transcript_preview_overlay import TranscriptPreviewOverlay

if TYPE_CHECKING:
    from history_manager import HistoryManager

logger = logging.getLogger(__name__)

class SearchProxyModel(QSortFilterProxyModel):
    """Proxy model for filtering transcription history."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setRecursiveFilteringEnabled(True)

    def filterAcceptsRow(self, source_row: int, source_parent: Any) -> bool:
        model = self.sourceModel()
        index = model.index(source_row, 0, source_parent)
        
        if not index.isValid():
            return False
            
        is_header = index.data(TranscriptionModel.IsHeaderRole)
        if is_header:
            return True 
        
        pattern = self.filterRegularExpression().pattern()
        if not pattern:
            return True
            
        text = index.data(TranscriptionModel.FullTextRole)
        if text and pattern.lower() in text.lower():
            return True
            
        return False

class SearchView(BaseView):
    """View for searching through transcription history."""
    
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._history_manager: HistoryManager | None = None
        self._model: TranscriptionModel | None = None
        self._proxy: SearchProxyModel | None = None
        
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Search Bar
        search_container = QHBoxLayout()
        lbl_icon = QLabel("🔍")
        lbl_icon.setFont(QFont("Segoe UI", Typography.FONT_SIZE_LG, Typography.FONT_WEIGHT_NORMAL))
        
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search transcripts...")
        self._search_input.setFixedHeight(36)
        # Styling handled in unified_stylesheet.py (SearchView QLineEdit)
        self._search_input.textChanged.connect(self._on_search_text_changed)
        
        search_container.addWidget(lbl_icon)
        search_container.addWidget(self._search_input)
        layout.addLayout(search_container)
        
        # Results Table
        self._table = QTableView()
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().hide()
        self._table.setShowGrid(False)
        # Styling in unified_stylesheet.py (SearchView QTableView)
        
        self._table.activated.connect(self._on_row_activated)
            
        layout.addWidget(self._table)
        
        # Overlay
        self._overlay = TranscriptPreviewOverlay(self)
        self._overlay.hide()
        self._overlay.closed.connect(self._on_overlay_closed)

    def set_history_manager(self, manager: HistoryManager) -> None:
        self._history_manager = manager
        self._model = TranscriptionModel(manager)
        self._proxy = SearchProxyModel()
        self._proxy.setSourceModel(self._model)
        self._table.setModel(self._proxy)
        
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)

    def get_view_id(self) -> str:
        return VIEW_SEARCH

    def get_capabilities(self) -> Capabilities:
        selection = self.get_selection()
        has_selection = bool(selection.selected_ids)
        
        return Capabilities(
            can_edit=has_selection,
            can_delete=has_selection,
            can_copy=has_selection,
            can_refine=has_selection
        )

    def get_selection(self) -> SelectionState:
        if not self._table.selectionModel():
            return SelectionState()
            
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return SelectionState()
            
        proxy_idx = indexes[0]
        source_idx = self._proxy.mapToSource(proxy_idx)
        
        is_header = source_idx.data(TranscriptionModel.IsHeaderRole)
        if is_header:
             return SelectionState()
             
        t_id = source_idx.data(TranscriptionModel.IdRole)
        if t_id:
            return SelectionState(selected_ids=(t_id,), primary_id=t_id)
            
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
            self._proxy.setFilterRegularExpression(QRegularExpression(text, QRegularExpression.PatternOption.CaseInsensitiveOption))
            self._proxy.sort(0, Qt.SortOrder.DescendingOrder)

    def _on_row_activated(self, index) -> None:
        # Check validity
        if not index.isValid(): return
        source_idx = self._proxy.mapToSource(index)
        
        is_header = source_idx.data(TranscriptionModel.IsHeaderRole)
        if is_header: return
            
        full_text = source_idx.data(TranscriptionModel.FullTextRole)
        timestamp = source_idx.data(TranscriptionModel.TimestampRole)
        
        if full_text:
            self._update_overlay_geometry()
            self._overlay.show_transcript(full_text, title=f"Transcript {timestamp}")
            
    def _on_overlay_closed(self) -> None:
        self._table.setFocus()
        
    def _on_selection_changed(self) -> None:
        self.capabilitiesChanged.emit()
        
    def dispatch_action(self, action_id: ActionId) -> None:
        selection = self.get_selection()
        if not selection.has_selection: return
        # Basic dispatch support
        if action_id == ActionId.COPY:
             entry = self._history_manager.get_entry(selection.primary_id)
             if entry:
                from ui.utils.clipboard_utils import copy_text
                copy_text(entry.text)