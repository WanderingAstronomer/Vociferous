"""
View-specific stylesheet overrides for RefineView.
"""

import src.ui.constants.colors as c


def get_refine_view_stylesheet() -> str:
    """
    Custom stylesheet for Refine View.
    """
    return f"""
        QSlider::groove:horizontal {{
            border: 1px solid {c.GRAY_7};
            background: {c.GRAY_8};
            height: 4px;
            border-radius: 2px;
        }}
        QSlider::sub-page:horizontal {{
            background: {c.BLUE_4};
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: {c.BLUE_4};
            border: 1px solid {c.BLUE_4};
            width: 12px;
            height: 12px;
            margin: -4px 0;
            border-radius: 6px;
        }}
    """


def get_refine_button_active_stylesheet() -> str:
    """Style for active refine button."""
    return f"""
        QPushButton {{
            background-color: {c.BLUE_4};
            color: {c.GRAY_0};
            border: none;
            border-radius: 4px;
            font-weight: bold;
        }}
        QPushButton:hover {{ background-color: {c.BLUE_3}; }}
        QPushButton:pressed {{ background-color: {c.BLUE_6}; }}
    """


def get_refine_button_inactive_stylesheet() -> str:
    """Style for inactive refine button."""
    return f"""
        QPushButton {{
            background-color: {c.GRAY_7};
            color: {c.GRAY_4};
            border: 1px solid {c.GRAY_6};
            border-radius: 4px;
            font-weight: normal;
        }}
    """
