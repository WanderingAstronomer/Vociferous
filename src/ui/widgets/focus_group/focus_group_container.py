"""
FocusGroupContainer - Container widget for the Focus Group section.

Provides a wrapper around FocusGroupTreeWidget with:
- Layout management
- Signal forwarding
- External API for creating groups
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from ui.widgets.dialogs import CreateGroupDialog
from ui.widgets.focus_group.focus_group_tree import FocusGroupTreeWidget

if TYPE_CHECKING:
    from history_manager import HistoryManager


class FocusGroupContainer(QWidget):
    """
    Container for the Focus Group section.

    Includes the tree widget and forwards its signals.
    """

    # Signals (forwarded from tree)
    entrySelected = pyqtSignal(str, str)
    groupCreated = pyqtSignal(int, str)
    groupRenamed = pyqtSignal(int, str)
    groupDeleted = pyqtSignal(int)
    groupColorChanged = pyqtSignal(int, str)

    def __init__(
        self,
        history_manager: HistoryManager | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._history_manager = history_manager

        self.tree = FocusGroupTreeWidget(history_manager, self)
        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self) -> None:
        """Set up layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.tree)

        # Minimum height to prevent crushing
        self.setMinimumHeight(50)

    def _setup_connections(self) -> None:
        """Forward signals from tree widget."""
        self.tree.entrySelected.connect(self.entrySelected)
        self.tree.groupCreated.connect(self.groupCreated)
        self.tree.groupRenamed.connect(self.groupRenamed)
        self.tree.groupDeleted.connect(self.groupDeleted)
        self.tree.groupColorChanged.connect(self.groupColorChanged)

    def create_new_group(self) -> None:
        """Show dialog to create new group."""
        dialog = CreateGroupDialog(self)
        if dialog.exec():
            name, color = dialog.get_result()
            if name:
                self.tree.create_group(name, color)

    def set_history_manager(self, manager: HistoryManager) -> None:
        """Set the history manager."""
        self._history_manager = manager
        self.tree.set_history_manager(manager)

    def load_groups(self) -> None:
        """Load groups from manager."""
        self.tree.load_groups()

    def refresh_counts(self) -> None:
        """Refresh content."""
        self.tree.refresh_counts()
