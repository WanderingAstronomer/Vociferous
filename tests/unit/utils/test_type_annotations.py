"""
Phase 5.5 TDD: Type Annotation Enforcement

Enforces mandatory type hints for function arguments and return values
in critical architectural components.

Scope:
- CommandBus (Core)
- IconRail (UI Component)
- MainWindow (UI Orchestrator)
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from tests.conftest import SRC_DIR


class TestTypeAnnotations:
    """Enforces type annotations in key files."""

    def _check_file_annotations(self, filepath: Path):
        """Parse file and check recursively for untyped functions."""
        assert filepath.exists(), f"File not found: {filepath}"

        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        missing_annotations = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Skip private methods if desired, but strict mode implies ALL.
                # Let's start with ALL methods, maybe excluding __init__ return (optional usually)
                # but good style requires -> None.

                func_name = node.name

                # Check return annotation
                if node.returns is None:
                    # __init__ often implicitly None, but we want explicit -> None
                    # for strictness, or at least consistent.
                    missing_annotations.append(f"{func_name} missing return annotation")

                # Check argument annotations
                for arg in node.args.args:
                    if arg.arg == "self":
                        continue
                    if arg.annotation is None:
                        missing_annotations.append(
                            f"{func_name} arg '{arg.arg}' missing annotation"
                        )

        if missing_annotations:
            pytest.fail(
                f"Type annotation errors in {filepath.name}:\n"
                + "\n".join(missing_annotations)
            )

    def test_annotations_command_bus(self):
        self._check_file_annotations(SRC_DIR / "core" / "command_bus.py")

    def test_annotations_icon_rail(self):
        self._check_file_annotations(
            SRC_DIR / "ui" / "components" / "main_window" / "icon_rail.py"
        )

    def test_annotations_main_window(self):
        self._check_file_annotations(
            SRC_DIR / "ui" / "components" / "main_window" / "main_window.py"
        )
