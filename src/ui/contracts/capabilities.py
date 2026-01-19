from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable


class ActionId(StrEnum):
    """Standardized action identifiers for view operations."""

    EDIT = "EDIT"
    REFINE = "REFINE"
    DELETE = "DELETE"
    MOVE_TO_PROJECT = "MOVE_TO_PROJECT"
    COPY = "COPY"
    VIEW_PREVIEW = "VIEW_PREVIEW"
    EXPORT = "EXPORT"
    DISCARD = "DISCARD"
    SAVE = "SAVE"
    CANCEL = "CANCEL"
    # Invariant-required actions
    START_RECORDING = "START_RECORDING"
    STOP_RECORDING = "STOP_RECORDING"
    CREATE_PROJECT = "CREATE_PROJECT"


@dataclass(slots=True, frozen=True)
class SelectionState:
    """Represents the current selection within a view."""

    selected_ids: tuple[int, ...] = field(default_factory=tuple)
    primary_id: int | None = None

    @property
    def has_selection(self) -> bool:
        """Return True if any items are selected."""
        return bool(self.selected_ids)

    @property
    def is_single_selection(self) -> bool:
        """Return True if exactly one item is selected."""
        return len(self.selected_ids) == 1


@dataclass(slots=True, frozen=True)
class Capabilities:
    """Declared capabilities of a view/state."""

    can_edit: bool = False
    can_refine: bool = False
    can_delete: bool = False
    can_move_to_project: bool = False
    can_copy: bool = False
    can_preview: bool = False
    can_export: bool = False
    can_save: bool = False
    can_discard: bool = False
    can_cancel: bool = False
    can_start_recording: bool = False
    can_stop_recording: bool = False
    can_create_project: bool = False


@runtime_checkable
class ViewInterface(Protocol):
    """Protocol for all unified Main Views."""

    def get_capabilities(self) -> Capabilities:
        """Return the current capabilities of the view."""
        ...

    def get_selection(self) -> SelectionState:
        """Return the current selection state."""
        ...

    def dispatch_action(self, action_id: ActionId) -> None:
        """Execute a standard action."""
        ...

    def get_view_id(self) -> str:
        """Return the unique identifier for this view."""
        ...
