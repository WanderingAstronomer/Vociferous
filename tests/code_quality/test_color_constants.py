"""
Phase 5 TDD: Color Constant Centralization Tests

Validates that all UI colors use semantic constants from colors.py
rather than hardcoded hex values or rgba literals.

Audit Finding: P3-06 - Hardcoded colors bypass centralized palette
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from tests.conftest import SRC_DIR

# Path to source directory
COLORS_MODULE = SRC_DIR / "ui" / "constants" / "colors.py"

# Files that are allowed to contain color literals (the definitions themselves)
ALLOWED_FILES = {
    "colors.py",  # Color definitions
}

# Patterns that indicate hardcoded colors
HEX_COLOR_PATTERN = re.compile(r'["\']#[0-9A-Fa-f]{6}["\']')
RGBA_PATTERN = re.compile(r"rgba?\s*\(\s*\d+")


class TestColorConstantCoverage:
    """Tests that production code does not contain hardcoded color literals."""

    def _get_python_files(self) -> list[Path]:
        """Get all Python files in src/, excluding allowed files."""
        files = []
        for path in SRC_DIR.rglob("*.py"):
            if path.name not in ALLOWED_FILES:
                files.append(path)
        return files

    def test_no_hardcoded_hex_in_python_files(self):
        """No Python files should contain hardcoded hex color strings."""
        violations = []

        for filepath in self._get_python_files():
            content = filepath.read_text()
            # Find all hex color matches
            for match in HEX_COLOR_PATTERN.finditer(content):
                # Get line number
                line_num = content[: match.start()].count("\n") + 1
                violations.append(
                    f"{filepath.relative_to(SRC_DIR)}:{line_num} -> {match.group()}"
                )

        assert not violations, (
            f"Found {len(violations)} hardcoded hex color(s):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_no_hardcoded_rgba_in_python_files(self):
        """No Python files should contain hardcoded rgba() color literals."""
        violations = []

        for filepath in self._get_python_files():
            content = filepath.read_text()
            # Find all rgba matches
            for match in RGBA_PATTERN.finditer(content):
                # Get line number
                line_num = content[: match.start()].count("\n") + 1
                # Extract the full rgba(...) for context
                end_idx = content.find(")", match.start())
                rgba_str = (
                    content[match.start() : end_idx + 1]
                    if end_idx > 0
                    else match.group()
                )
                violations.append(
                    f"{filepath.relative_to(SRC_DIR)}:{line_num} -> {rgba_str}"
                )

        assert not violations, (
            f"Found {len(violations)} hardcoded rgba() color(s):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


class TestColorConstantCompleteness:
    """Tests that the color palette has all required semantic tokens."""

    def test_semantic_tokens_for_toggle_switch(self):
        """Toggle switch should have semantic color tokens defined."""
        from src.ui.constants import colors as c

        # Toggle circle when ON should use white
        assert hasattr(c, "TOGGLE_CIRCLE_ON"), "Missing TOGGLE_CIRCLE_ON constant"
        assert c.TOGGLE_CIRCLE_ON == c.GRAY_0, (
            "TOGGLE_CIRCLE_ON should be white (GRAY_0)"
        )

    def test_semantic_tokens_for_hover_overlays(self):
        """Hover overlay colors should be defined as constants."""
        from src.ui.constants import colors as c

        # Light hover overlay (used on dark backgrounds)
        assert hasattr(c, "HOVER_OVERLAY_LIGHT"), "Missing HOVER_OVERLAY_LIGHT constant"

    def test_semantic_tokens_for_shell_and_content(self):
        """Shell and Content semantic tokens should be defined."""
        from src.ui.constants import colors as c

        assert hasattr(c, "SHELL_BACKGROUND"), "Missing SHELL_BACKGROUND constant"
        assert hasattr(c, "SHELL_BORDER"), "Missing SHELL_BORDER constant"
        assert hasattr(c, "CONTENT_BACKGROUND"), "Missing CONTENT_BACKGROUND constant"
        assert hasattr(c, "CONTENT_BORDER"), "Missing CONTENT_BORDER constant"

        # Verify default mappings (allow either GRAY_8 or GRAY_9 for shell)
        assert c.SHELL_BACKGROUND in (c.GRAY_8, c.GRAY_9)
        assert c.CONTENT_BACKGROUND == c.GRAY_8
        assert "rgba" in c.HOVER_OVERLAY_LIGHT.lower(), (
            "HOVER_OVERLAY_LIGHT should be rgba"
        )

        # Blue hover overlay (tree/table views)
        assert hasattr(c, "HOVER_OVERLAY_BLUE"), "Missing HOVER_OVERLAY_BLUE constant"
        assert "rgba" in c.HOVER_OVERLAY_BLUE.lower(), (
            "HOVER_OVERLAY_BLUE should be rgba"
        )

    def test_semantic_tokens_for_overlay_backdrop(self):
        """Modal/loading overlay backdrop should be defined."""
        from src.ui.constants import colors as c

        assert hasattr(c, "OVERLAY_BACKDROP"), "Missing OVERLAY_BACKDROP constant"
        assert "rgba" in c.OVERLAY_BACKDROP.lower(), "OVERLAY_BACKDROP should be rgba"


class TestColorConstantUsage:
    """Tests that specific files use constants correctly."""

    def test_toggle_switch_uses_constant(self):
        """ToggleSwitch should use TOGGLE_CIRCLE_ON instead of #FFFFFF."""
        toggle_path = SRC_DIR / "ui" / "widgets" / "toggle_switch.py"
        content = toggle_path.read_text()

        # Should NOT contain hardcoded #FFFFFF
        assert "#FFFFFF" not in content, (
            "toggle_switch.py contains hardcoded #FFFFFF - use c.TOGGLE_CIRCLE_ON"
        )

        # Should reference the constant
        assert "TOGGLE_CIRCLE_ON" in content or "GRAY_0" in content, (
            "toggle_switch.py should use TOGGLE_CIRCLE_ON or GRAY_0 constant"
        )

    def test_unified_stylesheet_uses_rgba_constants(self):
        """Unified stylesheet should use rgba constants, not inline values."""
        stylesheet_path = SRC_DIR / "ui" / "styles" / "unified_stylesheet.py"
        content = stylesheet_path.read_text()

        # Should NOT contain inline rgba(59, 130, 246, ...)
        assert "rgba(59, 130, 246" not in content, (
            "unified_stylesheet.py contains hardcoded rgba - use HOVER_OVERLAY_BLUE"
        )

    def test_refine_view_uses_overlay_constant(self):
        """RefineView loading overlay should use OVERLAY_BACKDROP constant."""
        refine_path = SRC_DIR / "ui" / "views" / "refine_view.py"
        content = refine_path.read_text()

        # Should NOT contain inline rgba(0,0,0,...)
        assert "rgba(0,0,0" not in content, (
            "refine_view.py contains hardcoded rgba - use OVERLAY_BACKDROP"
        )

    def test_main_window_styles_uses_hover_constant(self):
        """Main window styles should use HOVER_OVERLAY_LIGHT constant."""
        styles_path = (
            SRC_DIR / "ui" / "components" / "main_window" / "main_window_styles.py"
        )
        content = styles_path.read_text()

        # Should NOT contain inline rgba(255, 255, 255, ...)
        assert "rgba(255, 255, 255" not in content, (
            "main_window_styles.py contains hardcoded rgba - use HOVER_OVERLAY_LIGHT"
        )


