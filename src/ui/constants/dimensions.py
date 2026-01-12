"""
Dimension constants for widgets and layout.

Covers sidebar, workspace, metrics strip, buttons, and content area sizing.

Usage:
    from ui.constants import Dimensions, WindowSize
    sidebar.setMinimumWidth(Dimensions.SIDEBAR_MIN_WIDTH)
"""

from .spacing import S2


class Dimensions:
    """Dimension constants for widgets and layout."""

    # Sidebar geometry
    SIDEBAR_DEFAULT_RATIO = 0.30
    SIDEBAR_MIN_WIDTH = 240
    SIDEBAR_MIN_RATIO = 0.34
    SIDEBAR_MAX_RATIO = 0.50
    SPLITTER_HANDLE_WIDTH = 6
    SPLITTER_HIT_AREA = 14

    @staticmethod
    def get_sidebar_min_width(window_width: int) -> int:
        """Calculate minimum sidebar width based on window size.

        Returns max of absolute minimum (240px) or 33% of window width.
        This ensures sidebar is always readable on any screen size.
        """
        return max(Dimensions.SIDEBAR_MIN_WIDTH, int(window_width * 0.33))

    @staticmethod
    def get_sidebar_max_width(window_width: int) -> int:
        """Calculate maximum sidebar width based on window size.

        Returns 50% of window width to prevent sidebar from dominating.
        """
        return int(window_width * Dimensions.SIDEBAR_MAX_RATIO)

    @staticmethod
    def clamp_sidebar_width(width: int, window_width: int) -> int:
        """Clamp sidebar width to valid range for given window size.

        Args:
            width: Desired sidebar width
            window_width: Current window width

        Returns:
            Width clamped to [min_width, max_width] range
        """
        min_width = Dimensions.get_sidebar_min_width(window_width)
        max_width = Dimensions.get_sidebar_max_width(window_width)
        return max(min_width, min(width, max_width))

    # Sidebar internal padding
    SIDEBAR_TOP_PADDING = S2
    SIDEBAR_SIDE_PADDING = 12
    SIDEBAR_BOTTOM_PADDING = 12
    SIDEBAR_SECTION_GAP = 12

    # Section header geometry
    SECTION_HEADER_HEIGHT = 44
    SECTION_HEADER_PADDING_H = 12
    SECTION_HEADER_PADDING_V = 8
    SECTION_HEADER_RADIUS = 8

    # List row heights
    FOCUS_GROUP_ROW_HEIGHT = 36
    DAY_ROW_HEIGHT = 32
    DAY_HEADER_ROW_HEIGHT = 32
    TRANSCRIPT_ROW_HEIGHT = 32

    # Indentation
    DAY_INDENT = 14
    TRANSCRIPT_INDENT = 28

    # Sidebar left inset
    SIDEBAR_LEFT_INSET = 16

    # Metrics strip
    METRICS_STRIP_HEIGHT_EXPANDED = 28
    METRICS_STRIP_HEIGHT_COLLAPSED = 12
    METRICS_STRIP_PADDING_H = 16
    METRICS_BLOCK_PADDING = 12
    METRICS_DIVIDER_WIDTH = 1
    METRICS_DIVIDER_INSET = 8

    # Workspace
    WORKSPACE_PADDING = S2

    # Content column constraints
    CONTENT_COLUMN_MIN_WIDTH = 480
    CONTENT_COLUMN_MAX_WIDTH = 820
    CONTENT_COLUMN_OUTER_MARGIN = S2

    # Content panel
    CONTENT_PANEL_PADDING = S2
    CONTENT_PANEL_RADIUS = 8  # Use BORDER_RADIUS_MD

    # Button sizes (consistent heights using spacing scale)
    BUTTON_HEIGHT_PRIMARY = 48  # Snapped to scale (was 52)
    BUTTON_HEIGHT_SECONDARY = 40  # Snapped to scale (was 44)
    BUTTON_HEIGHT_DESTRUCTIVE = 40
    BUTTON_MIN_WIDTH_PRIMARY = 240

    # Blurb text constraints
    BLURB_MAX_WIDTH = 560
    BLURB_MAX_WIDTH_RATIO = 0.75

    # =================================================================
    # BORDER RADII (consolidated scale: 4, 8, 12, 16)
    # =================================================================
    BORDER_RADIUS_SM = 4  # Small: inputs, chips
    BORDER_RADIUS_MD = 8  # Medium: cards, buttons
    BORDER_RADIUS_LG = 12  # Large: dialogs, panels
    BORDER_RADIUS_XL = 16  # Extra large: modals

    # Legacy aliases (deprecated)
    BORDER_RADIUS = BORDER_RADIUS_MD
    BORDER_RADIUS_SMALL = BORDER_RADIUS_SM

    # Tree/list item heights
    TREE_ITEM_HEIGHT = 32


class WindowSize:
    """Window size bands for responsive design."""

    SMALL = 720
    BASE = 900
    LARGE = 1200

    MIN_WIDTH = 600
    MIN_HEIGHT = 400


# Module-level aliases for backward compatibility
SIDEBAR_DEFAULT_RATIO = 0.30
SIDEBAR_MIN_WIDTH = 240
SIDEBAR_MIN_RATIO = 0.34
SIDEBAR_MAX_RATIO = 0.50
SPLITTER_HANDLE_WIDTH = 6
SPLITTER_HIT_AREA = 14

SIDEBAR_TOP_PADDING = S2
SIDEBAR_SIDE_PADDING = 12
SIDEBAR_BOTTOM_PADDING = 12
SIDEBAR_SECTION_GAP = 12

SECTION_HEADER_HEIGHT = 44
SECTION_HEADER_PADDING_H = 12
SECTION_HEADER_PADDING_V = 8
SECTION_HEADER_RADIUS = 8

FOCUS_GROUP_ROW_HEIGHT = 36
DAY_ROW_HEIGHT = 32
TRANSCRIPT_ROW_HEIGHT = 32

DAY_INDENT = 14
TRANSCRIPT_INDENT = 28
SIDEBAR_LEFT_INSET = 16

METRICS_STRIP_HEIGHT_EXPANDED = 28
METRICS_STRIP_HEIGHT_COLLAPSED = 12
METRICS_STRIP_PADDING_H = 16
METRICS_BLOCK_PADDING = 12
METRICS_DIVIDER_WIDTH = 1
METRICS_DIVIDER_INSET = 8

WORKSPACE_PADDING = S2

CONTENT_COLUMN_MIN_WIDTH = 480
CONTENT_COLUMN_MAX_WIDTH = 820
CONTENT_COLUMN_OUTER_MARGIN = S2

CONTENT_PANEL_PADDING = S2
CONTENT_PANEL_RADIUS = 8

BUTTON_HEIGHT_PRIMARY = 52
BUTTON_HEIGHT_SECONDARY = 44
BUTTON_HEIGHT_DESTRUCTIVE = 40
BUTTON_MIN_WIDTH_PRIMARY = 240

BLURB_MAX_WIDTH = 560
BLURB_MAX_WIDTH_RATIO = 0.75

QT_WIDGET_MAX_HEIGHT = 16777215

HISTORY_EXPORT_LIMIT = 10000
HISTORY_RECENT_LIMIT = 100
HISTORY_PREVIEW_LENGTH = 100
SIDEBAR_PREVIEW_LENGTH = 60
