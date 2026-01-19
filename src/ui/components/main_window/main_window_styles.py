"""
Stylesheet definitions for MainWindow component.
"""

import src.ui.constants.colors as c
from src.ui.constants import Spacing, Typography
from src.ui.constants.dimensions import BORDER_RADIUS_LG, BORDER_RADIUS_SM

# About dialog styles
ABOUT_DIALOG_STYLE = f"""
    QDialog {{
        background-color: {c.GRAY_8};
        border-radius: {BORDER_RADIUS_LG}px;
    }}
    
    QLabel#aboutTitle {{
        font-size: {Typography.FONT_SIZE_HEADER}px;
        font-weight: {Typography.FONT_WEIGHT_BOLD};
        color: {c.GRAY_4};
        margin-bottom: {Spacing.MINOR_GAP}px;
    }}
    
    QLabel#aboutSubtitle {{
        font-size: {Typography.FONT_SIZE_LARGE}px;
        font-weight: {Typography.FONT_WEIGHT_MEDIUM};
        color: {c.GRAY_4};
    }}
    
    QLabel#aboutDescription {{
        font-size: {Typography.FONT_SIZE_BODY}px;
        color: {c.GRAY_4};
        line-height: 1.5;
    }}
    
    QLabel#aboutCreator {{
        font-size: {Typography.FONT_SIZE_BODY}px;
        font-weight: {Typography.FONT_WEIGHT_MEDIUM};
        color: {c.GRAY_4};
    }}
    
    QPushButton#secondaryButton {{
        background-color: {c.GRAY_7};
        color: {c.GRAY_4};
        border: 1px solid {c.GRAY_7};
        border-radius: {BORDER_RADIUS_SM}px;
        padding: {Spacing.BUTTON_PAD_V}px {Spacing.BUTTON_PAD_H}px;
        font-size: {Typography.FONT_SIZE_BODY}px;
        font-weight: {Typography.FONT_WEIGHT_MEDIUM};
        min-width: 120px;
    }}
    QPushButton#secondaryButton:hover {{
        background-color: {c.HOVER_OVERLAY_LIGHT};
        border-color: {c.GRAY_6};
    }}
    
    QPushButton#primaryButton {{
        background-color: {c.BLUE_4};
        color: {c.GRAY_0};
        border: none;
        border-radius: {BORDER_RADIUS_SM}px;
        padding: {Spacing.BUTTON_PAD_V}px {Spacing.BUTTON_PAD_H}px;
        font-size: {Typography.FONT_SIZE_BODY}px;
        font-weight: {Typography.FONT_WEIGHT_MEDIUM};
    }}
    QPushButton#primaryButton:hover {{
        background-color: {c.BLUE_3};
    }}
    QPushButton#primaryButton:pressed {{
        background-color: {c.BLUE_7};
    }}
"""

# Clear history dialog
CLEAR_DIALOG_STYLE = f"""
    QDialog {{
        background-color: {c.GRAY_8};
        border-radius: {BORDER_RADIUS_LG}px;
    }}
    
    QLabel {{
        font-size: {Typography.FONT_SIZE_BODY}px;
        color: {c.GRAY_4};
    }}
    
    QPushButton {{
        background-color: {c.GRAY_7};
        color: {c.GRAY_4};
        border: 1px solid {c.GRAY_7};
        border-radius: {BORDER_RADIUS_SM}px;
        padding: {Spacing.BUTTON_PAD_V}px {Spacing.BUTTON_PAD_H}px;
        font-size: {Typography.FONT_SIZE_BODY}px;
        min-width: 80px;
    }}
    QPushButton:hover {{
        background-color: {c.HOVER_OVERLAY_LIGHT};
    }}
    QPushButton:default {{
        border-color: {c.BLUE_4};
    }}
"""

# Main window container
MAIN_WINDOW_STYLE = f"""
    QMainWindow {{
        background-color: {c.GRAY_9};
        border: none;
        border-radius: 6px;
    }}
    
    QWidget#centralWidget {{
        background-color: transparent;
    }}
"""


def get_combined_stylesheet() -> str:
    """
    Return combined stylesheet for main window.
    """
    return MAIN_WINDOW_STYLE
