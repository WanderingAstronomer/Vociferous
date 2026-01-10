"""
Workspace component styles.
"""

from ui.constants import Colors, Dimensions, Spacing, Typography


def get_workspace_styles() -> str:
    """
    Generate stylesheet for workspace components.

    Returns:
        QSS stylesheet string.
    """
    return f"""
        /* Main workspace container */
        QWidget#mainWorkspace {{
            background-color: {Colors.BG_PRIMARY};
        }}

        /* Greeting label states */
        QLabel#greetingLabel {{
            color: {Colors.TEXT_PRIMARY};
        }}

        QLabel#greetingLabel[state="recording"] {{
            color: {Colors.ACCENT_RECORDING};
        }}

        QLabel#greetingLabel[state="transcribing"] {{
            color: {Colors.ACCENT_RECORDING};
        }}

        /* Subtext label */
        QLabel#subtextLabel {{
            color: {Colors.TEXT_SECONDARY};
        }}

        /* Hotkey hint */
        QLabel#hotkeyHint {{
            color: {Colors.TEXT_TERTIARY};
            font-size: {Typography.SMALL_SIZE}pt;
        }}

        /* Content label */
        QLabel#contentLabel {{
            color: {Colors.TEXT_SECONDARY};
        }}

        /* Transcript view */
        QLabel#transcriptView {{
            color: {Colors.TEXT_PRIMARY};
            font-size: {Typography.BODY_SIZE}pt;
            background-color: transparent;
        }}

        /* Transcript editor */
        QTextEdit#transcriptEditor {{
            background-color: {Colors.BG_TERTIARY};
            color: {Colors.TEXT_PRIMARY};
            font-size: {Typography.BODY_SIZE}pt;
            border: none;
            border-radius: 4px;
        }}

        /* Scroll area */
        QScrollArea#workspaceScrollArea {{
            background-color: transparent;
            border: none;
        }}

        QScrollArea#workspaceScrollArea > QWidget {{
            background-color: transparent;
        }}

        /* Workspace content - transparent to show ContentPanel background */
        QWidget#workspaceContent {{
            background-color: transparent;
        }}

        /* Stacked widget inside content - dark background for all pages */
        QStackedWidget {{
            background-color: {Colors.BG_TERTIARY};
        }}

        /* Text browser and editor - dark background */
        QTextBrowser#transcriptView,
        QTextEdit#transcriptEditor {{
            background-color: {Colors.BG_TERTIARY};
            color: {Colors.TEXT_PRIMARY};
            border: none;
        }}

        /* Text browser and editor viewport - dark background */
        QTextBrowser#transcriptView > QWidget,
        QTextEdit#transcriptEditor > QWidget {{
            background-color: {Colors.BG_TERTIARY};
        }}

        /* Content label - transparent to show stacked widget background */
        QLabel#contentLabel {{
            background-color: transparent;
            color: {Colors.TEXT_SECONDARY};
        }}

        /* Primary button */
        QPushButton#primaryButton {{
            background-color: {Colors.ACCENT_PRIMARY};
            color: {Colors.TEXT_ON_ACCENT};
            border: none;
            border-radius: {Dimensions.BORDER_RADIUS}px;
            font-size: {Typography.BODY_SIZE}pt;
            font-weight: 600;
            padding: 0 {Spacing.BUTTON_PADDING}px;
        }}

        QPushButton#primaryButton:hover {{
            background-color: {Colors.ACCENT_HOVER};
        }}

        QPushButton#primaryButton:pressed {{
            background-color: {Colors.ACCENT_PRESSED};
        }}

        QPushButton#primaryButton:disabled {{
            background-color: {Colors.BG_TERTIARY};
            color: {Colors.TEXT_TERTIARY};
        }}

        /* Secondary button */
        QPushButton#secondaryButton {{
            background-color: {Colors.BG_TERTIARY};
            color: {Colors.TEXT_PRIMARY};
            border: 1px solid {Colors.BORDER_COLOR};
            border-radius: {Dimensions.BORDER_RADIUS}px;
            font-size: {Typography.BODY_SIZE}pt;
            padding: 0 {Spacing.BUTTON_PADDING}px;
        }}

        QPushButton#secondaryButton:hover {{
            background-color: {Colors.HOVER_BG_ITEM};
        }}

        /* Destructive button */
        QPushButton#destructiveButton {{
            background-color: transparent;
            color: {Colors.ACCENT_DESTRUCTIVE};
            border: 1px solid {Colors.ACCENT_DESTRUCTIVE};
            border-radius: {Dimensions.BORDER_RADIUS}px;
            font-size: {Typography.BODY_SIZE}pt;
            padding: 0 {Spacing.BUTTON_PADDING}px;
        }}

        QPushButton#destructiveButton:hover {{
            background-color: rgba(231, 76, 60, 0.1);
        }}
    """
