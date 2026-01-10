"""
Focus Group widget styles.
"""

from ui.constants import Colors, Dimensions


def get_focus_group_styles() -> str:
    """
    Generate stylesheet for focus group tree widget.

    Returns:
        QSS stylesheet string.
    """
    return f"""
        /* Focus group tree - transparent over unified sidebar background */
        QTreeWidget#focusGroupTree {{
            background-color: transparent;
            border: none;
            outline: none;
        }}

        QTreeWidget#focusGroupTree::item {{
            min-height: {Dimensions.TREE_ITEM_HEIGHT}px;
            padding: 4px 6px;
            border: none;
            border-radius: 4px;
        }}

        QTreeWidget#focusGroupTree::item:hover {{
            background-color: {Colors.HOVER_BG_ITEM};
        }}

        QTreeWidget#focusGroupTree::item:selected {{
            background-color: {Colors.HOVER_BG_SECTION};
        }}

        QTreeWidget#focusGroupTree::branch {{
            background-color: transparent;
        }}

        QTreeWidget#focusGroupTree::branch:has-children:closed {{
            image: url(:/icons/branch-closed.png);
        }}

        QTreeWidget#focusGroupTree::branch:has-children:open {{
            image: url(:/icons/branch-open.png);
        }}
    """
