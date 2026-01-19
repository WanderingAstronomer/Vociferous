"""
Spacing system constants.

Non-linear spacing scale following Refactoring UI principles:
- 16px base unit that divides/multiplies nicely
- ~25%+ jumps between adjacent values
- Scale: 4, 8, 12, 16, 24, 32, 48, 64

Usage:
    from src.ui.constants import Spacing
    layout.setSpacing(Spacing.MINOR_GAP)
"""


class Spacing:
    """Spacing constants for consistent layout."""

    # =================================================================
    # SCALE VALUES
    # =================================================================
    S0 = 4  # Tightest
    S1 = 8  # Compact
    S2 = 12  # Default gaps
    S3 = 16  # Standard padding
    S4 = 24  # Comfortable
    S5 = 32  # Spacious
    S6 = 48  # Generous
    S7 = 64  # Maximum

    # =================================================================
    # SEMANTIC ALIASES (map to scale values)
    # =================================================================
    # Container padding
    APP_OUTER = S3  # 16px - window margins
    PANEL = S3  # 16px - card/panel padding
    CONTROL_CLUSTER = S3  # 16px - around control groups

    # Gaps between elements
    MAJOR_GAP = S3  # 16px - major section gaps
    MINOR_GAP = S1  # 8px - related element gaps
    CONTROL_GAP = S1  # 8px - between form controls

    # Header/content spacing
    HEADER_CONTROLS_GAP = S4  # 24px - header to controls
    CONTROLS_CONTENT_GAP = S4  # 24px - controls to content
    CONTROL_ROW_GAP = S2  # 12px - between control rows
    BUTTON_GAP = S2  # 12px - between buttons

    # Greeting text
    GREETING_TOP_MARGIN = S3  # 16px
    GREETING_TOP = S3  # 16px (alias)

    # Row padding (internal to list items)
    ROW_PADDING_V = S1  # 8px vertical
    ROW_PADDING_H = S2  # 12px horizontal

    # Header-to-list
    HEADER_TO_LIST_GAP = S1  # 8px

    # Button padding
    BUTTON_PAD_V = S1  # 8px
    BUTTON_PAD_H = S3  # 16px
    BUTTON_PADDING = S3  # 16px (single-value alias)

    # Workspace/Content
    WORKSPACE = S3  # 16px
    CONTENT_COLUMN_OUTER = S3  # 16px
    CONTENT_PANEL = S3  # 16px

    # Visual separators and borders
    TITLE_BAR_SEPARATOR = S0  # 4px - thin border below title bar

    # =================================================================
    # BORDER RADII (consolidated scale: 4, 8, 12, 16)
    # =================================================================
    RADIUS_SM = 4
    RADIUS_MD = 8
    RADIUS_LG = 12
    RADIUS_XL = 16

    # Legacy aliases (deprecated - use RADIUS_* instead)
    STANDARD_RADIUS = RADIUS_LG  # 12px
    BUTTON_RADIUS_PILL = RADIUS_XL  # 16px (was 18, snapped to scale)
    BUTTON_RADIUS_RECT = RADIUS_LG  # 12px (was 12, already on scale)
    HEADER_RADIUS = RADIUS_MD  # 8px (was 10, snapped to scale)


# =================================================================
# MODULE-LEVEL RE-EXPORTS (for backward compatibility)
# =================================================================
# These allow existing code to use: from src.ui.constants.spacing import MINOR_GAP
# instead of: from src.ui.constants import Spacing; Spacing.MINOR_GAP

# Scale values
S0 = Spacing.S0
S1 = Spacing.S1
S2 = Spacing.S2
S3 = Spacing.S3
S4 = Spacing.S4
S5 = Spacing.S5
S6 = Spacing.S6
S7 = Spacing.S7

# Semantic aliases
APP_OUTER_PADDING = Spacing.APP_OUTER
PANEL_PADDING = Spacing.PANEL
CONTROL_CLUSTER_PADDING = Spacing.CONTROL_CLUSTER
MAJOR_GAP = Spacing.MAJOR_GAP
MINOR_GAP = Spacing.MINOR_GAP
CONTROL_GAP = Spacing.CONTROL_GAP
HEADER_CONTROLS_GAP = Spacing.HEADER_CONTROLS_GAP
CONTROLS_CONTENT_GAP = Spacing.CONTROLS_CONTENT_GAP
CONTROL_ROW_GAP = Spacing.CONTROL_ROW_GAP
BUTTON_GAP = Spacing.BUTTON_GAP
GREETING_TOP_MARGIN = Spacing.GREETING_TOP_MARGIN
GREETING_TOP = Spacing.GREETING_TOP
ROW_PADDING_V = Spacing.ROW_PADDING_V
ROW_PADDING_H = Spacing.ROW_PADDING_H
HEADER_TO_LIST_GAP = Spacing.HEADER_TO_LIST_GAP
BUTTON_PAD_V = Spacing.BUTTON_PAD_V
BUTTON_PAD_H = Spacing.BUTTON_PAD_H
BUTTON_PADDING = Spacing.BUTTON_PADDING
WORKSPACE = Spacing.WORKSPACE
CONTENT_COLUMN_OUTER = Spacing.CONTENT_COLUMN_OUTER
CONTENT_PANEL = Spacing.CONTENT_PANEL
TITLE_BAR_SEPARATOR = Spacing.TITLE_BAR_SEPARATOR

# Border radii
RADIUS_SM = Spacing.RADIUS_SM
RADIUS_MD = Spacing.RADIUS_MD
RADIUS_LG = Spacing.RADIUS_LG
RADIUS_XL = Spacing.RADIUS_XL
STANDARD_RADIUS = Spacing.STANDARD_RADIUS
BUTTON_RADIUS_PILL = Spacing.BUTTON_RADIUS_PILL
BUTTON_RADIUS_RECT = Spacing.BUTTON_RADIUS_RECT
HEADER_RADIUS = Spacing.HEADER_RADIUS
