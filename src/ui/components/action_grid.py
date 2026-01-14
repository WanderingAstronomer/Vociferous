"""
Action Grid Component.

A context-aware button grid that adapts its available actions
based on the active View's capabilities.
"""

from __future__ import annotations


from PyQt6.QtWidgets import QWidget, QGridLayout, QPushButton

from ui.contracts.capabilities import ViewInterface, ActionId


class ActionGrid(QWidget):
    """
    Grid of action buttons driven by the active View's capabilities.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_view: ViewInterface | None = None
        self._buttons: dict[ActionId, QPushButton] = {}
        
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(4)
        
        self._init_buttons()

    def _init_buttons(self) -> None:
        """Initialize all possible action buttons (hidden by default)."""
        # Definition order determines grid placement
        actions = [
            (ActionId.EDIT, "Edit", 0, 0),
            (ActionId.DELETE, "Delete", 0, 1),
            (ActionId.REFINE, "Refine", 0, 2),
            (ActionId.COPY, "Copy", 1, 0),
            (ActionId.EXPORT, "Export", 1, 1),
            (ActionId.DISCARD, "Discard", 1, 2),
            (ActionId.SAVE, "Save", 2, 0),
            (ActionId.CANCEL, "Cancel", 2, 1),
        ]

        for action_id, label, row, col in actions:
            btn = QPushButton(label)
            btn.setObjectName(f"btn_{action_id.value}")
            btn.setVisible(False) # Hidden by default
            
            # Use lambda with default arg to capture loop variable
            btn.clicked.connect(lambda checked, a=action_id: self._on_button_click(a))
            
            self._layout.addWidget(btn, row, col)
            self._buttons[action_id] = btn

    def set_active_view(self, view: ViewInterface | None) -> None:
        """
        Update the grid to reflect the capabilities of the new view.
        If view is None, all actions are disabled/hidden.
        """
        # Disconnect from previous view if it had the signal
        if self._current_view and hasattr(self._current_view, "capabilitiesChanged"):
            try:
                self._current_view.capabilitiesChanged.disconnect(self._refresh_capabilities)
            except Exception:
                pass

        self._current_view = view
        
        if view is None:
            self._hide_all()
            self.setEnabled(False)
            return

        # Connect to new view
        if hasattr(view, "capabilitiesChanged"):
             view.capabilitiesChanged.connect(self._refresh_capabilities)

        self.setEnabled(True)
        self._refresh_capabilities()

    def _refresh_capabilities(self) -> None:
        """Fetch capabilities from current view and update buttons."""
        if not self._current_view:
            return

        caps = self._current_view.get_capabilities()
        
        # Update visibility/state based on capabilities
        # Note: This is a direct mapping. Complex logic might go here later.
        self._update_button(ActionId.EDIT, caps.can_edit)
        self._update_button(ActionId.DELETE, caps.can_delete)
        self._update_button(ActionId.REFINE, caps.can_refine)
        self._update_button(ActionId.COPY, caps.can_copy)
        self._update_button(ActionId.EXPORT, caps.can_export)
        
        # Transactional Actions
        self._update_button(ActionId.SAVE, caps.can_save)
        self._update_button(ActionId.DISCARD, caps.can_discard)
        self._update_button(ActionId.CANCEL, caps.can_discard) # CANCEL maps to DISCARD logic usually


    def _update_button(self, action_id: ActionId, visible: bool) -> None:
        if action_id in self._buttons:
            self._buttons[action_id].setVisible(visible)

    def _hide_all(self) -> None:
        for btn in self._buttons.values():
            btn.setVisible(False)

    def _on_button_click(self, action_id: ActionId) -> None:
        if self._current_view:
            self._current_view.dispatch_action(action_id)
