"""
Styles for HotkeyWidget.

QSS rules for hotkey input field and validation label.
"""

from ui.constants import Colors

HOTKEY_WIDGET_STYLESHEET = f"""
    /* Hotkey input field */
    QLineEdit#hotkeyInput {{
        background-color: {Colors.BG_SECONDARY};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER_DEFAULT};
        border-radius: 6px;
        padding: 8px 12px;
    }}

    QLineEdit#hotkeyInput:focus {{
        border-color: {Colors.ACCENT_BLUE};
    }}

    QLineEdit#hotkeyInput[invalid="true"] {{
        border: 1px solid {Colors.DESTRUCTIVE};
    }}

    /* Validation error label */
    QLabel#hotkeyValidation {{
        color: {Colors.DESTRUCTIVE};
    }}
"""
