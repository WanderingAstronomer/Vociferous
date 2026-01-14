"""
Spacing system constants.

Non-linear spacing scale following Refactoring UI principles:
- 16px base unit that divides/multiplies nicely
- ~25%+ jumps between adjacent values
- Scale: 4, 8, 12, 16, 24, 32, 48, 64

Usage:
    from ui.constants import Spacing
    layout.setSpacing(Spacing.M)
"""

# =================================================================
# SPACING SCALE (module-level for backward compatibility)
# =================================================================
# Non-linear scale: values get progressively more spaced apart
# 4 -> 8 (100%) -> 12 (50%) -> 16 (33%) -> 24 (50%) -> 32 (33%) -> 48 (50%) -> 64 (33%)
S0 = 4  # Tightest: icon gaps, small padding
S1 = 8  # Compact: related control gaps
S2 = 12  # Default: standard gaps (was 16, adjusted for better rhythm)
S3 = 16  # Standard: section padding, major gaps
S4 = 24  # Comfortable: between major sections
S5 = 32  # Spacious: page sections
S6 = 48  # Generous: major visual breaks
S7 = 64  # Maximum: hero sections


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
    CONTROL_ROW_GAP = S2  # 12px - between control rows (was 10, snapped to scale)
    BUTTON_GAP = S2  # 12px - between buttons (was 12, already on scale)

    # Greeting text
    GREETING_TOP_MARGIN = S3  # 16px
    GREETING_TOP = S3  # 16px (alias)

    # Row padding (internal to list items)
    ROW_PADDING_V = S1  # 8px vertical (was 6, snapped to scale)
    ROW_PADDING_H = S2  # 12px horizontal (was 10, snapped to scale)

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


# =================================================================
# MODULE-LEVEL ALIASES (for backward compatibility)
# =================================================================
APP_OUTER_PADDING = S3
PANEL_PADDING = S3
CONTROL_CLUSTER_PADDING = S3
MAJOR_GAP = S3
MINOR_GAP = S1
CONTROL_GAP = S1
HEADER_CONTROLS_GAP = S4
CONTROLS_CONTENT_GAP = S4
CONTROL_ROW_GAP = S2  # 12px (was 10)
BUTTON_GAP = S2  # 12px
GREETING_TOP_MARGIN = S3  # 16px (was 8)
ROW_PADDING_V = S1  # 8px (was 6)
ROW_PADDING_H = S2  # 12px (was 10)
HEADER_TO_LIST_GAP = S1

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
