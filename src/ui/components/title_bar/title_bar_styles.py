"""
Title bar styles.
"""

import src.ui.constants.colors as c
from src.ui.constants.dimensions import BORDER_RADIUS_SMALL


def get_title_bar_styles() -> str:
    """
    Generate stylesheet for title bar components.

    Returns:
        QSS stylesheet string.
    """
    return f"""
        /* Main window title bar */
        QWidget#titleBar {{
            background-color: {c.GRAY_9};

        }}

        QLabel#titleBarLabel {{
            color: {c.GRAY_4};
            font-weight: 600;
        }}

        /* Title bar control buttons */
        QToolButton#titleBarControl {{
            background-color: transparent;
            border: none;
            border-radius: {BORDER_RADIUS_SMALL}px;
        }}

        QToolButton#titleBarControl:hover {{
            background-color: {c.GRAY_7};
        }}

        QToolButton#titleBarControl:pressed {{
            background-color: {c.GRAY_7};
        }}

        /* Close button */
        QToolButton#titleBarClose {{
            background-color: transparent;
            border: none;
            border-radius: {BORDER_RADIUS_SMALL}px;
        }}

        QToolButton#titleBarClose:hover {{
            background-color: {c.RED_5};
        }}

        QToolButton#titleBarClose:pressed {{
            background-color: {c.RED_7};
        }}

        /* Dialog title bar */
        QWidget#dialogTitleBar {{
            background-color: {c.GRAY_9};
            border-bottom: 1px solid {c.GRAY_7};
        }}

        QLabel#dialogTitleLabel {{
            color: {c.GRAY_4};
            font-weight: 600;
        }}
    """
