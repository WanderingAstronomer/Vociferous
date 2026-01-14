"""
Stylesheet definitions for MainWindow component.
"""

from ui.constants import Colors, Dimensions, Spacing, Typography

# About dialog styles
ABOUT_DIALOG_STYLE = f"""
    QDialog {{
        background-color: {Colors.SURFACE};
        border-radius: {Dimensions.BORDER_RADIUS_LG}px;
    }}
    
    QLabel#aboutTitle {{
        font-size: {Typography.FONT_SIZE_HEADER}px;
        font-weight: {Typography.FONT_WEIGHT_BOLD};
        color: {Colors.TEXT_PRIMARY};
        margin-bottom: {Spacing.MINOR_GAP}px;
    }}
    
    QLabel#aboutSubtitle {{
        font-size: {Typography.FONT_SIZE_LARGE}px;
        font-weight: {Typography.FONT_WEIGHT_MEDIUM};
        color: {Colors.TEXT_SECONDARY};
    }}
    
    QLabel#aboutDescription {{
        font-size: {Typography.FONT_SIZE_BODY}px;
        color: {Colors.TEXT_SECONDARY};
        line-height: 1.5;
    }}
    
    QLabel#aboutCreator {{
        font-size: {Typography.FONT_SIZE_BODY}px;
        font-weight: {Typography.FONT_WEIGHT_MEDIUM};
        color: {Colors.TEXT_PRIMARY};
    }}
    
    QPushButton#secondaryButton {{
        background-color: {Colors.BUTTON_SECONDARY};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER_MEDIUM};
        border-radius: {Dimensions.BORDER_RADIUS_SM}px;
        padding: {Spacing.BUTTON_PAD_V}px {Spacing.BUTTON_PAD_H}px;
        font-size: {Typography.FONT_SIZE_BODY}px;
        font-weight: {Typography.FONT_WEIGHT_MEDIUM};
        min-width: 120px;
    }}
    QPushButton#secondaryButton:hover {{
        background-color: {Colors.HOVER_OVERLAY};
        border-color: {Colors.BORDER_LIGHT};
    }}
    
    QPushButton#primaryButton {{
        background-color: {Colors.PRIMARY};
        color: {Colors.TEXT_ON_PRIMARY};
        border: none;
        border-radius: {Dimensions.BORDER_RADIUS_SM}px;
        padding: {Spacing.BUTTON_PAD_V}px {Spacing.BUTTON_PAD_H}px;
        font-size: {Typography.FONT_SIZE_BODY}px;
        font-weight: {Typography.FONT_WEIGHT_MEDIUM};
    }}
    QPushButton#primaryButton:hover {{
        background-color: {Colors.PRIMARY_HOVER};
    }}
    QPushButton#primaryButton:pressed {{
        background-color: {Colors.PRIMARY_PRESSED};
    }}
"""

# Clear history dialog
CLEAR_DIALOG_STYLE = f"""
    QDialog {{
        background-color: {Colors.SURFACE};
        border-radius: {Dimensions.BORDER_RADIUS_LG}px;
    }}
    
    QLabel {{
        font-size: {Typography.FONT_SIZE_BODY}px;
        color: {Colors.TEXT_PRIMARY};
    }}
    
    QPushButton {{
        background-color: {Colors.BUTTON_SECONDARY};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER_MEDIUM};
        border-radius: {Dimensions.BORDER_RADIUS_SM}px;
        padding: {Spacing.BUTTON_PAD_V}px {Spacing.BUTTON_PAD_H}px;
        font-size: {Typography.FONT_SIZE_BODY}px;
        min-width: 80px;
    }}
    QPushButton:hover {{
        background-color: {Colors.HOVER_OVERLAY};
    }}
    QPushButton:default {{
        border-color: {Colors.PRIMARY};
    }}
"""

# Main window container
MAIN_WINDOW_STYLE = f"""
    QMainWindow {{
        background-color: {Colors.BACKGROUND};
    }}
    
    QWidget#centralWidget {{
        background-color: {Colors.BACKGROUND};
    }}
"""


def get_combined_stylesheet() -> str:
    """
    Return combined stylesheet for main window.
    """
    return MAIN_WINDOW_STYLE
