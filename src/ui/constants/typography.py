"""
Typography constants.

Font sizes, line heights, and responsive scaling rules for the UI.
Base reference width is 900px.

Usage:
    from ui.constants import Typography
    label.setStyleSheet(f"font-size: {Typography.FONT_SIZE_BODY}px;")
"""


class Typography:
    """Typography scale with responsive sizing."""

    # Font sizes (in pixels)
    FONT_SIZE_XS = 11
    FONT_SIZE_SM = 13
    FONT_SIZE_BODY = 19
    FONT_SIZE_LARGE = 18
    FONT_SIZE_HEADER = 22
    FONT_SIZE_TITLE = 42

    # Font weights
    FONT_WEIGHT_REGULAR = 400
    FONT_WEIGHT_MEDIUM = 500
    FONT_WEIGHT_SEMIBOLD = 600
    FONT_WEIGHT_BOLD = 700

    # Legacy size aliases
    GREETING_SIZE = FONT_SIZE_TITLE
    BODY_SIZE = FONT_SIZE_BODY
    SMALL_SIZE = FONT_SIZE_SM

    # Sidebar typography hierarchy
    SECTION_HEADER_SIZE = FONT_SIZE_HEADER
    DAY_HEADER_SIZE = FONT_SIZE_XS
    TRANSCRIPT_ITEM_SIZE = 12
    FOCUS_GROUP_NAME_SIZE = 17  # BODY_SIZE - 2px

    # Line heights
    GREETING_LINE_HEIGHT = 28
    BODY_LINE_HEIGHT = 24
    SMALL_LINE_HEIGHT = 18

    # Clamps for line heights
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
