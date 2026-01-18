"""
Base class for all specific views in the main application area.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget

from ui.contracts.capabilities import ActionId, Capabilities, SelectionState


class BaseView(QWidget):
    """
    Abstract base class for main application views.

    Implements the ViewInterface protocol.
    """

    # Signal emitted when internal state changes (selection, mode)
    # prompting ActionGrid to re-query capabilities.
    capabilitiesChanged = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Initialize the base view.

        Args:
            parent: Optional parent widget for Qt ownership hierarchy.
        """
        super().__init__(parent)
        self.setObjectName(self.__class__.__name__)
        self._logger = logging.getLogger(self.__class__.__name__)

        # Ensure custom views respect background-color in stylesheet
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

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
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement get_view_id()"
        )

    def dispatch_action(self, action: ActionId) -> None:
        """
        Handle a dispatched interaction action.
        Default: Log warning.
        """
        # In a real implementation this would map actions to intents or methods
        self._logger.warning(
            "Action %s dispatched to %s but not handled.",
            action,
            self.__class__.__name__,
        )
