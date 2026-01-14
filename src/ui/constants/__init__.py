"""
UI Constants Package.

Re-exports all constants for convenient import:
    from ui.constants import Colors, Typography, WorkspaceState, Spacing, Dimensions
"""

# Spacing (non-linear scale: 4, 8, 12, 16, 24, 32, 48, 64)
# Audio
from .audio import AudioConfig

# Colors
from .colors import Colors, ProjectColors

# Dimensions
from .dimensions import (
    BLURB_MAX_WIDTH,
    BLURB_MAX_WIDTH_RATIO,
    BUTTON_HEIGHT_DESTRUCTIVE,
    BUTTON_HEIGHT_PRIMARY,
    BUTTON_HEIGHT_SECONDARY,
    BUTTON_MIN_WIDTH_PRIMARY,
    CONTENT_COLUMN_MAX_WIDTH,
    CONTENT_COLUMN_MIN_WIDTH,
    CONTENT_COLUMN_OUTER_MARGIN,
    CONTENT_PANEL_PADDING,
    CONTENT_PANEL_RADIUS,
    DAY_INDENT,
    DAY_ROW_HEIGHT,
    PROJECT_ROW_HEIGHT,
    HISTORY_EXPORT_LIMIT,
    HISTORY_PREVIEW_LENGTH,
    HISTORY_RECENT_LIMIT,
    METRICS_BLOCK_PADDING,
    METRICS_DIVIDER_INSET,
    METRICS_DIVIDER_WIDTH,
    METRICS_STRIP_HEIGHT_COLLAPSED,
    METRICS_STRIP_HEIGHT_EXPANDED,
    METRICS_STRIP_PADDING_H,
    QT_WIDGET_MAX_HEIGHT,
    SECTION_HEADER_HEIGHT,
    SECTION_HEADER_PADDING_H,
    SECTION_HEADER_PADDING_V,
    SECTION_HEADER_RADIUS,
    SPLITTER_HANDLE_WIDTH,
    SPLITTER_HIT_AREA,
    TRANSCRIPT_INDENT,
    TRANSCRIPT_ROW_HEIGHT,
    WORKSPACE_PADDING,
    Dimensions,  # Class export
    WindowSize,
)

# Enums
from .enums import WorkspaceState
from .spacing import (
    APP_OUTER_PADDING,
    BUTTON_GAP,
    BUTTON_RADIUS_PILL,  # Legacy - use RADIUS_XL
    BUTTON_RADIUS_RECT,  # Legacy - use RADIUS_LG
    CONTROL_CLUSTER_PADDING,
    CONTROL_GAP,
    CONTROL_ROW_GAP,
    CONTROLS_CONTENT_GAP,
    GREETING_TOP_MARGIN,
    HEADER_CONTROLS_GAP,
    HEADER_RADIUS,  # Legacy - use RADIUS_MD
    HEADER_TO_LIST_GAP,
    MAJOR_GAP,
    MINOR_GAP,
    PANEL_PADDING,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_SM,
    RADIUS_XL,
    ROW_PADDING_H,
    ROW_PADDING_V,
    S0,
    S1,
    S2,
    S3,
    S4,
    S5,
    S6,
    S7,
    STANDARD_RADIUS,  # Legacy - use RADIUS_LG
    Spacing,  # Class export
)

# Timing
from .timing import (
    SPEAKING_SPEED_WPM,
    TYPING_SPEED_WPM,
    AnimationDurations,
    Opacity,
    TimerType,
    Timing,
    defer_call,
)

# Typography
from .typography import Typography

__all__ = [
    # Spacing (non-linear scale)
    "Spacing",
    "S0",  # 4px
    "S1",  # 8px
    "S2",  # 12px
    "S3",  # 16px
    "S4",  # 24px
    "S5",  # 32px
    "S6",  # 48px
    "S7",  # 64px
    "APP_OUTER_PADDING",
    "PANEL_PADDING",
    "CONTROL_CLUSTER_PADDING",
    "MAJOR_GAP",
    "MINOR_GAP",
    "CONTROL_GAP",
    # Border radii (scale: 4, 8, 12, 16)
    "RADIUS_SM",
    "RADIUS_MD",
    "RADIUS_LG",
    "RADIUS_XL",
    "STANDARD_RADIUS",  # Legacy
    "BUTTON_RADIUS_PILL",  # Legacy
    "BUTTON_RADIUS_RECT",  # Legacy
    "HEADER_RADIUS",  # Legacy
    # Gaps
    "HEADER_CONTROLS_GAP",
    "CONTROLS_CONTENT_GAP",
    "CONTROL_ROW_GAP",
    "BUTTON_GAP",
    "GREETING_TOP_MARGIN",
    "ROW_PADDING_V",
    "ROW_PADDING_H",
    "HEADER_TO_LIST_GAP",
    # Dimensions
    "Dimensions",
    "SPLITTER_HANDLE_WIDTH",
    "SPLITTER_HIT_AREA",
    "SECTION_HEADER_HEIGHT",
    "SECTION_HEADER_PADDING_H",
    "SECTION_HEADER_PADDING_V",
    "SECTION_HEADER_RADIUS",
    "PROJECT_ROW_HEIGHT",
    "DAY_ROW_HEIGHT",
    "TRANSCRIPT_ROW_HEIGHT",
    "DAY_INDENT",
    "TRANSCRIPT_INDENT",
    "METRICS_STRIP_HEIGHT_EXPANDED",
    "METRICS_STRIP_HEIGHT_COLLAPSED",
    "METRICS_STRIP_PADDING_H",
    "METRICS_BLOCK_PADDING",
    "METRICS_DIVIDER_WIDTH",
    "METRICS_DIVIDER_INSET",
    "WORKSPACE_PADDING",
    "CONTENT_COLUMN_MIN_WIDTH",
    "CONTENT_COLUMN_MAX_WIDTH",
    "CONTENT_COLUMN_OUTER_MARGIN",
    "CONTENT_PANEL_PADDING",
    "CONTENT_PANEL_RADIUS",
    "BUTTON_HEIGHT_PRIMARY",
    "BUTTON_HEIGHT_SECONDARY",
    "BUTTON_HEIGHT_DESTRUCTIVE",
    "BUTTON_MIN_WIDTH_PRIMARY",
    "BLURB_MAX_WIDTH",
    "BLURB_MAX_WIDTH_RATIO",
    "WindowSize",
    "QT_WIDGET_MAX_HEIGHT",
    "HISTORY_EXPORT_LIMIT",
    "HISTORY_RECENT_LIMIT",
    "HISTORY_PREVIEW_LENGTH",
    # Typography
    "Typography",
    # Colors
    "Colors",
    "ProjectColors",
    # Enums
    "WorkspaceState",
    # Timing
    "AnimationDurations",
    "Timing",
    "TimerType",
    "defer_call",
    "Opacity",
    "TYPING_SPEED_WPM",
    "SPEAKING_SPEED_WPM",
    # Audio
    "AudioConfig",
]
