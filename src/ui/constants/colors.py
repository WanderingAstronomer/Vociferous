"""
Color palette constants.

Dark theme colors following Refactoring UI principles:
- 3-tier text hierarchy: primary, secondary, tertiary
- Consolidated accent colors (no duplicates)
- Semantic naming for states and actions

Usage:
    from ui.constants import Colors
    widget.setStyleSheet(f"background: {Colors.BACKGROUND};")
"""


class Colors:
    """Application color palette."""

    # =================================================================
    # BACKGROUNDS (4-level surface hierarchy)
    # =================================================================
    BACKGROUND = "#1e1e1e"   # L0: Main window/app background
    SURFACE = "#252526"      # L1: Panels, cards, dialogs
    SURFACE_ALT = "#2a2a2a"  # L2: List items, hover states
    HEADER = "#1a1a1a"       # L-1: Section headers (darker)

    # Legacy aliases (deprecated - use semantic names above)
    BG_PRIMARY = BACKGROUND
    BG_SECONDARY = SURFACE
    BG_TERTIARY = SURFACE_ALT
    BG_HEADER = HEADER
    BG_SIDEBAR = SURFACE

    # =================================================================
    # TEXT HIERARCHY (per Refactoring UI: 3 tiers)
    # =================================================================
    TEXT_PRIMARY = "#d4d4d4"    # Headlines, important content
    TEXT_SECONDARY = "#888888"  # Supporting text, metadata
    TEXT_TERTIARY = "#555555"   # Disabled, very subtle hints

    # Special text colors
    TEXT_ACCENT = "#5a9fd4"     # Links, interactive text
    TEXT_ON_ACCENT = "#ffffff"  # Text on accent backgrounds
    TEXT_GREETING = "#ffffff"   # Hero/greeting text

    # Legacy alias
    TEXT_MUTED = TEXT_TERTIARY
    TEXT_ON_PRIMARY = TEXT_ON_ACCENT

    # =================================================================
    # PRIMARY ACCENT (consolidated - single source of truth)
    # =================================================================
    PRIMARY = "#5a9fd4"
    PRIMARY_HOVER = "#6db3e8"
    PRIMARY_PRESSED = "#2d5a7b"

    # Legacy aliases (all point to PRIMARY family)
    ACCENT_BLUE = PRIMARY
    ACCENT_BLUE_HOVER = PRIMARY_HOVER
    ACCENT_BLUE_DARK = PRIMARY_PRESSED
    ACCENT_BLUE_PRESSED = PRIMARY_PRESSED
    ACCENT_BLUE_BRIGHT = PRIMARY           # Consolidated
    ACCENT_BLUE_BRIGHT_HOVER = PRIMARY_HOVER  # Consolidated
    ACCENT_PRIMARY = PRIMARY
    ACCENT_HOVER = PRIMARY_HOVER
    ACCENT_PRESSED = PRIMARY_PRESSED
    BORDER_ACCENT = PRIMARY

    # =================================================================
    # SEMANTIC COLORS
    # =================================================================
    # Success (green)
    SUCCESS = "#4caf50"
    SUCCESS_HOVER = "#5bc95f"
    SUCCESS_PRESSED = "#3d8b40"

    # Destructive/Error (red)
    DESTRUCTIVE = "#ff6b6b"
    DESTRUCTIVE_HOVER = "#ff8585"
    DESTRUCTIVE_PRESSED = "#cc5656"
    DESTRUCTIVE_BG = "#5a2d2d"      # Subtle background tint

    # Warning (orange)
    WARNING = "#ffa500"
    WARNING_HOVER = "#ffb733"
    WARNING_PRESSED = "#cc8400"

    # Legacy destructive aliases
    ACCENT_DESTRUCTIVE = DESTRUCTIVE
    DESTRUCTIVE_IDLE = "#7a3535"
    DESTRUCTIVE_HOVER_BG = DESTRUCTIVE_BG

    # =================================================================
    # ACTION BUTTON COLORS
    # =================================================================
    # Start/Go (green)
    ACCENT_GREEN = "#2d6a4f"
    ACCENT_GREEN_HOVER = "#40916c"
    ACCENT_GREEN_PRESSED = "#1b4332"

    # Stop/Cancel (red)
    ACCENT_RED = "#e06c75"
    ACCENT_RECORDING = DESTRUCTIVE

    # Legacy
    ACCENT_SUCCESS = SUCCESS

    # =================================================================
    # STATUS INDICATORS
    # =================================================================
    STATUS_RECORDING = DESTRUCTIVE
    STATUS_TRANSCRIBING = WARNING
    STATUS_SUCCESS = SUCCESS

    # =================================================================
    # BORDERS
    # =================================================================
    BORDER_DEFAULT = "#3c3c3c"
    BORDER_LIGHT = "#4c4c4c"
    BORDER_MEDIUM = BORDER_DEFAULT

    # Legacy alias
    BORDER_COLOR = BORDER_DEFAULT

    # =================================================================
    # INTERACTIVE STATES
    # =================================================================
    HOVER_BG = "#2d3d4d"          # Primary hover bg
    HOVER_OVERLAY = "rgba(255, 255, 255, 0.08)"
    PRESSED_OVERLAY = "rgba(255, 255, 255, 0.12)"
    SELECTED_BG = PRIMARY_PRESSED

    # Component-specific hover states
    HOVER_BG_SECTION = "#3a3a3a"
    HOVER_BG_DAY = "#333333"
    HOVER_BG_ITEM = "#2e2e2e"

    # Section headers
    SECTION_HEADER_BG = "#323e4e"
    SECTION_HEADER_HOVER = "#3d4f5f"

    # =================================================================
    # SPECIAL
    # =================================================================
    TRANSPARENT = "transparent"
    BUTTON_SECONDARY = "#3c3c3c"


