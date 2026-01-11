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
        background-color: {Colors.BACKGROUND};
    }}

    QLabel#groupDialogLabel {{
        color: {Colors.TEXT_PRIMARY};
        font-size: {Typography.FONT_SIZE_SM}px;
        font-weight: {Typography.FONT_WEIGHT_EMPHASIS};
    }}

    QLineEdit#groupNameInput {{
        background-color: {Colors.SURFACE};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER_DEFAULT};
        border-radius: 6px;
        padding: 10px 12px;
        font-size: {Typography.FONT_SIZE_SM}px;
    }}

    QLineEdit#groupNameInput:focus {{
        border-color: {Colors.PRIMARY};
    }}

    /* Error dialog styles */
    QDialog#errorDialog {{
        background-color: {Colors.BG_PRIMARY};
    }}

    QLabel#errorDialogMessage {{
        color: {Colors.TEXT_PRIMARY};
        font-size: {Typography.BODY_SIZE}pt;
        padding: 0px 4px;
    }}

    QLabel#errorDialogIcon {{
        color: {Colors.DESTRUCTIVE};
    }}

    QPushButton#errorDialogToggle {{
        background: transparent;
        color: {Colors.ACCENT_BLUE};
        border: none;
        font-size: {Typography.SMALL_SIZE}pt;
        padding: 4px 0px;
        text-align: left;
    }}

    QPushButton#errorDialogToggle:hover {{
        text-decoration: underline;
    }}

    QPlainTextEdit#errorDialogDetails {{
        background-color: {Colors.BG_TERTIARY};
        color: {Colors.TEXT_SECONDARY};
        border: 1px solid {Colors.BORDER_DEFAULT};
        border-radius: 4px;
        font-family: monospace;
        font-size: {Typography.SMALL_SIZE}pt;
        padding: 8px;
    }}

    QPushButton#errorDialogCopy {{
        background-color: {Colors.BG_TERTIARY};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER_DEFAULT};
        border-radius: 4px;
        padding: 4px 8px;
        font-size: {Typography.SMALL_SIZE}pt;
    }}

    QPushButton#errorDialogCopy:hover {{
        background-color: {Colors.HOVER_BG_ITEM};
    }}

    QPushButton#errorDialogViewLogs {{
        background-color: transparent;
        color: {Colors.ACCENT_BLUE};
        border: none;
        font-size: {Typography.SMALL_SIZE}pt;
        padding: 4px 0px;
    }}

    QPushButton#errorDialogViewLogs:hover {{
        text-decoration: underline;
    }}
"""