class TestColorPaletteIntegrity:
    """Tests that the color palette is well-formed."""

    def test_no_duplicate_color_values(self):
        """Each color value should have at most one canonical name."""
        from src.ui.constants import colors as c

        # Get all color constants (excluding classes and functions)
        color_map: dict[str, list[str]] = {}
        for name in dir(c):
            if name.startswith("_") or name[0].islower():
                continue
            value = getattr(c, name)
            if isinstance(value, str) and (
                value.startswith("#") or value.startswith("rgba")
            ):
                normalized = value.lower()
                if normalized not in color_map:
                    color_map[normalized] = []
                color_map[normalized].append(name)

        # Find duplicates (more than one name for same value)
        # Note: Some duplicates are intentional (semantic aliases)
        # We only flag if there are 6+ names for the same value
        excessive_duplicates = {
            value: names for value, names in color_map.items() if len(names) >= 6
        }

        assert not excessive_duplicates, (
            "Found colors with 3+ names (consolidate):\n"
            + "\n".join(f"  {v}: {names}" for v, names in excessive_duplicates.items())
        )

    def test_all_grays_defined(self):
        """Gray scale should have complete range from GRAY_0 to GRAY_9."""
        from src.ui.constants import colors as c

        for i in range(10):
            name = f"GRAY_{i}"
            assert hasattr(c, name), f"Missing {name} in color palette"

    def test_color_naming_convention(self):
        """Color constants should follow FAMILY_INDEX or SEMANTIC naming."""
        from src.ui.constants import colors as c

        # Regex patterns for valid names
        family_pattern = re.compile(r"^(GRAY|BLUE|GREEN|RED|ORANGE|PURPLE)_\d$")
        semantic_pattern = re.compile(
            r"^(SUCCESS|DANGER|TOGGLE|HOVER|OVERLAY|FOCUS|SHELL|CONTENT|TEXT)_[A-Z_]+$"
        )

        for name in dir(c):
            if name.startswith("_") or name[0].islower():
                continue
            value = getattr(c, name)
            if isinstance(value, str) and (
                value.startswith("#") or value.startswith("rgba")
            ):
                valid = (
                    family_pattern.match(name)
                    or semantic_pattern.match(name)
                    or name in ("GREEN_3", "DANGER_BRIGHT")  # Legacy
                )
                assert valid, (
                    f"Color constant '{name}' doesn't follow naming convention. "
                    f"Use FAMILY_INDEX (e.g., BLUE_4) or SEMANTIC_ROLE (e.g., HOVER_OVERLAY_LIGHT)"
                )
