"""
Sidebar component styles.
"""

from ui.constants import Colors, Dimensions


def get_sidebar_styles() -> str:
    """
    Generate stylesheet for sidebar components.

    Returns:
        QSS stylesheet string.
    """
    return f"""
        /* Sidebar container */
        QWidget#sidebar {{
            background-color: {Colors.BG_SECONDARY};
            /* min-width managed programmatically via setMinimumWidth() */
        }}

        /* Sidebar content - unified background for all sections */
        QWidget#sidebarContent {{
            background-color: {Colors.BG_SECONDARY};
            border: 1px solid {Colors.BORDER_COLOR};
            border-left: none;
            border-radius: 6px;
        }}

        /* Sidebar edge */
        QWidget#sidebarEdge {{
            background-color: {Colors.BG_TERTIARY};
        }}

        /* Section divider */
        QFrame#sectionDivider {{
            background-color: {Colors.BORDER_COLOR};
        }}

        /* Bottom spacer - transparent over unified background */
        QWidget#bottomSpacer {{
            background-color: transparent;
        }}

        /* Sidebar list (transcript tree) - transparent over unified background */
        QTreeView#sidebarList {{
            background-color: transparent;
            border: none;
            outline: none;
        }}

        QTreeView#sidebarList::item {{
            min-height: {Dimensions.TREE_ITEM_HEIGHT}px;
            padding: 4px 8px;
            border: none;
        }}

        QTreeView#sidebarList::item:hover {{
            background-color: {Colors.HOVER_BG_ITEM};
        }}

        QTreeView#sidebarList::item:selected {{
            background-color: {Colors.HOVER_BG_SECTION};
        }}
    """
