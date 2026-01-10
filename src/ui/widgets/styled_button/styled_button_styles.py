"""
Styles for StyledButton widget.

QSS rules for primary, secondary, and destructive button styles.
"""

from ui.constants import BUTTON_RADIUS_RECT, Colors

STYLED_BUTTON_STYLESHEET = f"""
    /* Primary button style */
    QPushButton#styledPrimary {{
        background-color: {Colors.ACCENT_BLUE};
        color: {Colors.BG_PRIMARY};
        border: none;
        border-radius: {BUTTON_RADIUS_RECT}px;
        padding: 10px 24px;
        font-weight: bold;
    }}

    QPushButton#styledPrimary:hover {{
        background-color: {Colors.ACCENT_BLUE_HOVER};
    }}

    QPushButton#styledPrimary:disabled {{
        background-color: {Colors.BG_HEADER};
        color: {Colors.TEXT_SECONDARY};
    }}

    /* Secondary button style */
    QPushButton#styledSecondary {{
        background-color: {Colors.BG_TERTIARY};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER_DEFAULT};
        border-radius: {BUTTON_RADIUS_RECT}px;
        padding: 10px 24px;
    }}

    QPushButton#styledSecondary:hover {{
        background-color: {Colors.HOVER_BG};
        border-color: {Colors.ACCENT_BLUE};
        color: {Colors.TEXT_ACCENT};
    }}

    /* Destructive button style */
    QPushButton#styledDestructive {{
        background-color: {Colors.BG_TERTIARY};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER_DEFAULT};
        border-radius: {BUTTON_RADIUS_RECT}px;
        padding: 10px 24px;
    }}

    QPushButton#styledDestructive:hover {{
        background-color: {Colors.DESTRUCTIVE_HOVER};
        color: {Colors.DESTRUCTIVE};
        border-color: {Colors.DESTRUCTIVE};
    }}
"""
