"""
Style enforcement tests.
Ensures UI code conforms to styling invariants (Agent 5).
"""

import os
import re
import pytest
from pathlib import Path

# Paths to excludes
UI_ROOT = Path("src/ui")
COLORS_FILE = UI_ROOT / "constants/colors.py"
THEME_FILE = UI_ROOT / "styles/theme.py" # Maybe exclude this one too if it has defaults
STYLESHEET_REGISTRY = UI_ROOT / "styles/stylesheet_registry.py" # Might map things

# Permitted specific files (if any)
EXCLUDED_FILES = {
    COLORS_FILE.resolve(),
    # create_group_dialog.py uses strictly necessary dynamic inline styles for user-selected colors
    (UI_ROOT / "widgets/dialogs/create_group_dialog.py").resolve(), 
    # We permit some inline hex in specialized graphics code if strictly necessary, but ideally none.
}

def get_ui_files():
    """Yield all Python files in src/ui."""
    for root, _, files in os.walk(UI_ROOT):
        for file in files:
            if file.endswith(".py"):
                yield Path(root) / file

def test_no_raw_hex_colors_in_ui():
    """
    Invariant 2.1: No hard-coded hex colors appear in production widgets.
    Tokens must be used.
    """
    hex_pattern = re.compile(r'["\']#[0-9a-fA-F]{6}["\']')
    
    violations = []
    
    for file_path in get_ui_files():
        if file_path.resolve() in EXCLUDED_FILES:
            continue
            
        # Also exclude __pycache__ just in case
        if "__pycache__" in str(file_path):
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue # Skip binary
            
        lines = content.splitlines()
        for i, line in enumerate(lines):
            # Skip comments
            if line.strip().startswith("#"):
                continue
                
            matches = hex_pattern.findall(line)
            if matches:
                violations.append(f"{file_path}:{i+1} found {matches}")

    assert not violations, "Found raw hex colors in UI files. Use ui.constants.Colors tokens:\n" + "\n".join(violations)

def test_no_large_inline_stylesheets():
    """
    Invariant 2.2: Widget-specific styles are loaded from styles modules or unified sheet.
    Large inline setStyleSheet blocks are banned.
    """
    # Heuristic: setStyleSheet with triple quotes implies a large block
    inline_block_pattern = re.compile(r'\.setStyleSheet\(\s*f?["\']{3}')
    
    violations = []
    
    for file_path in get_ui_files():
        if file_path.resolve() == Path("src/ui/components/main_window/main_window.py").resolve():
             # Main window applies the GLOBAL stylesheet, so it might have setStyleSheet call, 
             # but it shouldn't have an inline block definition.
             pass

        if file_path.resolve() in EXCLUDED_FILES:
            continue
             
        content = file_path.read_text(encoding="utf-8")
        if inline_block_pattern.search(content):
            violations.append(str(file_path))

    assert not violations, "Found large inline stylesheets. Move styles to unified_stylesheet.py or *_styles.py:\n" + "\n".join(violations)

def test_no_parallel_implementations():
    """
    Invariant 1.3: No *_new.py files.
    """
    violations = []
    for file_path in get_ui_files():
        if file_path.name.endswith("_new.py") or "delegate_new" in file_path.name:
            violations.append(str(file_path))
            
    assert not violations, "Found banned parallel implementation files (*_new.py):\n" + "\n".join(violations)
