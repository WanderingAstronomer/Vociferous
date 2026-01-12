"""
Theme definitions.

Contains base/global styles that apply to the entire application,
independent of specific widgets. Widget-specific styles live
co-located with each widget.
"""

from ui.constants import (
    CONTENT_PANEL_RADIUS,
    SECTION_HEADER_RADIUS,
    SPLITTER_HANDLE_WIDTH,
    Colors,
)


def generate_base_stylesheet() -> str:
    """
    Generate base application stylesheet.

    Contains only global styles:
    - QMainWindow, QWidget defaults
    - Scrollbars
    - Menus and menu bar
    - Tooltips
    - Splitters

    Widget-specific styles are loaded from each widget's _styles.py module.
    """
    c = Colors
    return f"""
        /* Main window */
        QMainWindow {{
            background-color: {c.BG_PRIMARY};
            border: 1px solid {c.BORDER_DEFAULT};
            border-radius: 6px;
        }}

        QWidget {{
            background-color: {c.BG_PRIMARY};
            color: {c.TEXT_PRIMARY};
        }}

        /* Splitter */
        QSplitter::handle:horizontal {{
            background-color: {c.BORDER_DEFAULT};
            width: {SPLITTER_HANDLE_WIDTH}px;
        }}

        QSplitter::handle:horizontal:hover {{
            background-color: {c.BORDER_ACCENT};
        }}

        /* Scrollbars */
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

        /* Menu bar */
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
            background-color: {c.ACCENT_BLUE_HOVER};
            color: {c.TEXT_ACCENT};
        }}

        /* Tooltips */
        QToolTip {{
            background-color: {c.BG_SECONDARY};
            color: {c.TEXT_ACCENT};
            border: 1px solid {c.BORDER_ACCENT};
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 11px;
        }}

        /* Scroll areas */
        QScrollArea {{
            background: transparent;
            border: none;
        }}

        /* Content panel base */
        QWidget#contentPanel,
        QFrame#contentPanel {{
            background-color: {c.BG_TERTIARY};
            border: 1px solid {c.ACCENT_BLUE};
            border-radius: {CONTENT_PANEL_RADIUS}px;
        }}

        QFrame#contentPanelPainted {{
            background: transparent;
            border: none;
        }}

        QFrame#contentPanel[editing="true"] {{
            border: 3px solid {c.ACCENT_BLUE};
        }}

        QFrame#contentPanel[recording="true"] {{
            background-color: transparent;
            border: none;
        }}

        /* Section header - transparent over unified sidebar background */
        QWidget#sectionHeader {{
            background-color: transparent;
            border-radius: {SECTION_HEADER_RADIUS}px;
            border: none;
        }}

        QWidget#sectionHeader:hover {{
            background-color: rgba(255, 255, 255, 0.05);
            border: none;
        }}

        /* Section divider */
        QFrame#sectionDivider {{
            color: {c.BG_TERTIARY};
        }}

        /* Bottom spacer - transparent over unified sidebar background */
        QWidget#bottomSpacer {{
            background: transparent;
        }}
    """


def generate_dark_theme() -> str:
    """Generate the complete dark theme stylesheet."""
    return generate_base_stylesheet()


def generate_light_theme() -> str:
    """
    Generate a light theme stylesheet.

    TODO: Implement light theme colors when needed.
    """
    # Placeholder - return dark theme for now
    return generate_base_stylesheet()
