from src.ui.constants import (
    Spacing,
    Typography,
    CONTENT_PANEL_RADIUS,
)
import src.ui.constants.colors as c
from src.ui.constants.dimensions import BORDER_RADIUS_LG, BORDER_RADIUS_SMALL


def get_unified_stylesheet() -> str:
    return f"""
/* =================================================================
   TABLE OF CONTENTS
   =================================================================
   1.  GLOBAL DEFAULTS
   2.  SCROLLBARS
   3.  CONTAINERS & PANELS
   4.  BUTTONS
   5.  DIALOGS
   6.  TITLE BAR
   7.  SHELL COMPONENTS
   8.  VIEWS
   9.  HOTKEY WIDGET
   10. ONBOARDING
   11. TREE & TABLE VIEWS
   ================================================================= */

/* =================================================================
   GLOBAL DEFAULTS
   ================================================================= */

QMainWindow {{
    background-color: {c.GRAY_9};
    border: none;
    border-radius: 0 0 6px 6px;
}}

QWidget {{
    background-color: transparent;
    color: {c.GRAY_3};
}}

#centralWidget {{
    background-color: {c.GRAY_9};
    border-radius: 6px;
}}

/* =================================================================
   SCROLLBARS
   ================================================================= */

QScrollBar:vertical {{
    background-color: transparent;
    width: 10px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background-color: {c.BLUE_4};
    border-radius: 5px;
    min-height: 20px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {c.BLUE_3};
}}

QScrollBar::handle:vertical:pressed {{
    background-color: {c.BLUE_6};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    background: none;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 10px;
    margin: 0px;
}}

QScrollBar::handle:horizontal {{
    background-color: {c.BLUE_4};
    border-radius: 5px;
    min-width: 20px;
    margin: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {c.BLUE_3};
}}

QScrollBar::handle:horizontal:pressed {{
    background-color: {c.BLUE_6};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
    background: none;
}}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
}}

/* =================================================================
   CONTAINERS & PANELS
   ================================================================= */

/* Search/Transcript Preview Overlay */
QFrame#previewOverlay {{
    background-color: {c.SHELL_BACKGROUND};
    border: 2px solid {c.BLUE_4};
    border-radius: {BORDER_RADIUS_LG}px;
}}

QFrame#contentPanelPainted {{
    background: transparent;
    border: none;
}}

QWidget#contentPanel,
QFrame#contentPanel {{
    background-color: {c.CONTENT_BACKGROUND};
    border: 1px solid {c.CONTENT_BORDER};
    border-radius: {CONTENT_PANEL_RADIUS}px;
}}

QFrame#contentPanel[editing="true"] {{
    border: 3px solid {c.BLUE_4};
}}

QFrame#contentPanel[recording="true"] {{
    background-color: transparent;
    border: none;
}}

/* =================================================================
   BUTTONS
   ================================================================= */

QPushButton {{
    outline: none;
}}

QPushButton[styleClass="primaryButton"] {{
    background-color: {c.BLUE_4};
    color: {c.GRAY_0};
    border: none;
    border-radius: {BORDER_RADIUS_LG}px;
    font-size: 16px;
    font-weight: {Typography.FONT_WEIGHT_EMPHASIS};
    padding: 8px {Spacing.S4}px;
    min-width: 100px;
    min-height: 44px;
}}

QPushButton[styleClass="primaryButton"]:hover {{
    background-color: {c.BLUE_3};
}}

QPushButton[styleClass="primaryButton"]:pressed {{
    background-color: {c.BLUE_6};
}}

QPushButton[styleClass="primaryButton"]:focus {{
    background-color: {c.BLUE_3};
}}

QPushButton[styleClass="primaryButton"]:disabled {{
    background-color: {c.GRAY_7};
    color: {c.GRAY_4};
}}

QPushButton[styleClass="secondaryButton"] {{
    background-color: transparent;
    color: {c.GRAY_0};
    border: 1px solid {c.GRAY_6};
    border-radius: {BORDER_RADIUS_LG}px;
    font-size: 16px;
    font-weight: {Typography.FONT_WEIGHT_NORMAL};
    padding: 8px {Spacing.S4}px;
    min-width: 100px;
    min-height: 44px;
}}

QPushButton[styleClass="secondaryButton"]:hover {{
    background-color: {c.GRAY_7};
    border-color: {c.BLUE_4};
    color: {c.BLUE_3};
}}

QPushButton[styleClass="secondaryButton"]:focus {{
    border-color: {c.BLUE_4};
    color: {c.BLUE_3};
}}

QPushButton[styleClass="destructiveButton"] {{
    background-color: transparent;
    color: {c.RED_5};
    border: 1px solid {c.RED_5};
    border-radius: {BORDER_RADIUS_LG}px;
    font-size: 16px;
    font-weight: {Typography.FONT_WEIGHT_NORMAL};
    padding: 8px {Spacing.S4}px;
    min-width: 100px;
    min-height: 44px;
}}

QPushButton[styleClass="destructiveButton"]:hover {{
    background-color: {c.RED_9};
    color: {c.GRAY_0};
    border-color: {c.RED_5};
}}

QPushButton[styleClass="destructiveButton"]:focus {{
    border-color: {c.RED_4};
}}

QPushButton[styleClass="purpleButton"] {{
    background-color: transparent;
    color: {c.PURPLE_5};
    border: 1px solid {c.PURPLE_5};
    border-radius: {BORDER_RADIUS_LG}px;
    font-size: 16px;
    font-weight: {Typography.FONT_WEIGHT_NORMAL};
    padding: 8px {Spacing.S4}px;
    min-width: 100px;
    min-height: 44px;
}}

QPushButton[styleClass="purpleButton"]:hover {{
    background-color: {c.PURPLE_9};
    color: {c.GRAY_0};
    border-color: {c.PURPLE_5};
}}

QPushButton[styleClass="purpleButton"]:focus {{
    border-color: {c.PURPLE_4};
}}

/* =================================================================
   INPUT FIELDS (Combo, Text, Spin)
   ================================================================= */

QComboBox {{
    combobox-popup: 0;
    background-color: {c.GRAY_9};
    color: {c.GRAY_4}; /* Text color should be legible */
    border: 1px solid {c.GRAY_7};
    border-radius: 6px;
    padding: 6px 12px;
    min-height: 24px;
}}

QComboBox:hover {{
    border-color: {c.BLUE_4};
    color: {c.GRAY_0};
}}

QComboBox:on {{
    border-bottom-left-radius: 0px;
    border-bottom-right-radius: 0px;
    border-bottom: none;
}}

QComboBox::drop-down {{
    border: none;
    background: transparent;
    width: 24px;
    margin-right: 4px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid {c.GRAY_4};
    width: 0px;
    height: 0px;
    margin: 0px;
}}

QComboBox QAbstractItemView {{
    background-color: {c.GRAY_9};
    border: 1px solid {c.GRAY_7};
    border-top: none;
    selection-background-color: {c.BLUE_4};
    selection-color: {c.GRAY_0};
    outline: none;
    padding: 0px;
}}

QComboBox QAbstractItemView::item {{
    padding: 6px 12px;
    background-color: transparent;
    color: {c.GRAY_3};
}}

QComboBox QAbstractItemView::item:selected {{
    background-color: {c.BLUE_4};
    color: {c.GRAY_0};
}}

QComboBox QAbstractItemView::item:hover {{
    background-color: {c.BLUE_3};
    color: {c.GRAY_0};
}}

/* =================================================================
   DIALOGS
   ================================================================= */

QDialog {{
    background-color: transparent;
    border: none;
}}

QFrame#dialogFrame {{
    background-color: {c.GRAY_9};
    border: 3px solid {c.BLUE_4};
    border-radius: 0px;
}}

/* Dialog container - no border (border is on QFrame) */
QWidget#dialogContainer {{
    background-color: {c.GRAY_9};
}}

/* Dialog button container - bottom row with background */
QWidget#dialogButtonContainer {{
    background-color: {c.GRAY_9};
    border-top: 1px solid {c.GRAY_7};
    border-bottom-left-radius: 8px;
    border-bottom-right-radius: 8px;
}}

/* Dialog labels */
QLabel#dialogLabel {{
    color: {c.GRAY_4};
    font-size: {Typography.BODY_SIZE}pt;
    border: none;
}}

/* Muted dialog label (for hints/previews) */
QLabel#dialogLabelMuted {{
    color: {c.GRAY_4};
    font-size: {Typography.SMALL_SIZE}pt;
    font-style: italic;
}}

/* Dialog input fields */
QLineEdit#dialogInput {{
    background-color: {c.GRAY_9};
    color: {c.GRAY_4};
    border: 1px solid {c.GRAY_7};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: {Typography.BODY_SIZE}pt;
}}

QLineEdit#dialogInput:focus {{
    border-color: {c.BLUE_4};
}}

/* Create project dialog */
QDialog#createProjectDialog {{
    background-color: {c.GRAY_9};
}}

QLabel#dialogLabel {{
    color: {c.GRAY_4};
    font-size: {Typography.FONT_SIZE_SM}px;
    font-weight: {Typography.FONT_WEIGHT_EMPHASIS};
}}

QLineEdit#projectNameInput {{
    background-color: {c.GRAY_9};
    color: {c.GRAY_4};
    border: 1px solid {c.GRAY_7};
    border-radius: 6px;
    padding: 10px 12px;
    font-size: {Typography.FONT_SIZE_SM}px;
}}

QLineEdit#projectNameInput:focus {{
    border-color: {c.BLUE_4};
}}

/* Error dialog styles */
QDialog#errorDialog {{
    background-color: {c.GRAY_9};
}}

QLabel#errorDialogMessage {{
    color: {c.GRAY_4};
    font-size: {Typography.BODY_SIZE}pt;
    padding: 0px 4px;
}}

QLabel#errorDialogIcon {{
    color: {c.RED_5};
}}

QPushButton#errorDialogToggle {{
    background: transparent;
    color: {c.BLUE_4};
    border: none;
    font-size: {Typography.SMALL_SIZE}pt;
    padding: 4px 0px;
    text-align: left;
}}

QPushButton#errorDialogToggle:hover {{
    text-decoration: underline;
}}

QPlainTextEdit#errorDialogDetails {{
    background-color: {c.GRAY_9};
    color: {c.GRAY_4};
    border: 1px solid {c.GRAY_7};
    border-radius: 4px;
    font-family: monospace;
    font-size: {Typography.SMALL_SIZE}pt;
    padding: 8px;
}}

QPushButton#errorDialogCopy {{
    background-color: {c.GRAY_9};
    color: {c.GRAY_4};
    border: 1px solid {c.GRAY_7};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: {Typography.SMALL_SIZE}pt;
}}

QPushButton#errorDialogCopy:hover {{
    background-color: {c.GRAY_7};
}}

QPushButton#errorDialogViewLogs {{
    background-color: transparent;
    color: {c.BLUE_4};
    border: none;
    font-size: {Typography.SMALL_SIZE}pt;
    padding: 4px 0px;
}}

QPushButton#errorDialogViewLogs:hover {{
    text-decoration: underline;
}}

/* =================================================================
   TITLE BAR
   ================================================================= */

QWidget#titleBar {{
    background-color: {c.SHELL_BACKGROUND};
    border-bottom: 1px solid {c.BLUE_3};
}}

QLabel#titleBarLabel {{
    color: {c.GRAY_0};
    font-size: {Typography.TITLE_BAR_SIZE}px;
    font-weight: 600;
}}

QToolButton#titleBarControl {{
    background-color: transparent;
    border: none;
    border-radius: {BORDER_RADIUS_SMALL}px;
}}

QToolButton#titleBarControl:hover {{
    background-color: {c.GRAY_5};
}}

QToolButton#titleBarControl:pressed {{
    background-color: {c.GRAY_4};
}}

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

QWidget#dialogTitleBar {{
    background-color: {c.GRAY_9};
    border-bottom: 1px solid {c.GRAY_6};
}}

QLabel#dialogTitleLabel {{
    color: {c.GRAY_0};
    font-weight: 600;
}}

/* =================================================================
   SHELL COMPONENTS
   ================================================================= */

IconRail {{
    background-color: {c.BLUE_9};
    border: 1px solid {c.SHELL_BORDER};
    border-radius: 12px;
    min-width: 120px;
    max-width: 120px;
    margin: 20px 10px;
}}

IconRail QToolButton {{
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 10px 6px;
    margin: 0px;
    color: {c.GRAY_2};
    font-size: 13px;
    font-weight: 600;
}}

IconRail QToolButton:hover {{
    background-color: {c.GRAY_8};
    color: {c.GRAY_0};
}}

IconRail QToolButton:checked {{
    background-color: {c.GRAY_8};
    border-left: 6px solid {c.BLUE_4};
    border-radius: 8px;
    color: {c.BLUE_4};
}}

IconRail QToolButton[blink="active"] {{
    background-color: {c.GRAY_7};
    border-left: 6px solid {c.BLUE_3};
}}

ActionDock {{
    background-color: transparent;
    border-bottom: 1px solid {c.GRAY_6};
}}

QFrame#actionDockSeparator {{
    background-color: {c.GRAY_6};
    border: none;
    max-height: 1px;
}}

ActionDock QPushButton {{
    background-color: transparent;
    color: {c.GRAY_0};
    border: 1px solid {c.GRAY_6};
    border-radius: 4px;
    padding: 12px 16px;
    font-size: 13px;
    font-weight: 500;
    margin: 2px 4px;
    min-height: 48px;
}}

ActionDock QPushButton:hover {{
    background-color: {c.GRAY_7};
    border-color: {c.BLUE_4};
}}

ActionDock QPushButton:pressed {{
    background-color: {c.BLUE_6};
}}

ActionDock QPushButton#btn_START_RECORDING {{
    color: {c.GRAY_0};
}}

ActionDock QPushButton#btn_STOP_RECORDING {{
    color: {c.RED_5};
}}

ActionDock QPushButton#btn_CANCEL:hover {{
    background-color: {c.RED_5};
    color: {c.GRAY_0};
    border-color: {c.RED_5};
}}

QStatusBar {{
    background: {c.GRAY_9};
    color: {c.GRAY_2};
    border-top: 1px solid {c.GRAY_6};
    padding: 4px 8px;
}}

/* Batch Status Footer */
QWidget#batchStatusFooter {{
    background-color: {c.GRAY_9};
    border-top: 1px solid {c.BLUE_7};
}}

QLabel#batchStatusLabel {{
    color: {c.BLUE_2};
    font-size: {Typography.FONT_SIZE_XS}px;
    font-weight: {Typography.FONT_WEIGHT_EMPHASIS};
}}

/* Metrics Strip */
QWidget#metricsStrip {{
    background-color: transparent;
}}

QLabel#metricsToggle {{
    color: {c.GRAY_4};
    font-size: {Typography.FONT_SIZE_SM}px;
    font-weight: {Typography.FONT_WEIGHT_MEDIUM};
    qproperty-alignment: 'AlignCenter';
}}

QLabel#metricLabel {{
    color: {c.GRAY_4};
    font-size: {Typography.FONT_SIZE_SM}px;
    qproperty-alignment: 'AlignLeft';
}}

QLabel#metricValue {{
    color: {c.GRAY_0};
    font-size: {Typography.FONT_SIZE_SM}px;
    font-weight: bold;
    qproperty-alignment: 'AlignLeft';
}}

/* =================================================================
   VIEWS
   ================================================================= */

/* Content Panel Styling */
QLabel#contentPanelTitle {{
    color: {c.GRAY_4};
    font-size: {Typography.FONT_SIZE_LG}px;
    font-weight: bold;
}}

QFrame#contentPanelSeparator {{
    background-color: {c.GRAY_7};
    border: none;
    max-height: 1px;
}}

QLabel#contentPanelFooter {{
    color: {c.GRAY_4};
    font-size: {Typography.FONT_SIZE_BASE}px;
    border: none;
}}

/* Base styling for content panel text browser */
QTextBrowser#contentPanelText {{
    background-color: transparent;
    color: {c.GRAY_4};
    padding: 8px 0px;
    line-height: 1.5;
}}

TranscribeView QTextEdit {{
    background-color: {c.GRAY_9};
    border: 1px solid {c.GRAY_6};
    border-radius: 8px;
    padding: 16px;
    color: {c.GRAY_0};
    font-size: 16px;
}}

EditView QTextEdit {{
    background-color: {c.GRAY_9};
    color: {c.GRAY_0};
    border: 1px solid {c.GRAY_6};
    border-radius: 6px;
    padding: 12px;
}}

/* RefineView */
QLabel#refineTitle {{
    font-size: 18px;
    font-weight: bold;
    color: {c.GRAY_0};
    margin-bottom: 8px;
}}

QLabel#refineLabelOriginal {{
    color: {c.GRAY_2};
    font-weight: bold;
    margin-bottom: 4px;
}}

QLabel#refineLabelRefined {{
    color: {c.BLUE_4};
    font-weight: bold;
    margin-bottom: 4px;
}}

QTextEdit#refineTextOriginal {{
    background-color: {c.GRAY_9};
    border: 1px solid {c.GRAY_6};
    border-radius: 8px;
    padding: 16px;
    color: {c.GRAY_0};
    font-size: 14px;
}}

QTextEdit#refineTextRefined {{
    background-color: {c.GRAY_7};
    border: 1px solid {c.BLUE_4};
    border-radius: 8px;
    padding: 16px;
    color: {c.GRAY_0};
    font-size: 14px;
}}

/* =================================================================
   HOTKEY WIDGET
   ================================================================= */

/* Hotkey input field */
QLineEdit#hotkeyInput {{
    background-color: {c.GRAY_9};
    color: {c.GRAY_4};
    border: 1px solid {c.GRAY_7};
    border-radius: 6px;
    padding: 8px 12px;
}}

QLineEdit#hotkeyInput:focus {{
    border-color: {c.BLUE_4};
}}

QLineEdit#hotkeyInput[invalid="true"] {{
    border: 1px solid {c.RED_5};
}}

/* Validation error label */
QLabel#hotkeyValidation {{
    color: {c.RED_5};
}}

/* =================================================================
   ONBOARDING
   ================================================================= */

QWidget#onboardingFooter {{
    background-color: {c.GRAY_9};
    border-top: 1px solid {c.GRAY_7};
}}

QLabel#onboardingTitle {{
    color: {c.GRAY_0};
    font-weight: bold;
}}

QLabel.onboardingTitleXL {{
    font-size: {Typography.FONT_SIZE_XL}pt;
}}

QLabel.onboardingTitleLG {{
    font-size: {Typography.FONT_SIZE_LG}pt;
}}

QLabel#onboardingDesc {{
    color: {c.GRAY_2};
}}

QLabel#onboardingStatus {{
    color: {c.GRAY_4};
    font-size: {Typography.FONT_SIZE_MD}pt;
    font-style: italic;
}}

QProgressBar {{
    background-color: {c.GRAY_9};
    border: 1px solid {c.GRAY_7};
    border-radius: 4px;
    height: 8px;
}}

QProgressBar::chunk {{
    background-color: {c.BLUE_4};
    border-radius: 4px;
}}

/* TogglePill */
TogglePill {{
    background-color: {c.GRAY_9};
    color: {c.GRAY_2};
    border: 2px solid {c.GRAY_6};
    border-radius: {Spacing.RADIUS_XL}px;
    padding: {Spacing.S1}px {Spacing.S3}px;
    font-weight: 500;
    font-size: 14px;
}}

TogglePill:hover {{
    background-color: {c.GRAY_7};
    border-color: {c.GRAY_5};
    color: {c.GRAY_2};
}}

TogglePill:checked {{
    background-color: {c.BLUE_7};
    color: {c.GRAY_0};
    border: 2px solid {c.BLUE_4};
    font-weight: 600;
}}

TogglePill:checked:hover {{
    background-color: {c.BLUE_4};
    border-color: {c.BLUE_3};
}}

/* =================================================================
   TREE & TABLE VIEWS
   ================================================================= */

QTreeView {{
    background-color: transparent;
    border: none;
    outline: none;
}}

QTreeView::item {{
    padding: 6px; /* Consistent padding for tree items */
}}

QTableView {{
    background-color: transparent;
    border: none;
    color: {c.GRAY_2}; /* Softer text color */
    outline: none;
    gridline-color: {c.GRAY_7};
    selection-background-color: {c.BLUE_4}; /* Match other selection styles */
    selection-color: {c.GRAY_0};
}}

QTableView::item {{
    padding: 8px 12px; /* Breathing room for table cells */
    border: none;
}}

QTableView::item:selected {{
    background-color: {c.BLUE_4};
    color: {c.GRAY_0};
}}

QHeaderView::section {{
    background-color: {c.GRAY_9};
    color: {c.GRAY_4};
    padding: 6px 12px;
    border: none;
    border-bottom: 2px solid {c.GRAY_6};
    font-weight: 600;
}}

QTreeView {{
    alternate-background-color: {c.GRAY_6};
    background-color: {c.GRAY_9};
    border: none;
}}

QTreeView::item:hover {{
    background-color: {c.HOVER_OVERLAY_BLUE};
}}

QTableView {{
    alternate-background-color: {c.GRAY_6};
    background-color: {c.GRAY_9};
    border: none;
}}

QTableView::item:hover {{
    background-color: {c.HOVER_OVERLAY_BLUE};
}}

/* =================================================================
   BLOCKING OVERLAY
   ================================================================= */

QWidget#overlayContainer {{
    background-color: {c.GRAY_9};
    border: 1px solid {c.GRAY_6};
    border-radius: 8px;
}}

QLabel#overlayTitle {{
    color: {c.GRAY_0};
    font-size: 16px;
    font-weight: bold;
    border: none;
}}

QLabel#overlayStatus {{
    color: {c.GRAY_4};
    font-size: 14px;
    border: none;
}}

QProgressBar#overlayProgress {{
    background-color: {c.GRAY_7};
    border: none;
    border-radius: 2px;
    height: 4px;
}}

QProgressBar#overlayProgress::chunk {{
    background-color: {c.BLUE_4};
    border-radius: 2px;
}}
"""
