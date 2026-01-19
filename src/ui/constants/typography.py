"""
Typography constants.

Hand-crafted type scale following Refactoring UI principles:
- ~25% minimum difference between adjacent sizes
- Two font weights: normal (400) and emphasis (600)
- Scale: 11, 13, 16, 20, 24, 32, 48

Base reference width is 900px for responsive scaling.

Usage:
    from src.ui.constants import Typography
    label.setStyleSheet(f"font-size: {Typography.FONT_SIZE_BASE}px;")
"""


class Typography:
    """Hand-crafted typography scale with responsive sizing."""

    # =================================================================
    # TYPE SCALE (hand-crafted, ~25%+ jumps between sizes)
    # =================================================================
    # Scale: 11 -> 13 (18%) -> 16 (23%) -> 20 (25%) -> 24 (20%) -> 32 (33%) -> 48 (50%)
    FONT_SIZE_XS = 11  # Captions, timestamps, tertiary labels
    FONT_SIZE_SM = 13  # Secondary text, metadata
    FONT_SIZE_BASE = 16  # Body text, UI controls
    FONT_SIZE_MD = 20  # Subheadings, emphasized content
    FONT_SIZE_LG = 24  # Section headers
    FONT_SIZE_XL = 32  # Page titles
    FONT_SIZE_XXL = 48  # Hero/greeting text

    # =================================================================
    # FONT WEIGHTS (per Refactoring UI: stick to two weights)
    # =================================================================
    FONT_WEIGHT_NORMAL = 400  # Default for most text
    FONT_WEIGHT_EMPHASIS = 600  # Bold/emphasis for hierarchy

    # =================================================================
    # SEMANTIC SIZE USAGE (context-specific applications)
    # =================================================================
    # These document recommended usage for specific UI contexts
    BODY_SIZE = FONT_SIZE_BASE  # 16px - main content
    SMALL_SIZE = FONT_SIZE_SM  # 13px - secondary info
    GREETING_SIZE = FONT_SIZE_LG  # 24px - welcome text
    TITLE_BAR_SIZE = FONT_SIZE_SM  # 13px - compact title bar text
    SECTION_HEADER_SIZE = FONT_SIZE_LG  # 24px - "History", "Projects"
    DAY_HEADER_SIZE = FONT_SIZE_XS  # 11px - "Today", "Yesterday"
    TRANSCRIPT_ITEM_SIZE = FONT_SIZE_SM  # 13px - transcript previews
    PROJECT_NAME_SIZE = FONT_SIZE_BASE  # 16px - project names

    # =================================================================
    # LINE HEIGHTS
    # =================================================================
    GREETING_LINE_HEIGHT = 56  # ~1.2x for XXL
    BODY_LINE_HEIGHT = 24  # 1.5x for BASE
    SMALL_LINE_HEIGHT = 18  # ~1.4x for SM

    # Clamps for responsive line heights
    BODY_LINE_HEIGHT_MIN = 20
    BODY_LINE_HEIGHT_MAX = 30

    # =================================================================
    # LEGACY ALIASES (deprecated - for backward compatibility)
    # =================================================================
    FONT_SIZE_BODY = FONT_SIZE_BASE  # Deprecated: use FONT_SIZE_BASE
    FONT_SIZE_LARGE = FONT_SIZE_MD  # Deprecated: use FONT_SIZE_MD
    FONT_SIZE_HEADER = FONT_SIZE_LG  # Deprecated: use FONT_SIZE_LG
    FONT_SIZE_TITLE = FONT_SIZE_XXL  # Deprecated: use FONT_SIZE_XXL

    # Font weight legacy aliases (these were consolidated from 4 weights to 2)
    FONT_WEIGHT_REGULAR = FONT_WEIGHT_NORMAL
    FONT_WEIGHT_MEDIUM = FONT_WEIGHT_EMPHASIS  # Use 600 emphasis instead
    FONT_WEIGHT_SEMIBOLD = FONT_WEIGHT_EMPHASIS
    FONT_WEIGHT_BOLD = FONT_WEIGHT_EMPHASIS  # Use 600 emphasis instead

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


# =================================================================
# MODULE-LEVEL RE-EXPORTS (for backward compatibility)
# =================================================================
# Scale values
FONT_SIZE_XS = Typography.FONT_SIZE_XS
FONT_SIZE_SM = Typography.FONT_SIZE_SM
FONT_SIZE_BASE = Typography.FONT_SIZE_BASE
FONT_SIZE_MD = Typography.FONT_SIZE_MD
FONT_SIZE_LG = Typography.FONT_SIZE_LG
FONT_SIZE_XL = Typography.FONT_SIZE_XL
FONT_SIZE_XXL = Typography.FONT_SIZE_XXL

# Font weights
FONT_WEIGHT_NORMAL = Typography.FONT_WEIGHT_NORMAL
FONT_WEIGHT_EMPHASIS = Typography.FONT_WEIGHT_EMPHASIS

# Semantic sizes
BODY_SIZE = Typography.BODY_SIZE
SMALL_SIZE = Typography.SMALL_SIZE
GREETING_SIZE = Typography.GREETING_SIZE
TITLE_BAR_SIZE = Typography.TITLE_BAR_SIZE
SECTION_HEADER_SIZE = Typography.SECTION_HEADER_SIZE
DAY_HEADER_SIZE = Typography.DAY_HEADER_SIZE
TRANSCRIPT_ITEM_SIZE = Typography.TRANSCRIPT_ITEM_SIZE
PROJECT_NAME_SIZE = Typography.PROJECT_NAME_SIZE

# Line heights
GREETING_LINE_HEIGHT = Typography.GREETING_LINE_HEIGHT
BODY_LINE_HEIGHT = Typography.BODY_LINE_HEIGHT
SMALL_LINE_HEIGHT = Typography.SMALL_LINE_HEIGHT
BODY_LINE_HEIGHT_MIN = Typography.BODY_LINE_HEIGHT_MIN
BODY_LINE_HEIGHT_MAX = Typography.BODY_LINE_HEIGHT_MAX

# Legacy aliases - these are deprecated but kept for backward compatibility
FONT_SIZE_BODY = Typography.FONT_SIZE_BASE  # Deprecated: use FONT_SIZE_BASE
FONT_SIZE_LARGE = Typography.FONT_SIZE_MD  # Deprecated: use FONT_SIZE_MD
FONT_SIZE_HEADER = Typography.FONT_SIZE_LG  # Deprecated: use FONT_SIZE_LG
FONT_SIZE_TITLE = Typography.FONT_SIZE_XXL  # Deprecated: use FONT_SIZE_XXL

# Font weight legacy aliases (these were removed to reduce to 2 weights)
FONT_WEIGHT_REGULAR = Typography.FONT_WEIGHT_NORMAL
FONT_WEIGHT_MEDIUM = Typography.FONT_WEIGHT_EMPHASIS  # Use 600 emphasis instead
FONT_WEIGHT_SEMIBOLD = Typography.FONT_WEIGHT_EMPHASIS
FONT_WEIGHT_BOLD = Typography.FONT_WEIGHT_EMPHASIS  # Use 600 emphasis instead
