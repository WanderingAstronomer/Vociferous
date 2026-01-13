"""
Deprecated: Use src.input_handler instead.
This module is kept for backward compatibility.
"""
from input_handler import (
    EvdevBackend,
    InputBackend,
    InputEvent,
    KeyChord,
    KeyCode,
    KeyListener,
    PynputBackend,
)

__all__ = [
    "EvdevBackend",
    "InputBackend",
    "InputEvent",
    "KeyChord",
    "KeyCode",
    "KeyListener",
    "PynputBackend",
]
