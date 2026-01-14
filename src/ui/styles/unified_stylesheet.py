"""
Unified Stylesheet Generator.

Consolidates ALL application styles into a single stylesheet applied at app startup.
This follows PyQt6 best practices: apply styles once at app level, not per-widget.

Widget-specific styles are still organized in *_styles.py files but are collected
and applied together here instead of per-widget setStyleSheet() calls.
"""

from ui.constants import (
    CONTENT_PANEL_RADIUS,
    SECTION_HEADER_RADIUS,
    SPLITTER_HANDLE_WIDTH,
    Colors,
    Dimensions,
    Spacing,
    Typography,
)


def generate_unified_stylesheet() -> str:
    """
    Generate the complete application stylesheet.

    All styles are consolidated here and applied once at app startup.
    No per-widget setStyleSheet() calls needed.

    Returns:
        Complete QSS stylesheet string.
    """
    c = Colors
    return f"""
/* =================================================================
   GLOBAL / BASE STYLES
   ================================================================= */

/* Main window */
QMainWindow {{
    background-color: {c.BG_PRIMARY};
    border: 1px solid {c.BORDER_DEFAULT};
    border-radius: 6px;
}}

/* Default text color for all widgets */
QWidget {{
    color: {c.TEXT_PRIMARY};
}}

/* =================================================================
   SCROLLBARS
   ================================================================= */

QScrollBar:vertical {{
    background-color: {c.BG_PRIMARY};
    width: 10px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: {c.BORDER_DEFAULT};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {c.ACCENT_BLUE};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: {c.BG_PRIMARY};
    height: 10px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: {c.BORDER_DEFAULT};
    border-radius: 5px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {c.ACCENT_BLUE};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* Scroll areas */
QScrollArea {{
    background: transparent;
    border: none;
}}

/* =================================================================
   SPLITTER
   ================================================================= */

QSplitter::handle:horizontal {{
    background-color: {c.BORDER_DEFAULT};
    width: {SPLITTER_HANDLE_WIDTH}px;
}}

QSplitter::handle:horizontal:hover {{
    background-color: {c.BORDER_ACCENT};
}}

/* =================================================================
   MENU BAR
   ================================================================= */

QMenuBar {{
    background-color: {c.BG_PRIMARY};
    color: {c.TEXT_PRIMARY};
    font-size: 14px;
    border: none;
}}

QMenuBar::item {{
    padding: 4px 8px;
}}

QMenuBar::item:selected {{
    background-color: {c.ACCENT_BLUE_HOVER};
    color: {c.TEXT_ACCENT};
}}

QMenu {{
    background-color: {c.BG_SECONDARY};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER_ACCENT};
    font-size: 12px;
}}

QMenu::item {{
    padding: 6px 24px;
}}

QMenu::item:selected {{
    background-color: {c.ACCENT_BLUE};
    color: {c.TEXT_ON_ACCENT};
}}

/* =================================================================
   RADIO BUTTONS (Styled)
   ================================================================= */

QRadioButton[class="styledRadio"] {{
    color: {c.TEXT_PRIMARY};
    spacing: 8px;
    padding: 4px 0px;
}}

QRadioButton[class="styledRadio"]::indicator {{
    width: 16px;
    height: 16px;
    border: 2px solid {c.BORDER_DEFAULT};
    border-radius: 8px;
    background-color: {c.BG_TERTIARY};
}}

QRadioButton[class="styledRadio"]::indicator:checked {{
    background-color: {c.ACCENT_PRIMARY};
    border-color: {c.ACCENT_PRIMARY};
}}

QRadioButton[class="styledRadio"]::indicator:hover {{
    border-color: {c.ACCENT_PRIMARY};
}}

/* =================================================================
   TOOLTIPS
   ================================================================= */

QToolTip {{
    background-color: {c.BG_SECONDARY};
    color: {c.TEXT_ACCENT};
    border: 1px solid {c.BORDER_ACCENT};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
}}

/* =================================================================
   TITLE BAR
   ================================================================= */

QWidget#titleBar {{
    background-color: {c.BG_HEADER};
    border-bottom: 1px solid {c.BORDER_COLOR};
}}

QLabel#titleBarLabel {{
    color: {c.TEXT_PRIMARY};
    font-weight: 600;
}}

QToolButton#titleBarControl {{
    background-color: transparent;
    border: none;
    border-radius: {Dimensions.BORDER_RADIUS_SMALL}px;
}}

QToolButton#titleBarControl:hover {{
    background-color: {c.HOVER_BG_ITEM};
}}

QToolButton#titleBarControl:pressed {{
    background-color: {c.HOVER_BG_SECTION};
}}

QToolButton#titleBarClose {{
    background-color: transparent;
    border: none;
    border-radius: {Dimensions.BORDER_RADIUS_SM}px;
}}

QToolButton#titleBarClose:hover {{
    background-color: {c.DESTRUCTIVE};
}}

QToolButton#titleBarClose:pressed {{
    background-color: {c.DESTRUCTIVE_PRESSED};
}}

QWidget#dialogTitleBar {{
    background-color: {c.BG_HEADER};
}}

QLabel#dialogTitleLabel {{
    color: {c.TEXT_PRIMARY};
    font-weight: 600;
}}

QFrame#sectionDivider {{
    background-color: {c.BORDER_COLOR};
}}

QWidget#bottomSpacer {{
    background-color: transparent;
}}

/* =================================================================
   TREE VIEWS (History, Projects)
   ================================================================= */

QTreeView {{
    background-color: {c.BG_TERTIARY};
    border: none;
    outline: none;
}}

QTreeView::item {{
    min-height: {Dimensions.TREE_ITEM_HEIGHT}px;
    padding: 4px 8px;
    border: none;
}}

QTreeView::item:hover {{
    background-color: {c.HOVER_BG_ITEM};
}}

QTreeView::item:selected {{
    background-color: {c.HOVER_BG_SECTION};
}}

QTreeView::branch {{
    background-color: transparent;
}}

/* Project tree - transparent over background */
QTreeWidget#projectTree {{
    background-color: transparent;
    border: none;
    outline: none;
}}

QTreeWidget#projectTree::item {{
    min-height: {Dimensions.TREE_ITEM_HEIGHT}px;
    padding: 4px 8px;
    border: none;
}}

/* Hover and selection handled by ProjectDelegate */

QTreeWidget#projectTree::item:selected {{
    background-color: {c.HOVER_BG_SECTION};
}}

QTreeWidget#projectTree::branch {{
    background-color: transparent;
}}

/* =================================================================
   COLLAPSIBLE SECTIONS
   ================================================================= */

QLabel#sectionHeaderLabel {{
    font-weight: 600;
    font-size: {Typography.SECTION_HEADER_SIZE}px;
    background-color: transparent;
    border: none;
}}

QLabel#sectionHeaderLabel:disabled {{
    color: {c.TEXT_SECONDARY};
}}

QLabel#sectionHeaderLabel[sectionState="disabled"] {{
    color: {c.TEXT_MUTED};
}}

QLabel#sectionHeaderLabel[sectionState="collapsed"] {{
    color: {c.TEXT_SECONDARY};
}}

QLabel#sectionHeaderLabel[sectionState="expanded"] {{
    color: {c.TEXT_PRIMARY};
}}

/* Section header - transparent over background */
QWidget#sectionHeader {{
    background-color: transparent;
    border-radius: {SECTION_HEADER_RADIUS}px;
    border: none;
}}

QWidget#sectionHeader:hover {{
    background-color: rgba(255, 255, 255, 0.05);
    border: none;
}}

QPushButton#sectionActionButton {{
    background-color: transparent;
    color: {c.ACCENT_BLUE};
    border: none;
    font-size: 18pt;
    font-weight: bold;
    padding: 0px;
    margin: 0px;
}}

QPushButton#sectionActionButton:hover {{
    color: {c.TEXT_PRIMARY};
}}

QToolButton#collapseButton {{
    background-color: transparent;
    border: none;
    color: {c.TEXT_SECONDARY};
    font-size: 12px;
}}

/* =================================================================
   WORKSPACE
   ================================================================= */

QWidget#mainWorkspace {{
    background-color: {c.BG_PRIMARY};
}}

QLabel#greetingLabel {{
    color: {c.TEXT_PRIMARY};
}}

QLabel#greetingLabel[state="recording"] {{
    color: {c.ACCENT_RECORDING};
}}

QLabel#greetingLabel[state="transcribing"] {{
    color: {c.ACCENT_RECORDING};
}}

QLabel#subtextLabel {{
    color: {c.TEXT_SECONDARY};
}}

QLabel#hotkeyHint {{
    color: {c.TEXT_TERTIARY};
    font-size: {Typography.SMALL_SIZE}pt;
}}

QTextEdit#transcriptEditor {{
    background-color: {c.BG_TERTIARY};
    color: {c.TEXT_PRIMARY};
    font-size: {Typography.BODY_SIZE}pt;
    border: none;
    border-radius: 4px;
}}

QWidget#transcriptMetrics {{
    background-color: {c.BG_SECONDARY};
    border-bottom: 1px solid {c.BORDER_DEFAULT};
}}

QTextBrowser#transcriptView {{
    background-color: transparent;
    color: {c.TEXT_PRIMARY};
    font-size: {Typography.BODY_SIZE}pt;
    border: none;
}}

QScrollArea#workspaceScrollArea {{
    background-color: transparent;
    border: none;
}}

QScrollArea#workspaceScrollArea > QWidget {{
    background-color: transparent;
}}

/* Workspace content container - transparent to show ContentPanel background */
QWidget#workspaceContent {{
    background-color: transparent;
}}

/* Stacked widget inside workspace content - transparent to show ContentPanel background */
QWidget#workspaceContent QStackedWidget {{
    background-color: transparent;
}}

/* All pages inside QStackedWidget must also be transparent */
QWidget#workspaceContent QStackedWidget > QWidget {{
    background-color: transparent;
}}

/* Content label (IDLE state) - transparent background */
QLabel#contentLabel {{
    background-color: transparent;
    color: {c.TEXT_SECONDARY};
}}

/* =================================================================
   CONTENT PANEL
   ================================================================= */

QFrame#contentPanelPainted {{
    background: transparent;
    border: none;
}}

QWidget#contentPanel,
QFrame#contentPanel {{
    background-color: {c.BG_TERTIARY};
    border: 1px solid {c.ACCENT_BLUE};
    border-radius: {CONTENT_PANEL_RADIUS}px;
}}

QFrame#contentPanel[editing="true"] {{
    border: 3px solid {c.ACCENT_BLUE};
}}

QFrame#contentPanel[recording="true"] {{
    background-color: transparent;
    border: none;
}}

/* =================================================================
   BUTTONS - Following Refactoring UI Hierarchy Principles
   
   Primary: Solid high-contrast bg - THE main action on the page
   Secondary: Outline/low-contrast - clear but not prominent
   Destructive: Styled like secondary, only bold-red in confirmation dialogs
   
   All buttons use consistent padding (12px 24px) and border radius (12px)
   ================================================================= */

/* --- Primary Buttons (solid, high-contrast) --- */
QPushButton#primaryButton {{
    background-color: {c.PRIMARY};
    color: {c.TEXT_ON_ACCENT};
    border: none;
    border-radius: {Dimensions.BORDER_RADIUS_LG}px;
    font-size: {Typography.FONT_SIZE_BASE}px;
    font-weight: {Typography.FONT_WEIGHT_EMPHASIS};
    padding: {Spacing.S2}px {Spacing.S4}px;
}}

QPushButton#primaryButton:hover {{
    background-color: {c.PRIMARY_HOVER};
}}

QPushButton#primaryButton:pressed {{
    background-color: {c.PRIMARY_PRESSED};
}}

QPushButton#primaryButton:disabled {{
    background-color: {c.SURFACE_ALT};
    color: {c.TEXT_TERTIARY};
}}

/* --- Secondary Buttons (outline, subdued) --- */
QPushButton#secondaryButton {{
    background-color: transparent;
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER_DEFAULT};
    border-radius: {Dimensions.BORDER_RADIUS_LG}px;
    font-size: {Typography.FONT_SIZE_BASE}px;
    font-weight: {Typography.FONT_WEIGHT_NORMAL};
    padding: {Spacing.S2}px {Spacing.S4}px;
}}

QPushButton#secondaryButton:hover {{
    background-color: {c.HOVER_BG_ITEM};
    border-color: {c.PRIMARY};
    color: {c.TEXT_ACCENT};
}}

QPushButton#secondaryButton:disabled {{
    color: {c.TEXT_TERTIARY};
    border-color: {c.TEXT_TERTIARY};
}}

/* --- Destructive Buttons (outline, red accent on hover) --- */
/* Per Refactoring UI: destructive actions look secondary until confirmation */
QPushButton#destructiveButton {{
    background-color: transparent;
    color: {c.TEXT_SECONDARY};
    border: 1px solid {c.BORDER_DEFAULT};
    border-radius: {Dimensions.BORDER_RADIUS_LG}px;
    font-size: {Typography.FONT_SIZE_BASE}px;
    font-weight: {Typography.FONT_WEIGHT_NORMAL};
    padding: {Spacing.S2}px {Spacing.S4}px;
}}

QPushButton#destructiveButton:hover {{
    background-color: {c.DESTRUCTIVE_BG};
    color: {c.DESTRUCTIVE};
    border-color: {c.DESTRUCTIVE};
}}

/* --- Styled Buttons (dialogs - same principles) --- */
QPushButton#styledPrimary {{
    background-color: {c.PRIMARY};
    color: {c.TEXT_ON_ACCENT};
    border: none;
    border-radius: {Dimensions.BORDER_RADIUS_LG}px;
    font-size: {Typography.FONT_SIZE_BASE}px;
    font-weight: {Typography.FONT_WEIGHT_EMPHASIS};
    padding: {Spacing.S2}px {Spacing.S4}px;
}}

QPushButton#styledPrimary:hover {{
    background-color: {c.PRIMARY_HOVER};
}}

QPushButton#styledPrimary:disabled {{
    background-color: {c.SURFACE_ALT};
    color: {c.TEXT_TERTIARY};
}}

QPushButton#styledSecondary {{
    background-color: transparent;
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER_DEFAULT};
    border-radius: {Dimensions.BORDER_RADIUS_LG}px;
    font-size: {Typography.FONT_SIZE_BASE}px;
    font-weight: {Typography.FONT_WEIGHT_NORMAL};
    padding: {Spacing.S2}px {Spacing.S4}px;
}}

QPushButton#styledSecondary:hover {{
    background-color: {c.HOVER_BG_ITEM};
    border-color: {c.PRIMARY};
    color: {c.TEXT_ACCENT};
}}

QPushButton#styledDestructive {{
    background-color: transparent;
    color: {c.TEXT_SECONDARY};
    border: 1px solid {c.BORDER_DEFAULT};
    border-radius: {Dimensions.BORDER_RADIUS_LG}px;
    font-size: {Typography.FONT_SIZE_BASE}px;
    font-weight: {Typography.FONT_WEIGHT_NORMAL};
    padding: {Spacing.S2}px {Spacing.S4}px;
}}

QPushButton#styledDestructive:hover {{
    background-color: {c.DESTRUCTIVE_BG};
    color: {c.DESTRUCTIVE};
    border-color: {c.DESTRUCTIVE};
}}

/* =================================================================
   METRICS STRIP
   ================================================================= */

QWidget#metricsStrip {{
    background-color: {c.SURFACE};
    border-radius: {Dimensions.BORDER_RADIUS_MD}px;
}}

QLabel#metricLabel {{
    color: {c.TEXT_SECONDARY};
    font-size: 11px;
}}

QLabel#metricValue {{
    color: {c.TEXT_PRIMARY};
    font-size: 13px;
    font-weight: 500;
}}

QWidget#metricDivider {{
    background-color: {c.BORDER_DEFAULT};
}}

QLabel#metricsCollapsed {{
    color: {c.TEXT_SECONDARY};
    font-size: 11px;
}}

/* =================================================================
   HOTKEY WIDGET
   ================================================================= */

QLineEdit#hotkeyInput {{
    background-color: {c.BG_SECONDARY};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER_DEFAULT};
    border-radius: 6px;
    padding: 8px 12px;
}}

QLineEdit#hotkeyInput:focus {{
    border-color: {c.ACCENT_BLUE};
}}

QLineEdit#hotkeyInput[invalid="true"] {{
    border: 1px solid {c.DESTRUCTIVE};
}}

QLabel#hotkeyValidation {{
    color: {c.DESTRUCTIVE};
}}

/* =================================================================
   DIALOGS
   ================================================================= */

QDialog {{
    background-color: transparent;
    border: none;
}}

QFrame#dialogFrame {{
    background-color: {c.BG_PRIMARY};
    border: 3px solid {c.BORDER_ACCENT};
    border-radius: 0px;
}}

QWidget#dialogContent {{
    background-color: {c.BG_PRIMARY};
}}

QWidget#dialogContainer {{
    background-color: {c.BG_PRIMARY};
}}

QWidget#dialogButtonContainer {{
    background-color: {c.BG_SECONDARY};
    border-top: 1px solid {c.BORDER_DEFAULT};
    border-bottom-left-radius: 8px;
    border-bottom-right-radius: 8px;
}}

QLabel#dialogLabel {{
    color: {c.TEXT_PRIMARY};
    font-size: {Typography.BODY_SIZE}pt;
    border: none;
}}

QLineEdit#dialogInput {{
    background-color: {c.BG_SECONDARY};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER_DEFAULT};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: {Typography.BODY_SIZE}pt;
}}

QLineEdit#dialogInput:focus {{
    border-color: {c.ACCENT_BLUE};
}}

QLabel#groupDialogLabel {{
    color: {c.TEXT_PRIMARY};
    font-size: 14px;
    font-weight: 500;
}}

QLineEdit#groupNameInput {{
    background-color: {c.BG_SECONDARY};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER_DEFAULT};
    border-radius: 6px;
    padding: 10px 12px;
    font-size: 14px;
}}

QLineEdit#groupNameInput:focus {{
    border-color: {c.ACCENT_BLUE};
}}

/* =================================================================
   SETTINGS DIALOG
   ================================================================= */

QScrollArea#settingsScrollArea {{
    background-color: transparent;
    border: none;
}}

QLabel#settingsSectionHeader {{
    color: {c.TEXT_SECONDARY};
    font-size: {Typography.SECTION_HEADER_SIZE}pt;
    font-weight: 600;
    padding-top: {Spacing.MINOR_GAP}px;
    padding-bottom: {Spacing.MINOR_GAP // 2}px;
}}

/* Settings input widgets */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {c.BG_TERTIARY};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER_COLOR};
    border-radius: {Dimensions.BORDER_RADIUS_SMALL}px;
    padding: 6px 10px;
    min-height: 24px;
}}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {c.ACCENT_PRIMARY};
}}

/* QComboBox dropdown styling */
QComboBox::drop-down {{
    border: none;
    background: transparent;
}}

QComboBox::down-arrow {{
    image: none;
    border: none;
    width: 0px;
    height: 0px;
}}

QComboBox QAbstractItemView {{
    background-color: {c.BG_TERTIARY};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER_COLOR};
    selection-background-color: {c.ACCENT_PRIMARY};
    selection-color: {c.TEXT_PRIMARY};
    font-size: {Typography.SMALL_SIZE}pt;
    padding: 0px;
    margin: 0px;
    outline: 0;
}}

QComboBox QAbstractItemView::item {{
    background-color: {c.BG_TERTIARY};
    color: {c.TEXT_PRIMARY};
    padding: 8px 12px;
    min-height: 20px;
    border: none;
}}

QComboBox QAbstractItemView::item:selected {{
    background-color: {c.ACCENT_PRIMARY};
    color: {c.TEXT_PRIMARY};
}}

QComboBox QAbstractItemView::item:hover {{
    background-color: {c.HOVER_BG_ITEM};
}}

QCheckBox {{
    color: {c.TEXT_PRIMARY};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {c.BORDER_COLOR};
    border-radius: 3px;
    background-color: {c.BG_TERTIARY};
}}

QCheckBox::indicator:checked {{
    background-color: {c.ACCENT_PRIMARY};
    border-color: {c.ACCENT_PRIMARY};
}}

QWidget#settingsButtonContainer {{
    background-color: {c.BG_SECONDARY};
    border-top: 1px solid {c.BORDER_COLOR};
}}

QPushButton#settingsCancelBtn {{
    background-color: {c.BG_TERTIARY};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER_COLOR};
    border-radius: {Dimensions.BORDER_RADIUS}px;
}}

/* Hotkey widget Change button - primary blue style */
QPushButton#hotkeyChangeBtn {{
    background-color: {c.ACCENT_PRIMARY};
    color: {c.TEXT_PRIMARY};
    border: none;
    border-radius: {Dimensions.BORDER_RADIUS}px;
    padding: 8px 16px;
    font-weight: 600;
    min-width: 80px;
}}

QPushButton#hotkeyChangeBtn:hover {{
    background-color: {c.ACCENT_HOVER};
}}

QPushButton#hotkeyChangeBtn:pressed {{
    background-color: {c.ACCENT_PRESSED};
}}

QPushButton#hotkeyChangeBtn:disabled {{
    background-color: {c.BG_TERTIARY};
    color: {c.TEXT_SECONDARY};
}}

QPushButton#settingsCancelBtn:hover {{
    background-color: {c.HOVER_BG_ITEM};
}}

QPushButton#settingsApplyBtn {{
    background-color: {c.BG_TERTIARY};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER_COLOR};
    border-radius: {Dimensions.BORDER_RADIUS}px;
}}

QPushButton#settingsApplyBtn:hover {{
    background-color: {c.HOVER_BG_ITEM};
}}

QPushButton#settingsOkBtn {{
    background-color: {c.ACCENT_PRIMARY};
    color: {c.TEXT_ON_ACCENT};
    border: none;
    border-radius: {Dimensions.BORDER_RADIUS}px;
}}

QPushButton#settingsOkBtn:hover {{
    background-color: {c.ACCENT_HOVER};
}}

/* =================================================================
   ABOUT DIALOG
   ================================================================= */

QLabel#aboutTitle {{
    font-size: {Typography.FONT_SIZE_HEADER}px;
    font-weight: {Typography.FONT_WEIGHT_BOLD};
    color: {c.TEXT_PRIMARY};
    margin-bottom: {Spacing.MINOR_GAP}px;
}}

QLabel#aboutSubtitle {{
    font-size: {Typography.FONT_SIZE_LARGE}px;
    font-weight: {Typography.FONT_WEIGHT_MEDIUM};
    color: {c.TEXT_SECONDARY};
}}

QLabel#aboutDescription {{
    font-size: {Typography.FONT_SIZE_BODY}px;
    color: {c.TEXT_SECONDARY};
    line-height: 1.5;
}}

QLabel#aboutCreator {{
    font-size: {Typography.FONT_SIZE_BODY}px;
    font-weight: {Typography.FONT_WEIGHT_MEDIUM};
    color: {c.TEXT_PRIMARY};
}}

/* =================================================================
   WAVEFORM VISUALIZER
   ================================================================= */

QWidget#waveformVisualizer {{
    background-color: transparent;
}}

/* =================================================================
   FILE DIALOG (Qt-styled, non-native)
   ================================================================= */

QFileDialog {{
    background-color: {c.BG_PRIMARY};
    color: {c.TEXT_PRIMARY};
}}

QFileDialog QWidget {{
    background-color: {c.BG_PRIMARY};
    color: {c.TEXT_PRIMARY};
}}

QFileDialog QLabel {{
    color: {c.TEXT_PRIMARY};
    background: transparent;
}}

/* File/Directory list views */
QFileDialog QListView,
QFileDialog QTreeView {{
    background-color: {c.BG_SECONDARY};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER_DEFAULT};
    border-radius: {Dimensions.BORDER_RADIUS}px;
    selection-background-color: {c.ACCENT_PRIMARY};
    selection-color: {c.TEXT_ON_ACCENT};
}}

QFileDialog QListView::item,
QFileDialog QTreeView::item {{
    padding: 6px 8px;
    color: {c.TEXT_PRIMARY};
}}

QFileDialog QListView::item:hover,
QFileDialog QTreeView::item:hover {{
    background-color: {c.HOVER_BG_ITEM};
}}

QFileDialog QListView::item:selected,
QFileDialog QTreeView::item:selected {{
    background-color: {c.ACCENT_PRIMARY};
    color: {c.TEXT_ON_ACCENT};
}}

/* Header columns */
QFileDialog QHeaderView::section {{
    background-color: {c.BG_TERTIARY};
    color: {c.TEXT_SECONDARY};
    border: none;
    border-bottom: 1px solid {c.BORDER_DEFAULT};
    padding: 8px;
    font-weight: {Typography.FONT_WEIGHT_MEDIUM};
}}

/* Input fields */
QFileDialog QLineEdit {{
    background-color: {c.BG_SECONDARY};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER_DEFAULT};
    border-radius: {Dimensions.BORDER_RADIUS}px;
    padding: 8px 12px;
    selection-background-color: {c.ACCENT_PRIMARY};
    selection-color: {c.TEXT_ON_ACCENT};
}}

QFileDialog QLineEdit:focus {{
    border: 1px solid {c.ACCENT_PRIMARY};
}}

/* Dropdown/Combobox */
QFileDialog QComboBox {{
    background-color: {c.BG_SECONDARY};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER_DEFAULT};
    border-radius: {Dimensions.BORDER_RADIUS}px;
    padding: 8px 12px;
}}

QFileDialog QComboBox:focus {{
    border: 1px solid {c.ACCENT_PRIMARY};
}}

QFileDialog QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QFileDialog QComboBox QAbstractItemView {{
    background-color: {c.BG_SECONDARY};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.ACCENT_PRIMARY};
    selection-background-color: {c.ACCENT_PRIMARY};
    selection-color: {c.TEXT_ON_ACCENT};
}}

/* Toolbar and view buttons */
QFileDialog QToolBar {{
    background-color: {c.BG_PRIMARY};
    border: none;
    spacing: 4px;
}}

QFileDialog QToolButton {{
    background-color: {c.BG_SECONDARY};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER_DEFAULT};
    border-radius: {Dimensions.BORDER_RADIUS}px;
    padding: 6px;
    margin: 2px;
}}

QFileDialog QToolButton:hover {{
    background-color: {c.HOVER_BG_ITEM};
    border-color: {c.ACCENT_PRIMARY};
}}

QFileDialog QToolButton:checked {{
    background-color: {c.ACCENT_PRIMARY};
    border-color: {c.ACCENT_PRIMARY};
    color: {c.TEXT_ON_ACCENT};
}}

QFileDialog QToolButton:pressed {{
    background-color: {c.ACCENT_PRESSED};
}}

/* Navigation (places/shortcuts) */
QFileDialog QListView {{
    background-color: {c.BG_SECONDARY};
    border: 1px solid {c.BORDER_DEFAULT};
}}

QFileDialog QListView::item {{
    color: {c.TEXT_PRIMARY};
    padding: 6px;
}}

QFileDialog QListView::item:hover {{
    background-color: {c.HOVER_BG_ITEM};
}}

QFileDialog QListView::item:selected {{
    background-color: {c.ACCENT_PRIMARY};
    color: {c.TEXT_ON_ACCENT};
}}

/* Buttons - will be overridden programmatically for Choose/Cancel */
QFileDialog QPushButton {{
    background-color: {c.BG_TERTIARY};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER_DEFAULT};
    border-radius: {Dimensions.BORDER_RADIUS}px;
    padding: 10px 20px;
    min-width: 80px;
    font-size: {Typography.BODY_SIZE}pt;
}}

QFileDialog QPushButton:hover {{
    background-color: {c.HOVER_BG_ITEM};
    border-color: {c.ACCENT_PRIMARY};
}}

QFileDialog QPushButton:pressed {{
    background-color: {c.ACCENT_PRESSED};
}}

/* =================================================================
   SHELL COMPONENTS (IconRail, ActionDock)
   ================================================================= */

/* IconRail Container */
IconRail {{
    background-color: {c.BG_SECONDARY};
    border-right: 1px solid {c.BORDER_DEFAULT};
    min-width: 60px;
}}

/* IconRail Buttons */
IconRail QPushButton {{
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 10px;
    margin: 4px;
    color: {c.TEXT_SECONDARY};
    font-weight: bold;
    font-size: 16px; /* Icon placeholder size */
}}

IconRail QPushButton:hover {{
    background-color: {c.HOVER_BG_ITEM};
    color: {c.TEXT_PRIMARY};
}}

IconRail QPushButton:checked {{
    background-color: {c.ACCENT_TRANSPARENT};
    color: {c.ACCENT_BLUE};
    border-left: 3px solid {c.ACCENT_BLUE};
}}

/* ActionDock */
ActionDock {{
    background-color: {c.BG_SECONDARY};
    border-top: 1px solid {c.BORDER_DEFAULT};
    border-bottom: 1px solid {c.BORDER_DEFAULT};
    /* border-radius: 8px; */ 
}}

ActionDock QPushButton {{
    background-color: {c.BG_TERTIARY};
    border: 1px solid {c.BORDER_DEFAULT};
    border-radius: 4px;
    padding: 8px;
    color: {c.TEXT_PRIMARY};
}}

ActionDock QPushButton:hover {{
    background-color: {c.HOVER_BG_ITEM};
    border-color: {c.ACCENT_BLUE};
}}

ActionDock QPushButton:disabled {{
    color: {c.TEXT_TERTIARY};
    background-color: {c.BG_PRIMARY};
    border-color: {c.BORDER_DEFAULT};
}}

/* =================================================================
   STATUS BAR
   ================================================================= */
QStatusBar {{
    background: {c.BACKGROUND};
    color: {c.TEXT_SECONDARY};
    border-top: 1px solid {c.BORDER_DEFAULT};
    padding: 4px 8px;
}}

QStatusBar::item {{
    border: none;
}}

/* =================================================================
   OVERLAYS
   ================================================================= */
QFrame#previewOverlay {{
    background-color: {c.SURFACE};
    border: 1px solid {c.BORDER_LIGHT};
    border-radius: 6px;
}}

QFrame#previewOverlay QLabel {{
    color: {c.TEXT_PRIMARY};
    font-weight: bold;
}}

QFrame#previewOverlay QTextBrowser {{
    background-color: {c.BACKGROUND};
    border: none;
    color: {c.TEXT_PRIMARY};
    font-family: "Monospace";
}}

/* =================================================================
   CONTENT PANEL
   ================================================================= */
ContentPanel #timestampLabel {{
    font-size: 16px;
    font-weight: bold;
    color: {c.TEXT_PRIMARY};
}}

ContentPanel #durationLabel {{
    color: {c.TEXT_SECONDARY};
}}

ContentPanel QTextEdit {{
    background: {c.SURFACE};
    color: {c.TEXT_PRIMARY};
    font-size: 14px;
}}

/* =================================================================
   EDIT VIEW
   ================================================================= */
EditView QTextEdit {{
    background-color: {c.SURFACE};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER_DEFAULT};
    border-radius: 6px;
    padding: 12px;
    font-size: 14px;
    line-height: 1.5;
}}

EditView #saveButton {{
    background-color: {c.PRIMARY};
    color: {c.TEXT_ON_ACCENT};
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
    border: none;
}}

EditView #saveButton:hover {{
    background-color: {c.PRIMARY_HOVER};
}}

/* =================================================================
   TRANSCRIBE VIEW
   ================================================================= */
TranscribeView #headerPanel {{
    background-color: {c.SURFACE};
    border-bottom: 1px solid {c.BORDER_DEFAULT};
}}

TranscribeView #welcomeLabel {{
    color: {c.TEXT_PRIMARY};
    font-weight: bold;
}}

TranscribeView #motdLabel {{
    color: {c.TEXT_SECONDARY};
    font-style: italic;
}}

/* =================================================================
   SEARCH VIEW
   ================================================================= */
SearchView QLineEdit {{
    background-color: {c.SURFACE};
    border: 1px solid {c.BORDER_DEFAULT};
    border-radius: 4px;
    padding: 0 8px;
    font-size: 14px;
    color: {c.TEXT_PRIMARY};
}}

SearchView QLineEdit:focus {{
    border: 1px solid {c.ACCENT_PRIMARY};
}}

SearchView QTableView {{
    background-color: {c.BACKGROUND};
    border: none;
    gridline-color: {c.BORDER_DEFAULT};
}}

SearchView QTableView::item:selected {{
    background-color: {c.ACCENT_PRIMARY}40;
    color: {c.TEXT_PRIMARY};
}}

TranscribeView QTextEdit {{
    background-color: {c.SURFACE};
    border: 1px solid {c.BORDER_DEFAULT};
    border-radius: 8px;
    padding: 16px;
    color: {c.TEXT_PRIMARY};
    font-size: 16px;
}}

/* =================================================================
   METRICS DOCK
   ================================================================= */
#metricsDock {{
    background-color: {c.SURFACE};
    border-top: 1px solid {c.BORDER_DEFAULT};
}}

#metricsDock QLabel {{
    color: {c.TEXT_SECONDARY};
    font-family: "Segoe UI";
    font-size: 13px;
}}

#metricsDock #MetricValue {{
    color: {c.TEXT_PRIMARY};
    font-weight: bold;
    margin-left: 4px;
}}

/* =================================================================
   Project TREE
   ================================================================= */
QTreeView#projectGroupTree {{
    outline: 0;
    border: none;
    background-color: transparent;
    selection-background-color: transparent;
}}

QTreeView#projectGroupTree::item:focus {{
    border: none;
    outline: none;
}}

QTreeView#projectGroupTree::item:selected {{
    background-color: transparent;
    border: none;
}}

/* =================================================================
   WORKSPACE CONTENT (CAROUSEL)
   ================================================================= */
QWidget#carouselContainer {{
    background-color: {c.BACKGROUND};
    border-bottom: 1px solid {c.BORDER_DEFAULT};
}}

QWidget#carouselContainer QPushButton {{
    background: transparent;
    border: none;
    font-weight: bold;
    color: {c.TEXT_PRIMARY};
    border-radius: 4px;
}}

QWidget#carouselContainer QPushButton:hover {{
    background: {c.SURFACE_ALT};
}}

QWidget#carouselContainer QPushButton:disabled {{
    color: {c.TEXT_TERTIARY};
}}

QWidget#carouselContainer QLabel {{
    color: {c.TEXT_SECONDARY};
}}

/* =================================================================
   DIALOGS
   ================================================================= */
/* Metrics Explanation */
MetricsExplanationDialog QScrollArea {{
    background: {c.SURFACE};
    border: none;
}}

MetricsExplanationDialog QScrollArea > QWidget > QWidget {{
    background: {c.SURFACE};
}}

MetricsExplanationDialog QLabel[styleClass="sectionHeader"] {{
    color: {c.TEXT_PRIMARY};
    font-size: 14px;
    font-weight: bold;
    padding-top: 8px;
}}

MetricsExplanationDialog QLabel[styleClass="intro"] {{
    color: {c.TEXT_PRIMARY};
    font-size: 13px;
    line-height: 1.5;
    background: {c.SURFACE_ALT};
    padding: 12px;
    border-radius: 4px;
}}

MetricsExplanationDialog QLabel[styleClass="example"] {{
    color: {c.TEXT_SECONDARY};
    font-size: 13px;
    line-height: 1.6;
    background: {c.BACKGROUND};
    padding: 10px;
    border-left: 3px solid {c.PRIMARY};
    font-family: monospace;
}}

MetricsExplanationDialog QLabel[styleClass="philosophy"] {{
    color: {c.TEXT_PRIMARY};
    font-size: 13px;
    line-height: 1.5;
    background: {c.SURFACE_ALT}; /* Simplified gradient */
    padding: 12px;
    border-radius: 4px;
    border-left: 3px solid {c.PRIMARY};
}}

MetricsExplanationDialog QLabel[styleClass="body"] {{
    color: {c.TEXT_SECONDARY};
    font-size: 13px;
    line-height: 1.5;
}}

MetricsExplanationDialog QLabel[styleClass="formula"] {{
    color: {c.PRIMARY};
    font-size: 13px;
    font-family: 'Courier New', monospace;
    background: {c.BACKGROUND};
    padding: 10px 16px;
    border-radius: 4px;
    border: 1px solid rgba(90, 159, 212, 0.33);
}}

/* Error Dialog */
QLabel#errorDialogIcon {{
    color: {c.DESTRUCTIVE};
    padding: 0;
    margin: 0;
    font-size: {Typography.FONT_SIZE_XL}px;
    font-weight: {Typography.FONT_WEIGHT_EMPHASIS};
}}

QPlainTextEdit#errorDialogDetails {{
    color: {c.TEXT_PRIMARY};
    background-color: {c.SURFACE_ALT};
}}

QPushButton#errorDialogToggle {{
    background-color: transparent;
    color: {c.TEXT_SECONDARY};
    border: none;
    text-align: left;
    padding: 4px 8px;
}}

QPushButton#errorDialogToggle:hover {{
    color: {c.TEXT_PRIMARY};
}}

QPushButton#errorDialogCopy, QPushButton#errorDialogViewLogs {{
    color: white;
}}

/* Dialog Buttons (General) */
/* Targeted at QDialogButtonBox buttons styled as primary/secondary */
QPushButton[role="accept"] {{
    background-color: {c.PRIMARY};
    color: {c.TEXT_ON_ACCENT};
    border: none;
    border-radius: 6px; /* Dimensions.BORDER_RADIUS */
    padding: 12px 24px;
    font-weight: bold;
    min-width: 100px;
}}

QPushButton[role="accept"]:hover {{
    background-color: {c.PRIMARY_HOVER};
}}

QPushButton[role="accept"]:pressed {{
    background-color: {c.PRIMARY_PRESSED};
}}

QPushButton[role="reject"] {{
    background-color: {c.BG_TERTIARY};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER_DEFAULT};
    border-radius: 6px;
    padding: 12px 24px;
    font-weight: bold;
    min-width: 100px;
}}

QPushButton[role="reject"]:hover {{
    background-color: {c.HOVER_BG_ITEM};
}}

"""
