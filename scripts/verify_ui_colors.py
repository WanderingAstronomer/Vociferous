import sys
import os
import ast
import re
from pathlib import Path


def main():
    # Assume script is in scripts/ folder
    current_file = Path(__file__).resolve()
    # scripts/ -> root -> src
    root_dir = current_file.parent.parent / "src"
    if not root_dir.exists():
        # Fallback if running from a different location
        root_dir = Path("src").resolve()

    ui_dir = root_dir / "ui"

    hex_pattern = re.compile(r"#[0-9a-fA-F]{3,6}\b")
    violations = []

    excluded_dirs = [
        ui_dir / "constants",
        ui_dir / "styles",
    ]

    # Legacy widgets with pre-existing hardcoded colors
    excluded_files = {
        (ui_dir / "widgets/dialogs/create_project_dialog.py").resolve(),
        (ui_dir / "widgets/toggle_switch.py").resolve(),
        (
            ui_dir
            / "widgets/visualizers/bar_spectrum_visualizer/bar_spectrum_visualizer.py"
        ).resolve(),
    }

    for root, dirs, files in os.walk(ui_dir):
        root_path = Path(root)

        # Skip excluded directories
        should_skip = False
        for ex_dir in excluded_dirs:
            if root_path == ex_dir or ex_dir in root_path.parents:
                should_skip = True
                break
        if should_skip:
            continue

        if "__pycache__" in root:
            continue

        for filename in files:
            if not filename.endswith(".py"):
                continue

            filepath = root_path / filename

            # Skip excluded files
            try:
                if filepath.resolve() in excluded_files:
                    continue
            except OSError:
                continue

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    tree = ast.parse(content, filename=str(filepath))
            except (SyntaxError, UnicodeDecodeError):
                continue

            class StringVisitor(ast.NodeVisitor):
                def visit_Constant(self, node):
                    if isinstance(node.value, str):
                        matches = hex_pattern.findall(node.value)
                        if matches:
                            rel_path = filepath.relative_to(root_dir)
                            violations.append(
                                f"{rel_path}:{node.lineno} hex colors found {matches[:3]}..."
                            )
                    self.generic_visit(node)

            StringVisitor().visit(tree)

    if violations:
        print("Invariant 2.1 Violation: Hard-coded hex colors found in UI code.")
        print("Use tokens from ui.constants.colors or ui.styles.theme instead.")
        for v in violations:
            print(v)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
