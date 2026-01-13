"""
RecentView - Flat list of recent history items.
"""
# Force update: 2026-01-12

from __future__ import annotations

from typing import TYPE_CHECKING, Tuple


from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout, 
    QLabel, 
    QFrame, 
    QSplitter, 
    QVBoxLayout, 
    QTextEdit,
    QWidget
)

from ui.components.transcript_list import TranscriptList
from ui.constants.view_ids import VIEW_RECENT
from ui.contracts.capabilities import Capabilities, SelectionState
from ui.views.base_view import BaseView
from ui.models import TranscriptionModel, FocusGroupProxyModel
from ui.constants import Colors, Typography

if TYPE_CHECKING:
    from history_manager import HistoryManager, HistoryEntry

class RecentView(BaseView):
    """
    View for browsing recent transcripts.
    
    Layout:
        [ List of Transcripts ] | [ Preview / Detail ]
    """

    editRequested = pyqtSignal(int)
    refineRequested = pyqtSignal(int)

    def __init__(self, parent=None):

        super().__init__(parent)
        self._history_manager: HistoryManager | None = None
        self._model: TranscriptionModel | None = None
        self._proxy: FocusGroupProxyModel | None = None
        
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Initialize the two-pane layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._splitter = QSplitter()
        self._splitter.setHandleWidth(1)

        # Left Pane: Transcript List
        self._list_container = QFrame()
        list_layout = QVBoxLayout(self._list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        
        self.transcript_list = TranscriptList()
        self.transcript_list.selectionChangedSignal.connect(self._on_selection_changed)
        list_layout.addWidget(self.transcript_list)

        # Right Pane: Inspector
        self._inspector_container = QFrame()
        # Removed hardcoded background style
        
        self._setup_inspector()

        self._splitter.addWidget(self._list_container)
        self._splitter.addWidget(self._inspector_container)
        
        # Set initial sizes (List=40%, Detail=60%)
        self._splitter.setStretchFactor(0, 4)
        self._splitter.setStretchFactor(1, 6)

        layout.addWidget(self._splitter)
        
    def _setup_inspector(self) -> None:
        """Build the detail inspector pane."""
        layout = QVBoxLayout(self._inspector_container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # Header (Timestamp)
        self._lbl_timestamp = QLabel("Select a transcript")
        self._lbl_timestamp.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {Colors.TEXT_PRIMARY};")
        layout.addWidget(self._lbl_timestamp)
        
        # Metadata Row
        meta_layout = QHBoxLayout()
        self._lbl_duration = QLabel("-")
        self._lbl_duration.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        meta_layout.addWidget(self._lbl_duration)
        meta_layout.addStretch()
        layout.addLayout(meta_layout)
        
        # Content
        self._txt_content = QTextEdit()
        self._txt_content.setReadOnly(True)
        self._txt_content.setFrameShape(QFrame.Shape.NoFrame)
        # Use transparent background for read-only look
        self._txt_content.setStyleSheet(f"""
            QTextEdit {{
                background: transparent;
                color: {Colors.TEXT_PRIMARY};
                font-size: 14px;
                line-height: 1.5;
            }}
        """)
        layout.addWidget(self._txt_content)

    @pyqtSlot(tuple)
    def _on_selection_changed(self, selected_ids: tuple[str, ...]) -> None:
        """Handle selection update from list."""
        if not selected_ids:
            self._lbl_timestamp.setText("Select a transcript")
            self._lbl_duration.setText("-")
            self._txt_content.clear()
            return

        # Single selection support for now
        # Note: selected_ids are strings from proxy model, generally stringified ints
        try:
            primary_id = int(selected_ids[0])
            self._display_entry(primary_id)
        except (ValueError, IndexError):
            pass

    def _display_entry(self, entry_id: int) -> None:
        """Fetch and display entry details."""
        if not self._history_manager:
            return
            
        entry = self._history_manager.get_entry(entry_id)
        if not entry:
            return
            
        # Format Timestamp
        # Assuming ISO format "YYYY-MM-DDTHH:MM:SS..."
        try:
            ts = entry.timestamp.split("T")
            date_part = ts[0]
            time_part = ts[1][:8]
            display_ts = f"{date_part} {time_part}"
        except Exception:
            display_ts = entry.timestamp

        self._lbl_timestamp.setText(display_ts)
        self._lbl_duration.setText(f"Duration: {entry.duration_ms / 1000:.1f}s")
        self._txt_content.setText(entry.text)

    def dispatch_action(self, action_id: ActionId) -> None:
        """Handle actions from ActionGrid."""
        selection = self.get_selection()
        if not selection.has_selection:
            return
            
        # Parse ID
        try:
            # selection.selected_ids are strings, we need int
            transcript_id = int(selection.selected_ids[0])
        except (ValueError, IndexError):
            return

        if action_id == ActionId.EDIT:
            self.editRequested.emit(transcript_id)
            
        elif action_id == ActionId.REFINE:
            self.refineRequested.emit(transcript_id)
            
        elif action_id == ActionId.COPY:
            entry = self._history_manager.get_entry(transcript_id)
            if entry:
                from ui.utils.clipboard_utils import copy_text
                copy_text(entry.text)

    def get_view_id(self) -> str:
        return VIEW_RECENT

    def get_capabilities(self) -> Capabilities:
        """Return capabilities based on current selection."""
        selection = self.get_selection()
        has_selection = bool(selection.selected_ids)
        
        return Capabilities(
            can_edit=has_selection,
            can_delete=has_selection,
            can_refine=has_selection,
            can_copy=has_selection,
            # Export not yet supported directly in Capabilities dataclass
            can_move_to_project=has_selection
        )

    def get_selection(self) -> SelectionState:
        """Return current selection from the list."""
        ids = self.transcript_list.get_selected_ids()
        primary = ids[0] if ids else None
        return SelectionState(selected_ids=ids, primary_id=primary)

    def set_history_manager(self, manager: HistoryManager) -> None:
        """Inject history manager and setup models."""
        self._history_manager = manager
        
        # Create models
        # For RecentView, we might want to show EVERYTHING or just recent.
        # Ideally, we share the model instance if possible, or create a new one.
        # Since TranscriptionModel wraps manager, we can create one here.
        self._model = TranscriptionModel(manager)
        
        self.transcript_list.setModel(self._model)
        self.transcript_list.set_history_manager(manager)
