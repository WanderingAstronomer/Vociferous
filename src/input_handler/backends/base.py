from collections.abc import Callable
from typing import Protocol, runtime_checkable

from ..types import InputEvent, KeyCode


@runtime_checkable
class InputBackend(Protocol):
    """Protocol defining the interface for input backends."""

    on_input_event: Callable[[tuple[KeyCode, InputEvent]], None] | None

    @classmethod
    def is_available(cls) -> bool:
        """Check if this backend is available on the current system."""
        ...

    def start(self) -> None:
        """Start listening for input events."""
        ...

    def stop(self) -> None:
        """Stop listening and clean up resources."""
        ...
