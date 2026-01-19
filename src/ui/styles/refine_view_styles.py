"""
RefineView Styles - Consolidated styles for refinement UI.
"""

import src.ui.constants.colors as c


def get_strength_slider_stylesheet() -> str:
    """Style for the strength adjustment slider."""
    return f"""
        QSlider::groove:horizontal {{
            border: 1px solid {c.GRAY_6};
            background: {c.GRAY_8};
            height: 8px;
            border-radius: 4px;
        }}
        QSlider::sub-page:horizontal {{
            background: {c.BLUE_4};
            border-radius: 4px;
        }}
        QSlider::handle:horizontal {{
            background: {c.BLUE_4};
            border: 2px solid {c.BLUE_3};
            width: 20px;
            height: 20px;
            margin: -7px 0;
            border-radius: 10px;
        }}
        QSlider::handle:horizontal:hover {{
            background: {c.BLUE_3};
            border: 2px solid {c.BLUE_2};
        }}
    """


def get_refine_card_stylesheet() -> str:
    """Style for the card frame used in refinement views."""
    return f"""
        QFrame {{
            background-color: {c.GRAY_8};
            border: 1px solid {c.GRAY_6};
            border-radius: 8px;
        }}
    """
