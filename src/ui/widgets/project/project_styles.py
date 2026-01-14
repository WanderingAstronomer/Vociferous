"""
Project widget styles.
"""

from ui.constants import Colors, Dimensions


def get_project_styles() -> str:
    """
    Generate stylesheet for Project tree widget.

    Returns:
        QSS stylesheet string.
    """
    return f"""
        /* Project tree - transparent over background */
        QTreeWidget#projectGroupTree {{
            background-color: transparent;
            border: none;
            outline: none;
        }}

        QTreeWidget#projectGroupTree::item {{
            min-height: {Dimensions.TREE_ITEM_HEIGHT}px;
            padding: 4px 6px;
            border: none;
            border-radius: 4px;
        }}

        QTreeWidget#projectGroupTree::item:hover {{
            background-color: {Colors.HOVER_BG_ITEM};
        }}

        QTreeWidget#projectGroupTree::item:selected {{
            background-color: {Colors.HOVER_BG_SECTION};
        }}

        QTreeWidget#projectGroupTree::branch {{
            background-color: transparent;
        }}

        QTreeWidget#projectGroupTree::branch:has-children:closed {{
            image: url(:/icons/branch-closed.png);
        }}

        QTreeWidget#projectGroupTree::branch:has-children:open {{
            image: url(:/icons/branch-open.png);
        }}
    """
