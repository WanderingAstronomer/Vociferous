"""
Typography constants.

Hand-crafted type scale following Refactoring UI principles:
- ~25% minimum difference between adjacent sizes
- Two font weights: normal (400) and emphasis (600)
- Scale: 11, 13, 16, 20, 24, 32, 48

Base reference width is 900px for responsive scaling.

Usage:
    from ui.constants import Typography
    label.setStyleSheet(f"font-size: {Typography.FONT_SIZE_BODY}px;")
"""


class Typography:
    """Hand-crafted typography scale with responsive sizing."""

    # =================================================================
    # TYPE SCALE (hand-crafted, ~25%+ jumps between sizes)
    # =================================================================
    # Scale: 11 -> 13 (18%) -> 16 (23%) -> 20 (25%) -> 24 (20%) -> 32 (33%) -> 48 (50%)
    FONT_SIZE_XS = 11      # Captions, timestamps, tertiary labels
    FONT_SIZE_SM = 13      # Secondary text, metadata
    FONT_SIZE_BASE = 16    # Body text, UI controls
    FONT_SIZE_MD = 20      # Subheadings, emphasized content
    FONT_SIZE_LG = 24      # Section headers
    FONT_SIZE_XL = 32      # Page titles
    FONT_SIZE_XXL = 48     # Hero/greeting text

    # =================================================================
    # FONT WEIGHTS (per Refactoring UI: stick to two weights)
    # =================================================================
    FONT_WEIGHT_NORMAL = 400   # Default for most text
    FONT_WEIGHT_EMPHASIS = 600 # Bold/emphasis for hierarchy

    # Legacy weight aliases (for backward compatibility)
    FONT_WEIGHT_REGULAR = FONT_WEIGHT_NORMAL
    FONT_WEIGHT_MEDIUM = 500   # Kept for subtle emphasis cases
    FONT_WEIGHT_SEMIBOLD = FONT_WEIGHT_EMPHASIS
    FONT_WEIGHT_BOLD = 700     # Rarely needed, prefer 600

    # =================================================================
    # SEMANTIC SIZE ALIASES
    # =================================================================
    # These map semantic names to the scale for specific UI contexts
    BODY_SIZE = FONT_SIZE_BASE          # 16px - main content
    SMALL_SIZE = FONT_SIZE_SM           # 13px - secondary info
    GREETING_SIZE = FONT_SIZE_LG        # 24px - welcome text

    # Sidebar typography hierarchy
    SECTION_HEADER_SIZE = FONT_SIZE_LG  # 24px - "History", "Focus Groups"
    DAY_HEADER_SIZE = FONT_SIZE_XS      # 11px - "Today", "Yesterday"
    TRANSCRIPT_ITEM_SIZE = FONT_SIZE_SM # 13px - transcript previews
    FOCUS_GROUP_NAME_SIZE = FONT_SIZE_BASE  # 16px - group names

    # Legacy aliases (deprecated - use scale names instead)
    FONT_SIZE_BODY = FONT_SIZE_BASE     # Use FONT_SIZE_BASE
    FONT_SIZE_LARGE = FONT_SIZE_MD      # Use FONT_SIZE_MD
    FONT_SIZE_HEADER = FONT_SIZE_LG     # Use FONT_SIZE_LG
    FONT_SIZE_TITLE = FONT_SIZE_XXL     # Use FONT_SIZE_XXL

    # =================================================================
    # LINE HEIGHTS
    # =================================================================
    GREETING_LINE_HEIGHT = 56   # ~1.2x for XXL
    BODY_LINE_HEIGHT = 24       # 1.5x for BASE
    SMALL_LINE_HEIGHT = 18      # ~1.4x for SM

    # Clamps for responsive line heights
    BODY_LINE_HEIGHT_MIN = 20
    BODY_LINE_HEIGHT_MAX = 30

    @staticmethod
    def scale_factor(window_width: int) -> float:
        """Calculate typography scale factor based on window width."""
        BASE_WIDTH = 900
        k = window_width / BASE_WIDTH
        return max(0.85, min(k, 1.20))

    @classmethod
    def scaled_size(cls, base_size: int, window_width: int) -> int:
        """Return scaled font size for given window width."""
        k = cls.scale_factor(window_width)
        return round(base_size * k)

    @classmethod
    def scaled_line_height(
        cls,
        base_height: int,
        window_width: int,
        min_height: int = 20,
        max_height: int = 30,
    ) -> int:
        """Return clamped, scaled line height."""
        k = cls.scale_factor(window_width)
        scaled = round(base_height * k)
        return max(min_height, min(scaled, max_height))
