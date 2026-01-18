"""
Dimension constants for widgets and layout.

Covers workspace, metrics strip, buttons, and content area sizing.

Usage:
    from ui.constants.dimensions import SPLITTER_HANDLE_WIDTH, etc.
"""

from .spacing import Spacing

# Splitter geometry
SPLITTER_HANDLE_WIDTH = 1
SPLITTER_HIT_AREA = 14

# Section header geometry
SECTION_HEADER_HEIGHT = 44
SECTION_HEADER_PADDING_H = 12
SECTION_HEADER_PADDING_V = 8
SECTION_HEADER_RADIUS = 8

# List row heights
PROJECT_ROW_HEIGHT = 36
DAY_ROW_HEIGHT = 32
DAY_HEADER_ROW_HEIGHT = 32
TRANSCRIPT_ROW_HEIGHT = 32

# Indentation
DAY_INDENT = 14
TRANSCRIPT_INDENT = 28

# Metrics strip
METRICS_STRIP_HEIGHT_EXPANDED = 28
METRICS_STRIP_HEIGHT_COLLAPSED = 12
METRICS_STRIP_PADDING_H = 16
METRICS_BLOCK_PADDING = 12
METRICS_DIVIDER_WIDTH = 1
METRICS_DIVIDER_INSET = 8

# Workspace
WORKSPACE_PADDING = Spacing.S2  # 12px

# Content column constraints
CONTENT_COLUMN_MIN_WIDTH = 480
CONTENT_COLUMN_MAX_WIDTH = 820
CONTENT_COLUMN_OUTER_MARGIN = Spacing.S2  # 12px

# Content panel
CONTENT_PANEL_PADDING = Spacing.S2  # 12px
CONTENT_PANEL_RADIUS = 8  # Use BORDER_RADIUS_MD

# =============================================================================
# Widget Specific Dimensions (Phase 5.3 Magic Number Extraction)
# =============================================================================

# Toggle Switch
TOGGLE_WIDTH = 50
TOGGLE_HEIGHT = 24
TOGGLE_RADIUS = 12
TOGGLE_CIRCLE_SIZE = 18
TOGGLE_CIRCLE_MARGIN = 3
TOGGLE_ANIMATION_DURATION_MS = 200

# Content Panel Detail View
CONTENT_PANEL_DETAIL_MARGIN_H = 32
CONTENT_PANEL_DETAIL_MARGIN_V = 24
CONTENT_PANEL_DETAIL_SPACING = 12


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

# Window size bands for responsive design
SMALL = 720
BASE = 900
LARGE = 1200

MIN_WIDTH = 600
MIN_HEIGHT = 400

QT_WIDGET_MAX_HEIGHT = 16777215

HISTORY_EXPORT_LIMIT = 10000
HISTORY_RECENT_LIMIT = 100
HISTORY_PREVIEW_LENGTH = 100
