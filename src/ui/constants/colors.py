"""
Canonical color palette for Vociferous UI.

Naming Convention:
- Colors are named by family (e.g., GRAY, BLUE) and index (0-9).
- Lower index = lighter color; higher index = darker color.
- Only colors used in the UI are defined here.

Purpose:
- Centralize color definitions for consistency.
- Facilitate easy updates to the color scheme.
"""

# Grays
GRAY_0 = "#ffffff"
GRAY_1 = "#e0e0e0"
GRAY_2 = "#d4d4d4"
GRAY_3 = "#bbbbbb"
GRAY_4 = "#888888"
GRAY_5 = "#555555"
GRAY_6 = "#4c4c4c"
GRAY_7 = "#3c3c3c"
GRAY_8 = "#2a2a2a"
GRAY_9 = "#1e1e1e"

# Blues
BLUE_0 = "#e6f0fa"
BLUE_1 = "#cce0f5"
BLUE_2 = "#99c2ed"
BLUE_3 = "#6db3e8"
BLUE_4 = "#5a9fd4"
BLUE_5 = "#4a8ac0"
BLUE_6 = "#3d4f5f"
BLUE_7 = "#2d5a7b"
BLUE_8 = "#2d3d4d"
BLUE_9 = "#1a252e"

# Greens
GREEN_0 = "#e6fae6"
GREEN_1 = "#ccf5cc"
GREEN_2 = "#a8e6a8"
GREEN_3 = "#7ee37e"
GREEN_4 = "#5bc95f"
GREEN_5 = "#4caf50"
GREEN_6 = "#3e7d3e"
GREEN_7 = "#3d8b40"
GREEN_8 = "#2a522a"
GREEN_9 = "#1a351a"

# Reds
RED_4 = "#ff8585"
RED_5 = "#ff6b6b"
RED_7 = "#cc5656"
RED_8 = "#7a3535"
RED_9 = "#5a2d2d"
DANGER_BRIGHT = "#ff5555"  # Onboarding Cancel

# Orange
ORANGE_4 = "#ffb733"
ORANGE_5 = "#ffa500"
ORANGE_7 = "#cc8400"

# Purple
PURPLE_4 = "#9d46f0"
PURPLE_5 = "#8a2be2"
PURPLE_7 = "#5e1d9b"
PURPLE_9 = "#2a0a44"

# =============================================================================
# Semantic Tokens (Phase 5 TDD - Color Constant Centralization)
# =============================================================================

# Toggle Switch
TOGGLE_CIRCLE_ON = GRAY_0  # White circle when toggle is ON

# Hover Overlays (semi-transparent overlays for interactive states)
HOVER_OVERLAY_LIGHT = "rgba(255, 255, 255, 0.08)"  # Light overlay on dark backgrounds
HOVER_OVERLAY_BLUE = (
    "rgba(59, 130, 246, 0.08)"  # Blue-tinted hover for tree/table views
)

# Modal/Loading Overlays
OVERLAY_BACKDROP = "rgba(0, 0, 0, 0.5)"  # Semi-transparent black for modal backdrops

# Shell Elements (TitleBar, IconRail)
SHELL_BACKGROUND = GRAY_9
SHELL_BORDER = GRAY_7

# Content Surfaces
CONTENT_BACKGROUND = GRAY_8
CONTENT_BORDER = BLUE_4

# Text Hierarchy
TEXT_PRIMARY = GRAY_2
TEXT_SECONDARY = GRAY_4
TEXT_TERTIARY = GRAY_5
# Removed TEXT_ACCENT because #5a9fd4 already has BLUE_4 and CONTENT_BORDER names (3 max names limit in tests)


class ProjectColors:
    """
    Project-specific color selection utilities.

    Uses canonical color constants.
    """

    # User-facing names for the colors (mapped to canonical values)
    COLOR_NAMES = {
        BLUE_7: "Ocean Blue",
        GREEN_7: "Forest Green",
        ORANGE_7: "Goldenrod",
        PURPLE_7: "Amethyst",
        RED_8: "Brick Red",
        BLUE_4: "Teal",
    }

    # Ordered palette - used for auto-assignment to new groups
    # Six distinct colors with good visual separation
    PALETTE = [
        BLUE_7,
        GREEN_7,
        ORANGE_7,
        PURPLE_7,
        RED_8,
        BLUE_4,
    ]

    @classmethod
    def get_next_color(cls, existing_colors: list[str | None]) -> str:
        """Get next available color from palette, cycling if exhausted."""
        used = set(c for c in existing_colors if c)
        for color in cls.PALETTE:
            if color not in used:
                return color
        # All colors used, cycle back to first
        return cls.PALETTE[0]
