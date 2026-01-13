"""
Base class for all specific views in the main application area.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Tuple

from PyQt6.QtWidgets import QWidget

from ui.contracts.capabilities import ActionId, Capabilities, ViewInterface

if TYPE_CHECKING:
    from ui.contracts.capabilities import SelectionState

from ui.contracts.capabilities import SelectionState


class BaseView(QWidget):
    """
    Abstract base class for main application views.
    
    Implements the ViewInterface protocol.
    """
    
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(self.__class__.__name__)
        self._logger = logging.getLogger(self.__class__.__name__)

    def get_capabilities(self) -> Capabilities:
        """
        Return the capabilities supported by this view.
        Default: No capabilities enabled.
        """
        return Capabilities()

    def get_selection(self) -> SelectionState:
        """
        Return current selection state.
        Default: Empty selection.
        """
        return SelectionState()

    def get_view_id(self) -> str:
        """
        Return unique identifier for this view instance.
        Must be implemented by concrete subclasses.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement get_view_id()")

    def dispatch_action(self, action: ActionId) -> None:
        """
        Handle a dispatched interaction action.
        Default: Log warning.
        """
        # In a real implementation this would map actions to intents or methods
        self._logger.warning(
            "Action %s dispatched to %s but not handled.", 
            action, 
            self.__class__.__name__
        )
