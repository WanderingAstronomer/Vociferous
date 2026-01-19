"""
Phase 5.3 TDD: Magic Number Extraction Tests

Validates that layout dimensions, durations, and sizes use named constants
instead of hardcoded integer literals.

Scope: Focus on high-reuse components like ToggleSwitch and ContentPanel.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).parent.parent / "src"


class TestMagicNumberExtraction:
    """Tests for hardcoded numeric literals in UI components."""

    def test_toggle_switch_constants(self):
        """ToggleSwitch should not contain hardcoded dimensions."""
        filepath = SRC_DIR / "ui" / "widgets" / "toggle_switch.py"
        content = filepath.read_text()
        tree = ast.parse(content)

        magic_numbers = []
        allowed_numbers = {0, 1}  # 0 and 1 are usually safe (logic, indices)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check for setFixedSize(50, 24)
                if (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "setFixedSize"
                ):
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, int):
                            magic_numbers.append(f"setFixedSize({arg.value})")

                # Check for drawRoundedRect inputs
                if (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "drawRoundedRect"
                ):
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, int):
                            if arg.value not in allowed_numbers:
                                magic_numbers.append(f"drawRoundedRect({arg.value})")

            # Check for assignments like _circle_position = 3
            if isinstance(node, ast.Assign):
                if isinstance(node.value, ast.Constant) and isinstance(
                    node.value.value, int
                ):
                    if node.value.value not in allowed_numbers:
                        # Crude filtering to find likely layout constants
                        magic_numbers.append(f"assignment={node.value.value}")

        # We specifically want to eliminate 50, 24, 3, 12, 18, 29, 200
        target_literals = {"50", "24", "3", "12", "18", "29", "200"}
        found_targets = [
            m for m in magic_numbers if any(t in m for t in target_literals)
        ]

        assert not found_targets, (
            f"Found magic numbers in ToggleSwitch: {found_targets}. "
            "Extract to src/ui/constants/dimensions.py"
        )

    def test_content_panel_constants(self):
        """ContentPanel should not contain hardcoded margins/spacing."""
        filepath = SRC_DIR / "ui" / "components" / "shared" / "content_panel.py"
        content = filepath.read_text()

        # Check for setContentsMargins(32, 24, 32, 24)
        if "setContentsMargins(32, 24, 32, 24)" in content:
            pytest.fail("Found hardcoded margins (32, 24) in ContentPanel")

        # Check for setSpacing(12)
        if "setSpacing(12)" in content:
            pytest.fail("Found hardcoded spacing (12) in ContentPanel")
