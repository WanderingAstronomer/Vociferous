"""
Styles for dialog widgets.

QSS rules for dialog containers, labels, inputs, and button containers.
"""

from ui.constants import (
    STANDARD_RADIUS,
    Colors,
    Typography,
)

DIALOG_STYLESHEET = f"""
    /* Dialog container */
    QWidget#dialogContainer {{
        background-color: {Colors.BG_PRIMARY};
        border: 1px solid {Colors.BORDER_ACCENT};
        border-radius: {STANDARD_RADIUS}px;
    }}

    /* Dialog button container - bottom row with background */
    QWidget#dialogButtonContainer {{
        background-color: {Colors.BG_SECONDARY};
        border-top: 1px solid {Colors.BORDER_DEFAULT};
        border-bottom-left-radius: 8px;
        border-bottom-right-radius: 8px;
    }}

    /* Dialog labels */
    QLabel#dialogLabel {{
        color: {Colors.TEXT_PRIMARY};
        font-size: {Typography.BODY_SIZE}pt;
    }}

    /* Muted dialog label (for hints/previews) */
    QLabel#dialogLabelMuted {{
        color: {Colors.TEXT_SECONDARY};
        font-size: {Typography.SMALL_SIZE}pt;
        font-style: italic;
    }}

    /* Dialog input fields */
    QLineEdit#dialogInput {{
        background-color: {Colors.BG_SECONDARY};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER_DEFAULT};
        border-radius: 6px;
        padding: 8px 12px;
        font-size: {Typography.BODY_SIZE}pt;
    }}

    QLineEdit#dialogInput:focus {{
        border-color: {Colors.ACCENT_BLUE};
    }}

    /* Create group dialog */
    QDialog#createGroupDialog {{
        background-color: {Colors.BG_PRIMARY};
    }}

    QLabel#groupDialogLabel {{
        color: {Colors.TEXT_PRIMARY};
        font-size: 14px;
        font-weight: 500;
    }}

    QLineEdit#groupNameInput {{
        background-color: {Colors.BG_SECONDARY};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER_DEFAULT};
        border-radius: 6px;
        padding: 10px 12px;
        font-size: 14px;
    }}

    QLineEdit#groupNameInput:focus {{
        border-color: {Colors.ACCENT_BLUE};
    }}
"""
