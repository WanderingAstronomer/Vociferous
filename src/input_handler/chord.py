from dataclasses import dataclass, field

from .types import InputEvent, KeyCode


@dataclass(slots=True)
class KeyChord:
    """
    Represents a hotkey combination (e.g., Ctrl+Shift+Space).

    keys can contain KeyCode for specific keys, or frozenset[KeyCode]
    for "any of these" (e.g., either Ctrl key).
    """

    keys: set[KeyCode | frozenset[KeyCode]]
    pressed_keys: set[KeyCode] = field(default_factory=set)

    def update(self, key: KeyCode, event_type: InputEvent) -> bool:
        """Update the state of pressed keys and check if the chord is active."""
        match event_type:
            case InputEvent.KEY_PRESS:
                self.pressed_keys.add(key)
            case InputEvent.KEY_RELEASE:
                self.pressed_keys.discard(key)
        return self.is_active()

    def is_active(self) -> bool:
        """Check if all keys in the chord are currently pressed."""
        return all(
            any(k in self.pressed_keys for k in key)
            if isinstance(key, frozenset)
            else key in self.pressed_keys
            for key in self.keys
        )
