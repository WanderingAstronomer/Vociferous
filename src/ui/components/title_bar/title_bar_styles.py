"""
Title bar styles.
"""

from ui.constants import Colors, Dimensions


def get_title_bar_styles() -> str:
    """
    Generate stylesheet for title bar components.

    Returns:
        QSS stylesheet string.
    """
    return f"""
        /* Main window title bar */
        QWidget#titleBar {{
            background-color: {Colors.BG_HEADER};
            border-bottom: 1px solid {Colors.BORDER_COLOR};
        }}

        QLabel#titleBarLabel {{
            color: {Colors.TEXT_PRIMARY};
            font-weight: 600;
        }}

        /* Title bar control buttons */
        QToolButton#titleBarControl {{
            background-color: transparent;
            border: none;
            border-radius: {Dimensions.BORDER_RADIUS_SMALL}px;
        }}

        QToolButton#titleBarControl:hover {{
            background-color: {Colors.HOVER_BG_ITEM};
        }}

        QToolButton#titleBarControl:pressed {{
            background-color: {Colors.HOVER_BG_SECTION};
        }}

        /* Close button */
        QToolButton#titleBarClose {{
            background-color: transparent;
            border: none;
            border-radius: {Dimensions.BORDER_RADIUS_SMALL}px;
        }}

        QToolButton#titleBarClose:hover {{
            background-color: {Colors.ACCENT_DESTRUCTIVE};
        }}

        QToolButton#titleBarClose:pressed {{
            background-color: {Colors.DESTRUCTIVE_PRESSED};
        }}

        /* Dialog title bar */
        QWidget#dialogTitleBar {{
            background-color: {Colors.BG_HEADER};
            border-bottom: 1px solid {Colors.BORDER_COLOR};
        }}

        QLabel#dialogTitleLabel {{
            color: {Colors.TEXT_PRIMARY};
            font-weight: 600;
        }}
    """
