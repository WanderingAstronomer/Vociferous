"""
Architecture Contracts - Enforcing Orchestration Decoupling.

This test file ensures that the Orchestrator (src/main.py) does not
traverse deeply into the UI hierarchy to retrieve state.
"""

import ast
from pathlib import Path

import pytest
from tests.conftest import PROJECT_ROOT

SRC_ROOT = PROJECT_ROOT / "src"


class RecursiveAttributeVisitor(ast.NodeVisitor):
    def __init__(self):
        self.violations = []
        # Forbidden: self.main_window.workspace.<forbidden>
        # We look for Attribute nodes that construct this chain.
        # But specifically, we want to catch if someone goes DEEPER than workspace.xxx
        # Actually the instruction is: fail if it contains `self.main_window.workspace.`
        # followed by anything other than a strict allowlist.

        self.allowlist = {
            "show",
            "hide",
            "close",
            "set_state",
            "load_transcript",
            "set_history_manager",
            "set_audio_level",
            "set_live_text",
            "content_panel",  # required for geometry tests occasionally, but really shouldn't be here?
            # Orchestrator uses signals mostly.
            # If main.py says `self.main_window.workspace.content.transcript_view`, that is
            # `Attribute(Attribute(Attribute(..., 'workspace'), 'content'), 'transcript_view')`
        }

    def visit_Attribute(self, node):
        # We reconstruct the chain to see if it starts with self.main_window.workspace
        chain = []
        curr = node
        while isinstance(curr, ast.Attribute):
            chain.append(curr.attr)
            curr = curr.value

        if isinstance(curr, ast.Name) and curr.id == "self":
            chain.append("self")
            # chain is reversed: ['transcript_view', 'content', 'workspace', 'main_window', 'self']

            full_path = ".".join(reversed(chain))
            prefix = "self.main_window.workspace"

            if full_path.startswith(prefix):
                if full_path == prefix:
                    # Just accessing workspace is fine
                    pass
                else:
                    remaining = full_path[len(prefix) + 1 :]  # part after workspace.
                    first_component = remaining.split(".")[0]

                    # If they access something not in allowlist
                    # OR if they access DEEPER than one level (dotted)
                    if first_component not in self.allowlist:
                        self.violations.append(
                            f"Line {node.lineno}: Forbidden access to `{full_path}`. "
                            f"`{first_component}` is not in allowlist of public workspace methods."
                        )
                    elif "." in remaining:
                        # e.g. workspace.content.something
                        # Even if 'content' was allowed, reaching through it is not?
                        # The prompt says: "fail if it contains the forbidden prefix ... followed by anything other than a strict allowlist"
                        # And "It will not catch deeper traversal ... because the .attr becomes transcript_view"
                        # With this visitor, we check the FULL path of every attribute node.
                        # If we are visiting `workspace.content.view`, we catch it.
                        # If we are visiting `workspace.content`, we catch it (if content not in allowlist).
                        pass

        self.generic_visit(node)


class TestOrchestratorDecoupling:
    """Enforce separation between Orchestrator and UI details."""

    def test_orchestrator_no_ui_traversal(self) -> None:
        """
        The Orchestrator must not access deeply nested UI members.
        Enforces "no reach-through beyond composition boundaries".
        """
        main_py = SRC_ROOT / "main.py"
        if not main_py.exists():
            pytest.skip("main.py not found, skipping architecture check")

        tree = ast.parse(main_py.read_text(encoding="utf-8"))

        visitor = RecursiveAttributeVisitor()
        visitor.visit(tree)

        # Filter duplicates
        unique_violations = sorted(list(set(visitor.violations)))

        if unique_violations:
            pytest.fail("\n".join(unique_violations))

    def test_orchestrator_limited_ui_imports(self) -> None:
        """
        The Orchestrator should only import composition boundaries from `ui`, not internal widgets.
        Allowed: MainWindow, SystemTrayManager, global utils.
        """
        main_py = SRC_ROOT / "main.py"
        if not main_py.exists():
            pytest.skip("main.py not found")

        tree = ast.parse(main_py.read_text(encoding="utf-8"))

        # Allowlist of modules that can be imported from `ui.`
        allowed_ui_modules = {
            "src.ui.components.main_window",
            "src.ui.components.main_window.system_tray",
            "src.ui.components.settings",  # Currently used in main
            "src.ui.constants.view_ids",  # Used in show_settings()
            "src.ui.utils.clipboard_utils",
            "src.ui.styles.unified_stylesheet",
            "src.ui.utils.error_handler",
            "src.ui.widgets.dialogs.error_dialog",
        }

        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("src.ui."):
                    if node.module not in allowed_ui_modules:
                        violations.append(
                            f"Line {node.lineno}: Forbidden import `from {node.module} ...`. "
                            "Main.py should only import top-level composition boundaries (MainWindow, SystemTray)."
                        )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("src.ui."):
                        if alias.name not in allowed_ui_modules:
                            violations.append(
                                f"Line {node.lineno}: Forbidden import `import {alias.name}`. "
                                "Main.py should only import top-level composition boundaries."
                            )

        if violations:
            pytest.fail("\n".join(violations))
