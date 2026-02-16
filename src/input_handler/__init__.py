from collections.abc import Callable

from .backends.base import InputBackend
from .backends.evdev import EvdevBackend
from .backends.pynput import PynputBackend
from .chord import KeyChord
from .listener import KeyListener
from .types import InputEvent, KeyCode

__all__ = [
    "EvdevBackend",
    "InputBackend",
    "InputEvent",
    "KeyChord",
    "KeyCode",
    "KeyListener",
    "PynputBackend",
    "create_listener",
]


def create_listener(
    callback: Callable[[], None],
    deactivate_callback: Callable[[], None] | None = None,
    activation_key: str | None = None,
    backend: str | None = None,
) -> KeyListener:
    """
    Factory: create a KeyListener, wire the activation callback, and start it.

    Args:
        callback: Function to call when the activation hotkey is pressed.
        deactivate_callback: Function to call when the activation hotkey is released
            (needed for hold-to-record mode).
        activation_key: Override for the activation key (uses settings default if None).
        backend: Override for the input backend (uses settings default if None).

    Returns:
        A running KeyListener instance.
    """
    listener = KeyListener()
    listener.add_callback("on_activate", callback)
    if deactivate_callback is not None:
        listener.add_callback("on_deactivate", deactivate_callback)

    # Override activation key if provided
    if activation_key is not None:
        keys = listener.parse_key_combination(activation_key)
        listener.set_activation_keys(keys)

    listener.start()
    return listener
