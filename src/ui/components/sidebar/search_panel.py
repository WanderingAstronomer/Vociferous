"""
SearchPanel - Search view for finding transcripts.

Provides:
- Search input field
- Scope selector (All, Focus Groups, Recent)
- Results list using shared delegate styling
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QRadioButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.constants import Colors, Spacing, Typography
from ui.utils.history_utils import (
    format_day_header,
    format_preview,
    format_time_compact,
)

if TYPE_CHECKING:
    from history_manager import HistoryEntry, HistoryManager


class SearchScope:
    """Search scope constants."""

    ALL = "all"
    FOCUS_GROUPS = "focus_groups"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"


class SearchPanel(QWidget):
    """
    Search panel for finding transcripts across all history.

    Signals:
        entrySelected(str, str): Emitted when result is clicked (text, timestamp)
        backRequested(): Emitted when user wants to return to previous tab
    """

    entrySelected = pyqtSignal(str, str)
    backRequested = pyqtSignal()

    def __init__(
        self,
        history_manager: "HistoryManager | None" = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("searchPanel")
        self._history_manager = history_manager
        self._last_query = ""

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self) -> None:
        """Create search panel layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            Spacing.SIDEBAR_SIDE,
            Spacing.SIDEBAR_TOP,
            Spacing.SIDEBAR_SIDE,
            Spacing.SIDEBAR_BOTTOM,
        )
        layout.setSpacing(Spacing.MINOR_GAP)

        # Search input row
        search_row = QHBoxLayout()
        search_row.setSpacing(Spacing.MINOR_GAP)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("searchInput")
        self._search_input.setPlaceholderText("Search transcripts...")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.returnPressed.connect(self._on_search)
        self._search_input.textChanged.connect(self._on_text_changed)
        search_row.addWidget(self._search_input, 1)

        layout.addLayout(search_row)

        # Scope selector with radio buttons
        scope_label = QLabel("Search in:")
        scope_label.setObjectName("scopeLabel")
        layout.addWidget(scope_label)

        # Radio button group
        self._scope_group = QButtonGroup(self)

        self._radio_all = QRadioButton("All History")
        self._radio_all.setObjectName("scopeRadio")
        self._radio_all.setChecked(True)
        self._radio_all.setProperty("scope", SearchScope.ALL)
        self._scope_group.addButton(self._radio_all)
        layout.addWidget(self._radio_all)

        self._radio_focus = QRadioButton("Focus Groups")
        self._radio_focus.setObjectName("scopeRadio")
        self._radio_focus.setProperty("scope", SearchScope.FOCUS_GROUPS)
        self._scope_group.addButton(self._radio_focus)
        layout.addWidget(self._radio_focus)

        self._radio_7days = QRadioButton("Last 7 Days")
        self._radio_7days.setObjectName("scopeRadio")
        self._radio_7days.setProperty("scope", SearchScope.LAST_7_DAYS)
        self._scope_group.addButton(self._radio_7days)
        layout.addWidget(self._radio_7days)

        self._radio_30days = QRadioButton("Last 30 Days")
        self._radio_30days.setObjectName("scopeRadio")
        self._radio_30days.setProperty("scope", SearchScope.LAST_30_DAYS)
        self._scope_group.addButton(self._radio_30days)
        layout.addWidget(self._radio_30days)

        self._scope_group.buttonClicked.connect(self._on_scope_changed)

        layout.addSpacing(Spacing.MINOR_GAP)

        # Results area
        self._results_container = QWidget()
        self._results_container.setObjectName("searchResults")
        results_layout = QVBoxLayout(self._results_container)
        results_layout.setContentsMargins(0, Spacing.MINOR_GAP, 0, 0)
        results_layout.setSpacing(0)

        # Placeholder message (shown when no search/results)
        self._placeholder = QLabel("Enter a search term to find transcripts")
        self._placeholder.setObjectName("searchPlaceholder")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setWordWrap(True)
        results_layout.addWidget(self._placeholder)

        # Results tree (hidden initially)
        self._results_tree = QTreeWidget()
        self._results_tree.setObjectName("searchResultsTree")
        self._results_tree.setHeaderHidden(True)
        self._results_tree.setColumnCount(2)
        self._results_tree.setRootIsDecorated(False)
        self._results_tree.setIndentation(0)
        self._results_tree.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._results_tree.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._results_tree.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._results_tree.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._results_tree.itemClicked.connect(self._on_result_clicked)
        self._results_tree.itemDoubleClicked.connect(self._on_result_double_clicked)

        # Configure header
        header = self._results_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 240)  # Wide enough for "Jan 10, 2026 11:30a"

        self._results_tree.hide()
        results_layout.addWidget(self._results_tree)

        results_layout.addStretch(1)

        layout.addWidget(self._results_container, 1)

    def _apply_styles(self) -> None:
        """Apply search panel styling."""
        self.setStyleSheet(f"""
            #searchPanel {{
                background: transparent;
            }}
            
            #searchInput {{
                background: {Colors.SURFACE_ALT};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: {Typography.BODY_SIZE}pt;
            }}
            
            #searchInput:focus {{
                border-color: {Colors.PRIMARY};
            }}
            
            #scopeLabel {{
                color: {Colors.TEXT_SECONDARY};
                font-size: {Typography.SMALL_SIZE}pt;
                padding-top: 4px;
            }}
            
            QRadioButton#scopeRadio {{
                color: {Colors.TEXT_PRIMARY};
                font-size: {Typography.SMALL_SIZE}pt;
                spacing: 8px;
                padding: 4px 0px;
            }}
            
            QRadioButton#scopeRadio::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                background-color: {Colors.BG_TERTIARY};
            }}
            
            QRadioButton#scopeRadio::indicator:checked {{
                background-color: {Colors.ACCENT_PRIMARY};
                border-color: {Colors.ACCENT_PRIMARY};
            }}
            
            QRadioButton#scopeRadio::indicator:hover {{
                border-color: {Colors.ACCENT_PRIMARY};
            }}
            
            #searchPlaceholder {{
                color: {Colors.TEXT_SECONDARY};
                font-size: {Typography.BODY_SIZE}pt;
                padding: 24px;
            }}
            
            #searchResults {{
                background: transparent;
            }}
            
            #searchResultsTree {{
                background: transparent;
                border: none;
                outline: none;
            }}
            
            #searchResultsTree::item {{
                padding: 6px 4px;
                border-bottom: 1px solid {Colors.BORDER_DEFAULT};
            }}
            
            #searchResultsTree::item:hover {{
                background-color: {Colors.HOVER_BG_ITEM};
            }}
            
            #searchResultsTree::item:selected {{
                background-color: {Colors.HOVER_BG_SECTION};
            }}
        """)

    def _on_text_changed(self, text: str) -> None:
        """Handle search text changes (for live search)."""
        # Could implement debounced live search here
        pass

    def _on_search(self) -> None:
        """Execute search."""
        query = self._search_input.text().strip()
        if not query:
            self._show_placeholder("Enter a search term to find transcripts")
            return

        if not self._history_manager:
            self._show_placeholder("Search unavailable")
            return

        self._last_query = query
        scope = self._scope_group.checkedButton().property("scope")

        # Perform search
        results = self._history_manager.search(query, scope=scope, limit=100)

        if not results:
            self._show_placeholder(f'No results found for "{query}"')
            return

        # Display results
        self._display_results(results, query)

    def _display_results(self, results: list, query: str) -> None:
        """Display search results in the tree widget."""
        self._placeholder.hide()
        self._results_tree.clear()
        self._results_tree.show()

        # Build group map for context
        group_map = {}
        if self._history_manager:
            try:
                groups = self._history_manager.get_focus_groups()
                for row in groups:
                    # Handle tuple variations (id, name, color...)
                    if row and len(row) >= 2:
                        group_map[row[0]] = row[1]
            except Exception:
                pass  # Fail gracefully if group fetch fails

        for entry in results:
            item = self._create_result_item(entry, query, group_map)
            self._results_tree.addTopLevelItem(item)

    def _create_result_item(
        self, entry: "HistoryEntry", query: str, group_map: dict = None
    ) -> QTreeWidgetItem:
        """Create a tree widget item for a search result."""
        # Parse timestamp for display
        try:
            dt = datetime.fromisoformat(entry.timestamp)
            date_str = format_day_header(dt)
            time_str = format_time_compact(dt)
            display_time = f"{date_str} {time_str}"
        except (ValueError, TypeError):
            display_time = entry.timestamp[:16] if entry.timestamp else ""

        # Add group context if available
        if group_map and entry.focus_group_id in group_map:
            group_name = group_map[entry.focus_group_id]
            # Prepend group name to timestamp/metadata column
            display_time = f"[{group_name}]  {display_time}"

        # Create preview with query highlighted context
        preview = format_preview(entry.text, 80)

        item = QTreeWidgetItem([preview, display_time])
        item.setData(0, Qt.ItemDataRole.UserRole, entry.text)
        item.setData(0, Qt.ItemDataRole.UserRole + 1, entry.timestamp)

        # Style the item
        item.setSizeHint(0, QSize(-1, 32))

        preview_font = QFont()
        preview_font.setPointSize(Typography.TRANSCRIPT_ITEM_SIZE)
        item.setFont(0, preview_font)
        item.setForeground(0, QColor(Colors.TEXT_PRIMARY))

        time_font = QFont()
        time_font.setPointSize(Typography.SMALL_SIZE)
        item.setFont(1, time_font)
        item.setForeground(1, QColor(Colors.ACCENT_BLUE))

        item.setTextAlignment(
            0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        item.setTextAlignment(
            1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        return item

    def _on_result_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle result item click."""
        if not item:
            return
        text = item.data(0, Qt.ItemDataRole.UserRole)
        timestamp = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if text and timestamp:
            self.entrySelected.emit(text, timestamp)

    def _on_result_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle result item double-click (copy to clipboard)."""
        if not item:
            return
        text = item.data(0, Qt.ItemDataRole.UserRole)
        if text:
            from ui.utils.clipboard_utils import copy_text

            copy_text(text)

    def _on_scope_changed(self, button) -> None:
        """Handle scope selection change."""
        if self._last_query:
            self._on_search()  # Re-run search with new scope

    def _show_placeholder(self, message: str) -> None:
        """Show placeholder message in results area."""
        self._results_tree.hide()
        self._placeholder.setText(message)
        self._placeholder.show()

    def focus_search(self) -> None:
        """Focus the search input field."""
        self._search_input.setFocus()
        self._search_input.selectAll()

    def clear(self) -> None:
        """Clear search input and results."""
        self._search_input.clear()
        self._results_tree.clear()
        self._last_query = ""
        self._show_placeholder("Enter a search term to find transcripts")

    def set_history_manager(self, manager: "HistoryManager") -> None:
        """Set history manager for search operations."""
        self._history_manager = manager
