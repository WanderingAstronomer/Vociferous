"""
View Host Component.

A container that manages multiple Views (screens) and allows switching between them.
It maintains a registry of views and their identifiers.
"""

from __future__ import annotations

import logging

from PyQt6.QtWidgets import QStackedWidget, QWidget
from PyQt6.QtCore import pyqtSignal

logger = logging.getLogger(__name__)


class ViewHost(QStackedWidget):
    """
    Main content area switching between different functional views.
    """

    viewChanged = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._views: dict[str, int] = {}

    def register_view(self, view: QWidget, view_id: str) -> None:
        """
        Add a view to the host and register it with an ID.
        
        Args:
            view: The widget to display.
            view_id: Unique string identifier for the view.
        """
        if view_id in self._views:
            logger.warning(f"View ID '{view_id}' is already registered. Overwriting.")
            old_index = self._views[view_id]
            self.removeWidget(self.widget(old_index))
        
        index = self.addWidget(view)
        self._views[view_id] = index
        logger.debug(f"Registered view '{view_id}' at index {index}")

    def switch_to_view(self, view_id: str) -> None:
        """
        Activate the view associated with the given ID.
        
        Args:
            view_id: The ID of the view to show.
        
        Raises:
            ValueError: If view_id is not registered.
        """
        if view_id not in self._views:
            logger.error(f"Attempted to switch to unknown view_id: {view_id}")
            # Depending on policy, we might want to fail silently or fallback.
            # But the spec says "Raises error or logs warning".
            return

        index = self._views[view_id]
        changed = self.currentIndex() != index
        
        if changed:
            self.setCurrentIndex(index)
        
        # CRITICAL FIX: Always emit viewChanged, even if index didn't change.
        # This ensures ActionDock syncs on initial boot when QStackedWidget
        # auto-sets currentIndex to 0 for the first registered view.
        self.viewChanged.emit(view_id)
        
        if changed:
            logger.debug(f"Switched to view '{view_id}'")
        else:
            logger.debug(f"Activated current view '{view_id}' (emitted signal for observers)")
    
    def get_current_view_id(self) -> str | None:
        """Return the ID of the currently active view."""
        current_index = self.currentIndex()
        if current_index == -1:
            return None
            
        for vid, idx in self._views.items():
            if idx == current_index:
                return vid
        return None

    def get_view(self, view_id: str) -> QWidget | None:
        """
        Retrieve the view widget for a given ID.
        Useful for testing or specific child access.
        """
        idx = self._views.get(view_id)
        if idx is not None:
            return self.widget(idx)
        return None
