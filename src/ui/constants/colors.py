"""
Color palette constants.

Dark theme colors for backgrounds, text, accents, borders, and status indicators.

Usage:
    from ui.constants import Colors
    widget.setStyleSheet(f"background: {Colors.BACKGROUND};")
"""


class Colors:
    """Application color palette."""

    # === Primary Backgrounds ===
    BACKGROUND = "#1e1e1e"  # Main window background
    SURFACE = "#252526"  # Panels, cards, dialogs
    SURFACE_ALT = "#2a2a2a"  # Alternate surface (list items)
    HEADER = "#1a1a1a"  # Section headers

    # Legacy aliases (for backward compatibility)
    BG_PRIMARY = BACKGROUND
    BG_SECONDARY = SURFACE
    BG_TERTIARY = SURFACE_ALT
    BG_HEADER = HEADER
    BG_SIDEBAR = SURFACE

    # === Text Colors ===
    TEXT_PRIMARY = "#d4d4d4"  # Main text
    TEXT_SECONDARY = "#888888"  # Muted text
    TEXT_TERTIARY = "#555555"  # Disabled/very muted text
    TEXT_MUTED = TEXT_TERTIARY  # Alias
    TEXT_ACCENT = "#5a9fd4"  # Blue accent text
    TEXT_GREETING = "#ffffff"  # Greeting text
    TEXT_ON_PRIMARY = "#ffffff"  # Text on primary color buttons
    TEXT_ON_ACCENT = "#ffffff"  # Text on accent color backgrounds

    # === Primary Accent ===
    PRIMARY = "#5a9fd4"  # Primary accent color
    PRIMARY_HOVER = "#6db3e8"  # Primary hover
    PRIMARY_PRESSED = "#2d5a7b"  # Primary pressed

    # Legacy accent aliases
    ACCENT_BLUE = PRIMARY
    ACCENT_BLUE_DARK = "#2d5a7b"
    ACCENT_BLUE_HOVER = PRIMARY_HOVER
    ACCENT_BLUE_BRIGHT = "#4a9fd4"
    ACCENT_BLUE_BRIGHT_HOVER = "#78c0ff"
    ACCENT_BLUE_PRESSED = PRIMARY_PRESSED

    # === Semantic Accents ===
    ACCENT_PRIMARY = PRIMARY
    ACCENT_HOVER = PRIMARY_HOVER
    ACCENT_PRESSED = PRIMARY_PRESSED
    ACCENT_RECORDING = "#ff6b6b"  # Recording state
    ACCENT_DESTRUCTIVE = "#ff6b6b"  # Delete/cancel actions
    ACCENT_SUCCESS = "#4caf50"  # Success state

    # === Green for Start button ===
    ACCENT_GREEN = "#2d6a4f"
    ACCENT_GREEN_HOVER = "#40916c"
    ACCENT_GREEN_PRESSED = "#1b4332"
    ACCENT_RED = "#e06c75"

    # === Destructive Actions ===
    DESTRUCTIVE = "#ff6b6b"
    DESTRUCTIVE_HOVER = "#5a2d2d"
    DESTRUCTIVE_IDLE = "#7a3535"
    DESTRUCTIVE_HOVER_BG = "#b54545"

    # === Status Colors ===
    STATUS_RECORDING = "#ff6b6b"
    STATUS_TRANSCRIBING = "#ffa500"
    STATUS_SUCCESS = "#4caf50"

    # === Borders ===
    BORDER_DEFAULT = "#3c3c3c"
    BORDER_COLOR = BORDER_DEFAULT  # Alias
    BORDER_LIGHT = "#4c4c4c"
    BORDER_MEDIUM = "#3c3c3c"
    BORDER_ACCENT = PRIMARY

    # === Hover/Selection ===
    HOVER_BG = "#2d3d4d"
    HOVER_OVERLAY = "rgba(255, 255, 255, 0.08)"
    PRESSED_OVERLAY = "rgba(255, 255, 255, 0.12)"
    HOVER_BG_SECTION = "#3a3a3a"
    HOVER_BG_DAY = "#333333"
    HOVER_BG_ITEM = "#2e2e2e"
    SELECTED_BG = "#2d5a7b"

    # === Section Headers ===
    SECTION_HEADER_BG = "#323e4e"
    SECTION_HEADER_HOVER = "#3d4f5f"

    # === Special ===
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
