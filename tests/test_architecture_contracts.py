"""
Architecture Contracts - Enforcing Orchestration Decoupling.

This test file ensures that the Orchestrator (src/main.py) does not
traverse deeply into the UI hierarchy to retrieve state.
"""

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
SRC_ROOT = PROJECT_ROOT / "src"

class TestOrchestratorDecoupling:
    """Enforce separation between Orchestrator and UI details."""

    def test_orchestrator_no_ui_traversal(self) -> None:
        """
        The Orchestrator must not access `self.main_window.workspace.content`.
        Data must be passed via signals/intents.
        """
        main_py = SRC_ROOT / "main.py"
        if not main_py.exists():
            return  # Skip if main.py is missing (e.g. testing env)

        tree = ast.parse(main_py.read_text(encoding="utf-8"))
        violations = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                # Check for .content access
                if node.attr == "content":
                    # Check parent for .workspace
                    if isinstance(node.value, ast.Attribute) and node.value.attr == "workspace":
                         # Check parent for .main_window
                         if isinstance(node.value.value, ast.Attribute) and node.value.value.attr == "main_window":
                             # Check parent for .self
                             if isinstance(node.value.value.value, ast.Name) and node.value.value.value.id == "self":
                                 violations.append(
                                     f"Line {node.lineno}: Direct access to `self.main_window.workspace.content` is forbidden. "
                                     "Pass data via Signal or Intent payload instead."
                                 )
        
        if violations:
            pytest.fail("\n".join(violations))
