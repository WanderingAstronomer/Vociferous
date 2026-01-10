"""
Styles for ContentPanel widget.

Note: ContentPanel uses custom painting for borders due to QScrollArea
clipping issues, so minimal QSS is needed here.
"""

from ui.constants import CONTENT_PANEL_RADIUS, Colors

CONTENT_PANEL_STYLESHEET = f"""
    /* Painted content panel (border/background handled in paintEvent) */
    QFrame#contentPanelPainted {{
        background: transparent;
        border: none;
    }}

    /* Fallback for non-painted content panels */
    QWidget#contentPanel,
    QFrame#contentPanel {{
        background-color: {Colors.BG_TERTIARY};
        border: 1px solid {Colors.ACCENT_BLUE};
        border-radius: {CONTENT_PANEL_RADIUS}px;
    }}

    QFrame#contentPanel[editing="true"] {{
        border: 3px solid {Colors.ACCENT_BLUE};
    }}

    QFrame#contentPanel[recording="true"] {{
        background-color: transparent;
        border: none;
    }}
"""
