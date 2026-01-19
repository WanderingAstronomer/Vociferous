"""
Action Dock Component.

A context-aware control surface that adapts its available actions
based on the active view's capabilities.
"""

from __future__ import annotations


from PyQt6.QtWidgets import (
    QWidget,
    QPushButton,
    QGridLayout,
    QSizePolicy,
    QVBoxLayout,
    QFrame,
    QHBoxLayout,
)
from PyQt6.QtCore import Qt

from src.ui.contracts.capabilities import ViewInterface, ActionId


class ActionDock(QWidget):
    """
    Control surface driven by the active View's capabilities.
    Displays action buttons in a visually refined layout.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_view: ViewInterface | None = None
        self._buttons: dict[ActionId, QPushButton] = {}

        # Enforce painting of background-color from stylesheet
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Outer container layout (holds separator + buttons)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Create centered half-width separator at top
        separator_container = QHBoxLayout()
        separator_container.setContentsMargins(0, 0, 0, 0)
        separator_container.addStretch()
        separator_line = QFrame()
        separator_line.setFrameShape(QFrame.Shape.HLine)
        separator_line.setFrameShadow(QFrame.Shadow.Sunken)
        separator_line.setObjectName("actionDockSeparator")
        separator_line.setFixedWidth(200)  # Half-width relative to typical dock
        separator_container.addWidget(separator_line)
        separator_container.addStretch()
        outer_layout.addLayout(separator_container)

        # Main layout for buttons with consistent spacing (S1 = 8px)
        self._layout = QGridLayout()
        # Bottom margin increased to 20px to align buttons with Icon Rail visual bottom
        self._layout.setContentsMargins(8, 8, 8, 20)
        self._layout.setSpacing(8)  # S1 from spacing scale
        outer_layout.addLayout(self._layout)

        # Ensure dock reserves space and resists compression
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        # Ensure dock reserves space and resists compression
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        self._init_buttons()

    def _init_buttons(self) -> None:
        """Initialize all possible action buttons with improved styling."""
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

        # Determine if button should use secondary or destructive style
        destructive_actions = {ActionId.DELETE, ActionId.DISCARD}
        primary_actions = {ActionId.SAVE, ActionId.START_RECORDING, ActionId.EDIT}
        purple_actions = {ActionId.REFINE}

        for action_id, label in actions:
            btn = QPushButton(label)
            # Keep the action-based name for test discovery
            btn.setObjectName(f"btn_{action_id.value}")
            btn.setVisible(False)  # Hidden by default
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            # Store style class as property for stylesheet selectors
            style_class = "secondaryButton"
            if action_id in destructive_actions:
                style_class = "destructiveButton"
            elif action_id in primary_actions:
                style_class = "primaryButton"
            elif action_id in purple_actions:
                style_class = "purpleButton"

            btn.setProperty("styleClass", style_class)

            # Set minimum height for better touch targets and vertical respect
            btn.setMinimumHeight(48)

            # Use lambda with default arg to capture loop variable
            btn.clicked.connect(lambda checked, a=action_id: self._on_button_click(a))

            # Initial parenting (layout manages this later, but safe to set here)
            btn.setParent(self)
            self._buttons[action_id] = btn

        # Initial layout pass (creates empty structure)
        self._repack_grid()

    def set_active_view(self, view: ViewInterface | None) -> None:
        """
        Update the dock to reflect the capabilities of the new view.
        If view is None, all actions are disabled/hidden.
        """
        # Disconnect from previous view if it had the signal
        if self._current_view and hasattr(self._current_view, "capabilities_changed"):
            try:
                self._current_view.capabilities_changed.disconnect(
                    self._refresh_capabilities
                )
            except Exception:
                pass

        self._current_view = view

        if view is None:
            self._hide_all()
            self.setEnabled(False)
            return

        # Connect to new view
        if hasattr(view, "capabilities_changed"):
            view.capabilities_changed.connect(self._refresh_capabilities)

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
        self._update_button(ActionId.CANCEL, caps.can_cancel)

        self._repack_grid()

    def _repack_grid(self) -> None:
        """Dynamically organize visible buttons into a grid."""
        # Clean up existing items from layout
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().setParent(self)

        # Define preferred sort order for consistency
        order = [
            ActionId.STOP_RECORDING,
            ActionId.CANCEL,
            ActionId.SAVE,  # Transactional
            ActionId.DISCARD,
            ActionId.CREATE_PROJECT,
            ActionId.EDIT,  # Modification
            ActionId.COPY,  # Output
            ActionId.DELETE,
            ActionId.REFINE,  # Append refinement last if present
            ActionId.EXPORT,
        ]

        # Gather visible buttons (excluding Start Recording)
        visible_buttons = []
        for aid in order:
            btn = self._buttons.get(aid)
            if btn and not btn.isHidden():
                visible_buttons.append(btn)

        # 1. Handle START_RECORDING specially (Top, Full Width)
        start_btn = self._buttons.get(ActionId.START_RECORDING)
        has_start = start_btn and not start_btn.isHidden()

        if not visible_buttons and not has_start:
            return

        row_offset = 0
        if has_start:
            # Span across all columns used by secondary buttons
            colspan = max(1, len(visible_buttons))
            self._layout.addWidget(start_btn, 0, 0, 1, colspan)
            row_offset = 1

        # Grid Packing - Single horizontal row for secondary actions
        for i, btn in enumerate(visible_buttons):
            # Row 1 (if start exists), Column i
            self._layout.addWidget(btn, row_offset, i)

        # Push everything to the top
        final_row = row_offset + 1
        self._layout.setRowStretch(final_row, 1)

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
