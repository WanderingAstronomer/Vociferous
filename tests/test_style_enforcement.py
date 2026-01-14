"""
Style enforcement tests.
Ensures UI code conforms to styling invariants (Agent 5).
"""

import os
import re
import pytest
from pathlib import Path

# Paths to excludes
# Use absolute path resolution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
UI_ROOT = PROJECT_ROOT / "src" / "ui"
COLORS_FILE = UI_ROOT / "constants/colors.py"
THEME_FILE = UI_ROOT / "styles/theme.py"
STYLESHEET_REGISTRY = UI_ROOT / "styles/stylesheet_registry.py"

# Permitted specific files (if any)
EXCLUDED_FILES = {
    COLORS_FILE.resolve(),
    (UI_ROOT / "widgets/dialogs/create_project_dialog.py").resolve(), 
}

def get_ui_files():
    """Yield all Python files in src/ui."""
    for root, _, files in os.walk(UI_ROOT):
        for file in files:
            if file.endswith(".py"):
                yield Path(root) / file

def test_no_raw_colors_in_ui():
    """
    Invariant 2.1: No hard-coded colors (hex, rgb, rgba) appear in production widgets.
    Tokens must be used.
    """
    hex_pattern = re.compile(r'["\']#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})["\']')
    rgb_pattern = re.compile(r'["\']\s*rgba?\(', re.IGNORECASE)
    
    violations = []
    
    for file_path in get_ui_files():
        if file_path.resolve() in EXCLUDED_FILES:
            continue
            
        if "__pycache__" in str(file_path):
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue 
            
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if line.strip().startswith("#"):
                continue
            
            # Check Hex
            matches = hex_pattern.findall(line)
            if matches:
                violations.append(f"{file_path}:{i+1} found hex {matches}")
                
            # Check RGB/RGBA
            if rgb_pattern.search(line):
                violations.append(f"{file_path}:{i+1} found rgb/rgba")

    assert not violations, "Found hard-coded colors in UI files. Invariants restrict to ui.constants.Colors tokens:\n" + "\n".join(violations)

def test_no_large_inline_stylesheets():
    """
    Invariant 2.2: Widget-specific styles are loaded from styles modules or unified sheet.
    """
    # Heuristic: setStyleSheet with triple quotes implies a large block
    inline_block_pattern = re.compile(r'\.setStyleSheet\(\s*f?["\']{3}')
    
    violations = []
    
    for file_path in get_ui_files():
        if file_path.resolve() == (UI_ROOT / "components/main_window/main_window.py").resolve():
             pass

        if file_path.resolve() in EXCLUDED_FILES:
            continue
             
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
             continue
             
        if inline_block_pattern.search(content):
            violations.append(str(file_path))

    assert not violations, "Found large inline stylesheets. Move styles to unified_stylesheet.py or *_styles.py:\n" + "\n".join(violations)

def test_no_parallel_implementations():
    """
    Enforce single source of truth for styles.
    Check for 'delegate_new' or other migration markers in CONTENT.
    """
    violations = []
    for file_path in get_ui_files():
         # Check content for "delegate_new" or similar markers
         try:
             content = file_path.read_text(encoding="utf-8")
             if "delegate_new" in content:
                 violations.append(f"{file_path} contains 'delegate_new'")
         except Exception:
             pass
             
    assert not violations, "Found forbidden migration markers in UI files:\n" + "\n".join(violations)
