"""
Key capture helper for hotkey rebinding.

Builds the on_key closure that accumulates modifier keys and finalizes
a chord string when a non-modifier key is pressed. Extracted from the
``/api/keycapture/start`` route handler.
"""

from __future__ import annotations

from collections.abc import Callable

from .types import InputEvent, KeyCode

MODIFIER_CODES: frozenset[KeyCode] = frozenset(
    {
        KeyCode.CTRL_LEFT,
        KeyCode.CTRL_RIGHT,
        KeyCode.SHIFT_LEFT,
        KeyCode.SHIFT_RIGHT,
        KeyCode.ALT_LEFT,
        KeyCode.ALT_RIGHT,
        KeyCode.META_LEFT,
        KeyCode.META_RIGHT,
    }
)

MODIFIER_LABELS: dict[KeyCode, str] = {
    KeyCode.CTRL_LEFT: "Ctrl",
    KeyCode.CTRL_RIGHT: "Ctrl",
    KeyCode.SHIFT_LEFT: "Shift",
    KeyCode.SHIFT_RIGHT: "Shift",
    KeyCode.ALT_LEFT: "Alt",
    KeyCode.ALT_RIGHT: "Alt",
    KeyCode.META_LEFT: "Meta",
    KeyCode.META_RIGHT: "Meta",
}


def make_capture_handler(
    *,
    on_chord: Callable[[str, str], None],
) -> Callable[[KeyCode, InputEvent], None]:
    """Create a key capture callback that accumulates a chord.

    Args:
        on_chord: Called with ``(combo, display)`` when the chord is finalized
            (i.e. a non-modifier key is pressed). ``combo`` is the raw form
            (e.g. ``"Alt+Ctrl+F5"``), ``display`` is the human-readable form
            (e.g. ``"Alt + Ctrl + F5"``).

    Returns:
        A callback suitable for :pymethod:`KeyListener.enable_capture_mode`.
    """
    captured_keys: set[str] = set()

    def on_key(key: KeyCode, event: InputEvent) -> None:
        if event not in {InputEvent.KEY_PRESS, InputEvent.MOUSE_PRESS}:
            return

        if key in MODIFIER_CODES:
            captured_keys.add(MODIFIER_LABELS[key])
        else:
            key_name = key.name.replace("_", " ").title().replace(" ", "_")
            parts = sorted(captured_keys) + [key.name]
            combo = "+".join(parts)
            display = " + ".join(sorted(captured_keys) + [key_name])
            captured_keys.clear()
            on_chord(combo, display)

    return on_key
