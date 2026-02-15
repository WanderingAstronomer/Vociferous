"""
Pytest configuration for Vociferous (v4).

Minimal configuration to support architectural contracts and code quality checks.
Legacy UI/PyQt fixtures have been removed during the v4 migration.
"""

from pathlib import Path
import sys

# Project root - resolve from this conftest location (tests/conftest.py -> tests -> project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))
