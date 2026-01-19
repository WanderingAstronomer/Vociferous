"""Keycode mapping utilities for hotkey display and configuration."""

from src.input_handler import KeyCode

# Display names for keys (user-facing)
KEY_DISPLAY_NAMES = {
    KeyCode.CTRL_LEFT: "Ctrl",
    KeyCode.CTRL_RIGHT: "Ctrl",
    KeyCode.SHIFT_LEFT: "Shift",
    KeyCode.SHIFT_RIGHT: "Shift",
    KeyCode.ALT_LEFT: "Alt",
    KeyCode.ALT_RIGHT: "Alt",
    KeyCode.META_LEFT: "Meta",
    KeyCode.META_RIGHT: "Meta",
    KeyCode.SPACE: "Space",
    KeyCode.ENTER: "Enter",
    KeyCode.TAB: "Tab",
    KeyCode.BACKSPACE: "Backspace",
    KeyCode.DELETE: "Delete",
    KeyCode.ESC: "Esc",
    # Letters
    KeyCode.A: "A",
    KeyCode.B: "B",
    KeyCode.C: "C",
    KeyCode.D: "D",
    KeyCode.E: "E",
    KeyCode.F: "F",
    KeyCode.G: "G",
    KeyCode.H: "H",
    KeyCode.I: "I",
    KeyCode.J: "J",
    KeyCode.K: "K",
    KeyCode.L: "L",
    KeyCode.M: "M",
    KeyCode.N: "N",
    KeyCode.O: "O",
    KeyCode.P: "P",
    KeyCode.Q: "Q",
    KeyCode.R: "R",
    KeyCode.S: "S",
    KeyCode.T: "T",
    KeyCode.U: "U",
    KeyCode.V: "V",
    KeyCode.W: "W",
    KeyCode.X: "X",
    KeyCode.Y: "Y",
    KeyCode.Z: "Z",
    # Numbers
    KeyCode.ZERO: "0",
    KeyCode.ONE: "1",
    KeyCode.TWO: "2",
    KeyCode.THREE: "3",
    KeyCode.FOUR: "4",
    KeyCode.FIVE: "5",
    KeyCode.SIX: "6",
    KeyCode.SEVEN: "7",
    KeyCode.EIGHT: "8",
    KeyCode.NINE: "9",
    # Function keys
    KeyCode.F1: "F1",
    KeyCode.F2: "F2",
    KeyCode.F3: "F3",
    KeyCode.F4: "F4",
    KeyCode.F5: "F5",
    KeyCode.F6: "F6",
    KeyCode.F7: "F7",
    KeyCode.F8: "F8",
    KeyCode.F9: "F9",
    KeyCode.F10: "F10",
    KeyCode.F11: "F11",
    KeyCode.F12: "F12",
}

# Config names for keys (lowercase for config file)
KEY_CONFIG_NAMES = {
    KeyCode.CTRL_LEFT: "ctrl",
    KeyCode.CTRL_RIGHT: "ctrl",
    KeyCode.SHIFT_LEFT: "shift",
    KeyCode.SHIFT_RIGHT: "shift",
    KeyCode.ALT_LEFT: "alt",
    KeyCode.ALT_RIGHT: "alt",
    KeyCode.META_LEFT: "meta",
    KeyCode.META_RIGHT: "meta",
    KeyCode.SPACE: "space",
    KeyCode.ENTER: "enter",
    KeyCode.TAB: "tab",
    KeyCode.BACKSPACE: "backspace",
    KeyCode.DELETE: "delete",
    KeyCode.ESC: "esc",
}

# Reverse mapping: config name -> KeyCode
REVERSE_KEY_MAP = {}
for key_code, config_name in KEY_CONFIG_NAMES.items():
    if config_name not in REVERSE_KEY_MAP:
        REVERSE_KEY_MAP[config_name] = key_code

# Add letter mappings
for letter in "abcdefghijklmnopqrstuvwxyz":
    key_code = getattr(KeyCode, letter.upper())
    REVERSE_KEY_MAP[letter] = key_code
    KEY_CONFIG_NAMES[key_code] = letter

# Add number mappings
number_names = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
]
for i, name in enumerate(number_names):
    key_code = getattr(KeyCode, name.upper())
    REVERSE_KEY_MAP[str(i)] = key_code
    KEY_CONFIG_NAMES[key_code] = str(i)


def keycodes_to_strings(keycodes: set[KeyCode]) -> tuple[str, str]:
    """
    Convert a set of keycodes to display and config strings.

    Args:
        keycodes: Set of KeyCode enums

    Returns:
        Tuple of (display_string, config_string)
        Display string uses capitalized names like "Ctrl+Shift+A"
        Config string uses lowercase like "ctrl+shift+a"
    """
    # Sort order: modifiers first (ctrl, shift, alt, meta), then regular keys
    modifier_order = {
        "ctrl": 0,
        "shift": 1,
        "alt": 2,
        "meta": 3,
    }

    display_parts = []
    config_parts = []

    for keycode in keycodes:
        display_name = KEY_DISPLAY_NAMES.get(keycode, keycode.name)
        config_name = KEY_CONFIG_NAMES.get(keycode, keycode.name.lower())

        display_parts.append(display_name)
        config_parts.append(config_name)

    # Sort by modifier order, then alphabetically
    config_parts.sort(key=lambda x: (modifier_order.get(x, 99), x))
    display_parts.sort(key=lambda x: (modifier_order.get(x.lower(), 99), x))

    return ("+".join(display_parts), "+".join(config_parts))


def normalize_hotkey_string(hotkey: str) -> str:
    """
    Normalize a hotkey string to canonical order.

    Args:
        hotkey: Hotkey string like "shift+ctrl+a"

    Returns:
        Normalized string like "ctrl+shift+a"
    """
    modifier_order = {
        "ctrl": 0,
        "shift": 1,
        "alt": 2,
        "meta": 3,
    }

    parts = hotkey.lower().split("+")
    parts.sort(key=lambda x: (modifier_order.get(x, 99), x))

    return "+".join(parts)
