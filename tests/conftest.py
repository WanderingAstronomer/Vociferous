"""
Pytest configuration and fixtures for Vociferous tests.

Test Tiers:
-----------
Tests are classified into tiers for selective execution:

1. UI-Independent (Tier 1):
   - Pure logic, no display required
   - Can run in CI without virtual display
   - Includes config, input logic, service backends (mocked), and utilities.

2. UI-Dependent (Tier 2):
   - Require Qt widget instantiation
   - Need QApplication or virtual display (xvfb)
   - May fail with SIGABRT in headless environments
   - includes component tests, view scaffolding, style enforcement, and geometry.

Run Tier 1 only: pytest -m "not ui_dependent"
Run Tier 2 only: pytest -m "ui_dependent"
"""

import os
import sys
from contextlib import suppress

from pathlib import Path

import pytest

# Add src to path
# Use resolve() for determinism across working directories
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Set Qt to use offscreen platform for headless testing
# This prevents SIGABRT when no display server is available
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp_session():
    """Session-scoped QApplication for ConfigManager and other Qt objects."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture(scope="session", autouse=True)
def init_config(qapp_session):
    """Initialize ConfigManager once for all tests."""
    from utils import ConfigManager

    ConfigManager.initialize()
    yield ConfigManager


@pytest.fixture
def config_manager(init_config):
    """Provide ConfigManager instance."""
    return init_config

@pytest.fixture
def key_listener(qapp_session):
    """Create and yield a KeyListener, stopping it after test."""
    from input_handler import KeyListener

    kl = KeyListener()
    yield kl
    with suppress(Exception):
        kl.stop()
        # Drain events to prevent late signal delivery
        qapp_session.processEvents()

