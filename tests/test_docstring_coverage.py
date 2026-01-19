"""
Phase 5.2 TDD: Docstring Coverage Tests

Validates that priority architectural components have proper docstrings
for maintainability and API documentation.

Scope: Focus on core architectural files (Intent Pattern, Views, Widgets)
rather than exhaustive coverage of all 148+ undocumented items.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# Path to source directory
SRC_DIR = Path(__file__).parent.parent / "src"

# Priority files that MUST have complete docstring coverage
PRIORITY_FILES = [
    "ui/views/base_view.py",
    "ui/interaction/intents.py",
    # "ui/interaction/router.py", # File not found/removed
    "ui/contracts/capabilities.py",
    "ui/widgets/toggle_switch.py",
    "ui/components/shared/content_panel.py",
]


def get_missing_docstrings(filepath: Path) -> list[str]:
    """
    Parse a Python file and return list of classes/functions missing docstrings.

    Args:
        filepath: Path to Python file to analyze

    Returns:
        List of "line:type name" strings for items missing docstrings
    """
    missing = []
    try:
        tree = ast.parse(filepath.read_text())
    except SyntaxError:
        return [f"SYNTAX_ERROR in {filepath}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if not ast.get_docstring(node):
                missing.append(f"{node.lineno}:class {node.name}")
        elif isinstance(node, ast.FunctionDef):
            # Skip private methods (except __init__ which should be documented)
            if node.name.startswith("_") and node.name != "__init__":
                continue
            if not ast.get_docstring(node):
                missing.append(f"{node.lineno}:def {node.name}")

    return missing


class TestDocstringCoverageArchitectural:
    """Tests that priority architectural files have complete docstrings."""

    @pytest.mark.parametrize("relpath", PRIORITY_FILES)
    def test_priority_file_has_docstrings(self, relpath: str):
        """Each priority file should have docstrings on all public classes/methods."""
        filepath = SRC_DIR / relpath
        if not filepath.exists():
            pytest.skip(f"File not found: {relpath}")

        missing = get_missing_docstrings(filepath)

        assert not missing, (
            f"{relpath} has {len(missing)} item(s) missing docstrings:\n"
            + "\n".join(f"  Line {m}" for m in missing)
        )


class TestDocstringQuality:
    """Tests for docstring content quality (not just presence)."""

    def test_base_view_class_has_descriptive_docstring(self):
        """BaseView class docstring should describe its purpose."""
        filepath = SRC_DIR / "ui" / "views" / "base_view.py"
        tree = ast.parse(filepath.read_text())

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "BaseView":
                docstring = ast.get_docstring(node)
                assert docstring is not None, "BaseView class missing docstring"
                assert len(docstring) > 20, "BaseView docstring too short"
                assert "view" in docstring.lower(), (
                    "BaseView docstring should mention 'view'"
                )
                return

        pytest.fail("BaseView class not found")

    def test_toggle_switch_class_has_descriptive_docstring(self):
        """ToggleSwitch class docstring should describe its purpose."""
        filepath = SRC_DIR / "ui" / "widgets" / "toggle_switch.py"
        tree = ast.parse(filepath.read_text())

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "ToggleSwitch":
                docstring = ast.get_docstring(node)
                assert docstring is not None, "ToggleSwitch class missing docstring"
                assert len(docstring) > 20, "ToggleSwitch docstring too short"
                return

        pytest.fail("ToggleSwitch class not found")

    def test_content_panel_class_has_descriptive_docstring(self):
        """ContentPanel class docstring should describe its purpose."""
        filepath = SRC_DIR / "ui" / "components" / "shared" / "content_panel.py"
        tree = ast.parse(filepath.read_text())

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "ContentPanel":
                docstring = ast.get_docstring(node)
                assert docstring is not None, "ContentPanel class missing docstring"
                assert len(docstring) > 20, "ContentPanel docstring too short"
                return

        pytest.fail("ContentPanel class not found")


class TestDocstringConventions:
    """Tests that docstrings follow project conventions."""

    def test_init_methods_document_parameters(self):
        """__init__ methods in priority files should document their parameters."""
        # Sample check on one file - BaseView
        filepath = SRC_DIR / "ui" / "views" / "base_view.py"
        tree = ast.parse(filepath.read_text())

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "__init__":
                docstring = ast.get_docstring(node)
                assert docstring is not None, "__init__ missing docstring"
                # Check for Args section if there are parameters beyond self
                if len(node.args.args) > 1:  # More than just 'self'
                    assert (
                        "args" in docstring.lower() or "param" in docstring.lower()
                    ), "__init__ with parameters should document them"
                return

        pytest.fail("__init__ not found in BaseView")
