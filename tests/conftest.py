"""
Pytest configuration for Vociferous (v4).

Minimal configuration to support architectural contracts and code quality checks.
"""

from pathlib import Path
import sys

# Project root — ensures `from src.core.xxx import ...` works from tests.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
