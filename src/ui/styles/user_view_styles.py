"""
View-specific stylesheet overrides for UserView.
"""

import src.ui.constants.colors as c


def get_user_view_stylesheet() -> str:
    """
    Custom stylesheet for User View.

    Includes:
    - Styled metric cards
    - Centered layouts
    - Professional spacing
    """
    return f"""
        /* User View Container */
        UserView {{
            background-color: {c.GRAY_9};
        }}
        
        /* Metric cards */
        UserView QFrame#metricCard {{
            background-color: {c.GRAY_8};
            border: 1px solid {c.GRAY_6};
            border-radius: 8px;
            padding: 20px;
            min-height: 96px;
        }}
        
        UserView QFrame#metricCard:hover {{
            border-color: {c.BLUE_4};
        }}
        
        /* Explanation cards */
        UserView QFrame#explanationCard {{
            background-color: {c.GRAY_8};
            border: 1px solid {c.GRAY_6};
            border-radius: 6px;
        }}
        
        /* Section headers */
        UserView QLabel#sectionHeader {{
            color: {c.GRAY_3};
            font-weight: bold;

        }}

        UserView QLabel#timeframeBadge {{
            color: {c.GRAY_5};
            background-color: {c.GRAY_8};
            border: 1px solid {c.GRAY_6};
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 11px;
            text-transform: uppercase;
        }}
        
        /* Metric values */
        UserView QLabel#metricValue {{
            color: {c.BLUE_4};
        }}
        
        /* Metric titles */
        UserView QLabel#metricTitle {{
            color: {c.GRAY_2};
            padding: 0px 5px;
        }}
        
        /* Metric descriptions */
        UserView QLabel#metricDescription {{
            color: {c.GRAY_3};
            font-size: 13px;
        }}
        
        /* Metric Icons */
        UserView QLabel#metricIcon {{
            opacity: 0.6;
            padding-bottom: 8px;
        }}
        
        /* About section (Footer role) */
        UserView QLabel#aboutTitle {{
            color: {c.BLUE_4};
            font-size: 36px;
            font-weight: bold;
        }}

        UserView QLabel#aboutSubtitle {{
            color: {c.GRAY_3};
            font-size: 24px;
        }}

        UserView QLabel#aboutDescription {{
            color: {c.GRAY_3};
            font-size: 20px;
        }}

        UserView QLabel#aboutCreator {{
            color: {c.GRAY_3};
            font-size: 24px;
        }}
        
        /* Buttons */
        UserView QPushButton#secondaryButton {{
            background-color: {c.GRAY_8};
            color: {c.GRAY_2};
            border: 1px solid {c.GRAY_6};
            border-radius: 4px;
            font-weight: 600;
            padding: 6px 24px;
        }}
        
        UserView QPushButton#secondaryButton:hover {{
            background-color: {c.GRAY_7};
            border-color: {c.BLUE_4};
        }}
        /* Insight Row */
        UserView QLabel#insightText {{
            color: {c.GRAY_2};
            font-size: 18px;
            font-style: italic;
        }}

        /* Empty State */
        UserView QFrame#emptyStateCard {{
            background-color: {c.GRAY_8};
            border: 1px dashed {c.GRAY_5};
            border-radius: 8px;
            padding: 32px;
        }}
        
        UserView QLabel#emptyStateTitle {{
            color: {c.GRAY_2};
            font-size: 18px;
            font-weight: bold;
        }}

        UserView QLabel#emptyStateDescription {{
            color: {c.GRAY_3};
            font-size: 14px;
        }}

        /* Collapsible Header */
        UserView QPushButton#collapseButton {{
            text-align: center;
            border: none;
            background: transparent;
            color: {c.GRAY_3};
            font-weight: 600;
            font-size: 18px;
            padding: 8px;
        }}
        
        UserView QPushButton#collapseButton:hover {{
            color: {c.BLUE_4};
        }}
    """
