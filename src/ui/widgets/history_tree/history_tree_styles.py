"""
History tree widget styles.
"""

from ui.constants import Colors, Dimensions


def get_history_tree_styles() -> str:
    """
    Generate stylesheet for history tree view.

    Returns:
        QSS stylesheet string.
    """
    return f"""
        QTreeView {{
            background-color: {Colors.BG_TERTIARY};
            border: none;
            outline: none;
        }}

        QTreeView::item {{
            min-height: {Dimensions.TREE_ITEM_HEIGHT}px;
            padding: 4px 8px;
            border: none;
        }}

        QTreeView::item:hover {{
            background-color: {Colors.HOVER_BG_ITEM};
        }}

        QTreeView::item:selected {{
            background-color: {Colors.HOVER_BG_SECTION};
        }}

        QTreeView::branch {{
            background-color: transparent;
        }}
    """
