"""
Spacing system constants.

Base unit S = 8px, used for consistent padding, margins, and gaps throughout the UI.

Usage:
    from ui.constants import Spacing
    layout.setSpacing(Spacing.MAJOR_GAP)
"""

# Base spacing units (module-level for backward compatibility)
S0 = 4  # Smallest gap
S1 = 8  # Base unit
S2 = 16  # Standard padding/gaps
S3 = 24  # Large gaps
S4 = 32  # Extra large


class Spacing:
    """Spacing constants for consistent layout."""

    # Base units
    S0 = 4
    S1 = 8
    S2 = 16
    S3 = 24
    S4 = 32

    # Container padding
    APP_OUTER = S2  # 16px on all sides
    PANEL = S2  # 16px inside cards/panels
    CONTROL_CLUSTER = S2  # 16px around control groups

    # Gap between major blocks
    MAJOR_GAP = S2  # 16px
    MINOR_GAP = S1  # 8px (same as CONTROL_GAP, but for general use)
    CONTROL_GAP = S1  # 8px between related controls

    # Header to controls gap
    HEADER_CONTROLS_GAP = S3  # 24px
    # Controls to content gap
    CONTROLS_CONTENT_GAP = S3  # 24px
    # Gap between control rows
    CONTROL_ROW_GAP = 10
    # Gap between buttons in a row
    BUTTON_GAP = 12

    # Greeting text top margin
    GREETING_TOP_MARGIN = 16
    GREETING_TOP = 16  # Alias

    # Row padding
    ROW_PADDING_V = 6
    ROW_PADDING_H = 10

    # Header-to-list gap
    HEADER_TO_LIST_GAP = 8

    # Button padding
    BUTTON_PAD_V = 8
    BUTTON_PAD_H = 16
    BUTTON_PADDING = 16  # Alias for single-value padding

    # Sidebar
    SIDEBAR_TOP = 16
    SIDEBAR_SIDE = 12
    SIDEBAR_BOTTOM = 12
    SIDEBAR_SECTION_GAP = 12

    # Workspace/Content
    WORKSPACE = S2  # 16px
    CONTENT_COLUMN_OUTER = S2  # 16px
    CONTENT_PANEL = S2  # 16px


# Module-level aliases for backward compatibility
APP_OUTER_PADDING = S2
PANEL_PADDING = S2
CONTROL_CLUSTER_PADDING = S2
MAJOR_GAP = S2
MINOR_GAP = S1
CONTROL_GAP = S1
HEADER_CONTROLS_GAP = S3
CONTROLS_CONTENT_GAP = S3
CONTROL_ROW_GAP = 10
BUTTON_GAP = 12
GREETING_TOP_MARGIN = 8
ROW_PADDING_V = 6
ROW_PADDING_H = 10
HEADER_TO_LIST_GAP = 8

# Corner radius
STANDARD_RADIUS = 12
BUTTON_RADIUS_PILL = 18
BUTTON_RADIUS_RECT = 12
HEADER_RADIUS = 10
