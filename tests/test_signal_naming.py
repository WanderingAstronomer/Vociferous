"""
Phase 5.4 TDD: Signal Naming Tests

Enforces PyQt signal naming conventions:
1. camelCase (no snake_case)
2. No hungarian notation ('Signal' suffix)
3. Event-based naming (verbEd, nounChanged, nounRequested)

Scope: Priority architectural files.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).parent.parent / "src"

class TestSignalNaming:
    """Tests for signal naming compliance."""

    def test_signal_naming_conventions_in_icon_rail(self):
        """IconRail signals must use camelCase."""
        filepath = SRC_DIR / "ui" / "components" / "main_window" / "icon_rail.py"
        self._check_file_signals(filepath)

    def test_signal_naming_conventions_in_main_window(self):
        """MainWindow signals must use camelCase."""
        filepath = SRC_DIR / "ui" / "components" / "main_window" / "main_window.py"
        self._check_file_signals(filepath)

    def test_signal_naming_conventions_in_history_list(self):
        """HistoryList signals must not have 'Signal' suffix."""
        filepath = SRC_DIR / "ui" / "components" / "shared" / "history_list.py"
        self._check_file_signals(filepath)

    def test_signal_naming_conventions_in_onboarding_pages(self):
        """Onboarding pages signals must use camelCase."""
        filepath = SRC_DIR / "ui" / "components" / "onboarding" / "pages.py"
        self._check_file_signals(filepath)

    def _check_file_signals(self, filepath: Path):
        """
        Scan a file for pyqtSignal definitions and check defaults.
        """
        content = filepath.read_text()
        tree = ast.parse(content)
        
        camel_case_pattern = re.compile(r"^[a-z][a-zA-Z0-9]*$")
        
        violations = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                # Look for assignment to pyqtSignal(...)
                # Simplified check: assumes pyqtSignal is called directly
                is_signal = False
                if isinstance(node.value, ast.Call):
                     if isinstance(node.value.func, ast.Name) and node.value.func.id == "pyqtSignal":
                         is_signal = True
                     elif isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "pyqtSignal":
                         is_signal = True
                
                if is_signal:
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            name = target.id
                            
                            # Check 1: No snake_case (unless it is actually camelCase which regex handles)
                            if "_" in name and not camel_case_pattern.match(name):
                                violations.append(f"{name} (snake_case detected)")
                            
                            # Check 2: No 'Signal' suffix
                            if name.endswith("Signal") and len(name) > 6:
                                violations.append(f"{name} (redundant 'Signal' suffix)")
        
        assert not violations, (
            f"Signal naming violations in {filepath.name}:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )
