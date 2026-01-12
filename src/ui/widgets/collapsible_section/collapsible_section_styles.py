"""
Styles for CollapsibleSection widget.

QSS rules for section headers, title labels, action buttons, and state variations.
"""

from ui.constants import (
    SECTION_HEADER_RADIUS,
    Colors,
    Typography,
)

COLLAPSIBLE_SECTION_STYLESHEET = f"""
    /* Section header label base */
    QLabel#sectionHeaderLabel {{
        font-weight: 600;
        font-size: {Typography.SECTION_HEADER_SIZE}px;
        background-color: transparent;
        border: none;
    }}

    QLabel#sectionHeaderLabel:disabled {{
        color: {Colors.TEXT_SECONDARY};
    }}

    /* Collapsible section title states */
    QLabel#sectionHeaderLabel[sectionState="disabled"] {{
        color: {Colors.TEXT_MUTED};
    }}

    QLabel#sectionHeaderLabel[sectionState="collapsed"] {{
        color: {Colors.TEXT_SECONDARY};
    }}

    QLabel#sectionHeaderLabel[sectionState="expanded"] {{
        color: {Colors.TEXT_PRIMARY};
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

    /* Section action button (e.g., "+" for creating items) */
    QPushButton#sectionActionButton {{
        background-color: transparent;
        color: {Colors.PRIMARY};
        border: none;
        font-size: {Typography.FONT_SIZE_LG}px;
        font-weight: {Typography.FONT_WEIGHT_EMPHASIS};
        padding: 0px;
        margin: 0px;
    }}

    QPushButton#sectionActionButton:hover {{
        color: {Colors.TEXT_PRIMARY};
    }}

    /* Collapse toggle button */
    QToolButton#collapseButton {{
        background-color: transparent;
        border: none;
        color: {Colors.TEXT_SECONDARY};
        font-size: {Typography.FONT_SIZE_SM}px;
    }}
"""