class FocusGroupColors:
    """
    Darker color palette for Focus Groups.

    Design principles:
    - Darker colors for better contrast with white text
    - Full-width colored bars as section headers
    - Distinct enough for quick identification
    - Works on dark background
    """

    # Ordered palette - used for auto-assignment to new groups
    # Six distinct colors with good visual separation
    PALETTE = [
        "#3a5f7f",  # Deep Ocean Blue - cool, professional
        "#4f6b38",  # Forest Green - natural, earthy
        "#b8860b",  # Dark Goldenrod - warm, distinct
        "#8b5a9e",  # Amethyst Purple - rich, creative
        "#a04238",  # Brick Red - warm, grounded
        "#5a8e8e",  # Teal - cool, balanced
    ]

    # Color names for UI display
    COLOR_NAMES = {
        "#3a5f7f": "Ocean Blue",
        "#4f6b38": "Forest Green",
        "#b8860b": "Goldenrod",
        "#8b5a9e": "Amethyst",
        "#a04238": "Brick Red",
        "#5a8e8e": "Teal",
    }

    # Named colors for specific UI purposes
    SLATE = "#6b8fa3"
    TEAL = "#7ba89b"
    AMBER = "#c4a574"
    INDIGO = "#8b7bb8"
    ROSE = "#a87b8b"
    CYAN = "#7ba3a3"
    TAUPE = "#a89b7b"
    OLIVE = "#8b9b7b"
    LAVENDER = "#9b8ba8"
    SAND = "#a8947b"
    STEEL = "#7b8ba8"
    MOSS = "#8ba87b"

    @classmethod
    def get_next_color(cls, existing_colors: list[str | None]) -> str:
        """Get next available color from palette, cycling if exhausted."""
        used = set(c for c in existing_colors if c)
        for color in cls.PALETTE:
            if color not in used:
                return color
        # All colors used, cycle back to first
        return cls.PALETTE[0]
