"""
Action Dock Component.

A context-aware control surface that adapts its available actions
based on the active view's capabilities.
"""

from __future__ import annotations


from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton

from ui.contracts.capabilities import ViewInterface, ActionId


class ActionDock(QWidget):
    """
    Control surface driven by the active View's capabilities.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_view: ViewInterface | None = None
        self._buttons: dict[ActionId, QPushButton] = {}
        
        # Changed from QGridLayout to QVBoxLayout for "rail" semantics
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(4)
        
        self._init_buttons()

    def _init_buttons(self) -> None:
        """Initialize all possible action buttons (hidden by default)."""
        actions = [
            (ActionId.START_RECORDING, "Start Recording"),
            (ActionId.STOP_RECORDING, "Stop Recording"),
            (ActionId.CREATE_PROJECT, "Create Project"),
            (ActionId.EDIT, "Edit"),
            (ActionId.DELETE, "Delete"),
            (ActionId.REFINE, "Refine"),
            (ActionId.COPY, "Copy"),
            (ActionId.EXPORT, "Export"),
            (ActionId.DISCARD, "Discard"),
            (ActionId.SAVE, "Save"),
            (ActionId.CANCEL, "Cancel"),
        ]

        for action_id, label in actions:
            btn = QPushButton(label)
            btn.setObjectName(f"btn_{action_id.value}")
            btn.setVisible(False) # Hidden by default
            
            # Use lambda with default arg to capture loop variable
            btn.clicked.connect(lambda checked, a=action_id: self._on_button_click(a))
            
            self._layout.addWidget(btn)
            self._buttons[action_id] = btn
        
        self._layout.addStretch()

    def set_active_view(self, view: ViewInterface | None) -> None:
        """
        Update the dock to reflect the capabilities of the new view.
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
        self._update_button(ActionId.START_RECORDING, caps.can_start_recording)
        self._update_button(ActionId.STOP_RECORDING, caps.can_stop_recording)
        self._update_button(ActionId.CREATE_PROJECT, caps.can_create_project)
        self._update_button(ActionId.EDIT, caps.can_edit)
        self._update_button(ActionId.DELETE, caps.can_delete)
        self._update_button(ActionId.REFINE, caps.can_refine)
        self._update_button(ActionId.COPY, caps.can_copy)
        self._update_button(ActionId.EXPORT, caps.can_export)
        
        # Transactional Actions
        self._update_button(ActionId.SAVE, caps.can_save)
        self._update_button(ActionId.DISCARD, caps.can_discard)
        self._update_button(ActionId.CANCEL, caps.can_discard) # CANCEL maps to DISCARD logic usually

    def get_button(self, action_id: ActionId | str) -> QPushButton | None:
        """
        Get a button by ActionId for testing purposes.
        
        Args:
            action_id: ActionId enum or string value of action
            
        Returns:
            QPushButton if found, None otherwise
        """
        if isinstance(action_id, str):
            # Convert string to ActionId
            try:
                action_id = ActionId(action_id)
            except ValueError:
                return None
        return self._buttons.get(action_id)

    def _update_button(self, action_id: ActionId, visible: bool) -> None:
        if action_id in self._buttons:
            self._buttons[action_id].setVisible(visible)

    def _hide_all(self) -> None:
        for btn in self._buttons.values():
            btn.setVisible(False)

    def _on_button_click(self, action_id: ActionId) -> None:
        if self._current_view:
            self._current_view.dispatch_action(action_id)
