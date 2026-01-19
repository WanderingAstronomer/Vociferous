import pytest
from unittest.mock import MagicMock
from PyQt6.QtCore import Qt, QModelIndex
from PyQt6.QtWidgets import QTableView
from src.ui.views.search_view import SearchView
from src.ui.models.table_model import TranscriptionTableModel
from src.ui.contracts.capabilities import ActionId
from src.database.dtos import HistoryEntry


# Mocks
class MockHistoryManager:
    def __init__(self):
        self.entries = []
        self._project_colors = {}

    def get_recent(self, limit=100):
        return self.entries

    def get_entry(self, t_id):
        for e in self.entries:
            if e.id == t_id:
                return e
        return None

    def get_project_colors(self):
        return self._project_colors

    def get_projects(self):
        return []


@pytest.fixture
def history_manager():
    hm = MockHistoryManager()
    # Add some dummy entries
    # Dates: 2023-01-01 (Group 1), 2023-01-02 (Group 2)
    e1 = HistoryEntry(
        id=1, timestamp="2023-01-01T12:00:00", text="Hello World", duration_ms=1000
    )
    e2 = HistoryEntry(
        id=2, timestamp="2023-01-01T12:05:00", text="Another entry", duration_ms=2000
    )
    e3 = HistoryEntry(
        id=3, timestamp="2023-01-02T10:00:00", text="Testing search", duration_ms=3000
    )
    hm.entries = [e3, e2, e1]
    return hm


def test_search_view_filters_entries(qtbot, history_manager):
    """
    Test that SearchView filters entries based on search text.
    Entries should be flat, not hierarchical.
    """
    view = SearchView()
    qtbot.addWidget(view)
    view.set_history_manager(history_manager)
    view._model.refresh_from_manager()

    # Check initial state (no search text)
    proxy = view._proxy
    assert proxy.rowCount(QModelIndex()) == 3

    # Search for "Hello" (Should match e1)
    view._search_input.setText("Hello")

    assert proxy.rowCount(QModelIndex()) == 1

    # Verify the visible entry is e1
    idx = proxy.index(0, 0)
    source_idx = proxy.mapToSource(idx)
    assert source_idx.data(TranscriptionTableModel.IdRole) == 1
    assert "Hello" in source_idx.data(TranscriptionTableModel.FullTextRole)


def test_search_view_uses_table_view(qtbot, history_manager):
    """
    SearchView MUST use QTableView for Excel-like appearance.
    """
    view = SearchView()
    qtbot.addWidget(view)

    assert isinstance(view._table, QTableView)


def test_dispatch_actions(qtbot, history_manager):
    """Test that actions are dispatched via signals."""
    view = SearchView()
    qtbot.addWidget(view)
    view.set_history_manager(history_manager)
    view._model.refresh_from_manager()

    # Mock signals
    view.edit_requested = MagicMock()
    view.delete_requested = MagicMock()
    view.refine_requested = MagicMock()

    # Select first item (e3 because order depends on backend list, typically get_recent returns recent first)
    # [e3, e2, e1]

    proxy = view._proxy
    idx = proxy.index(0, 0)

    # Select row
    view._table.selectionModel().select(
        idx,
        view._table.selectionModel().SelectionFlag.Select
        | view._table.selectionModel().SelectionFlag.Rows,
    )

    # Check selection
    selection = view.get_selection()
    assert selection.primary_id == 3

    # Dispatch
    view.dispatch_action(ActionId.EDIT)
    view.edit_requested.emit.assert_called_with(3)
