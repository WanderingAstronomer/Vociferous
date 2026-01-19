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

import logging
import os
import sys
import tempfile
from contextlib import suppress

# FORCE Qt to use offscreen platform for headless testing
# This prevents SIGABRT and UI popups
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from pathlib import Path

import pytest

# Add src to path
# Use resolve() for determinism across working directories
# sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def _get_vociferous_lock_path() -> str:
    """Match Vociferous' lock path logic (see `src/main.py`)."""
    override = os.environ.get("VOCIFEROUS_LOCK_PATH")
    if override:
        return override
    return os.path.join(tempfile.gettempdir(), "vociferous.lock")


def pytest_sessionstart(session) -> None:
    """Abort the entire test run if Vociferous is already running.

    This prevents flakey UI tests and avoids interference with the live app.
    Set `VOCIFEROUS_TEST_IGNORE_RUNNING=1` to bypass.
    """
    if os.environ.get("VOCIFEROUS_TEST_IGNORE_RUNNING") == "1":
        return

    # Import lazily to avoid Qt import work if not needed.
    from PyQt6.QtCore import QLockFile

    lock_path = _get_vociferous_lock_path()
    lock = QLockFile(lock_path)
    lock.setStaleLockTime(10_000)

    if lock.tryLock():
        lock.unlock()
        return

    # Attempt to recover stale locks (crash recovery) and continue if recovered.
    if lock.removeStaleLockFile() and lock.tryLock():
        lock.unlock()
        return

    msg = (
        f"Vociferous appears to be running (lock held at {lock_path}). "
        "Aborting test run to avoid interference. "
        "Close Vociferous or set VOCIFEROUS_TEST_IGNORE_RUNNING=1 to override."
    )
    logging.getLogger(__name__).warning(msg)
    pytest.exit(msg, returncode=2)


@pytest.fixture(scope="session")
def qapp_session():
    """Session-scoped QApplication for ConfigManager and other Qt objects."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture(scope="function", autouse=True)
def init_config(qapp_session):
    """Ensure ConfigManager is initialized and reset for all tests."""
    from src.core.config_manager import ConfigManager

    ConfigManager.reset_for_tests()
    ConfigManager.initialize()
    yield ConfigManager
    ConfigManager.reset_for_tests()


@pytest.fixture(scope="session", autouse=True)
def check_threads(qapp_session):
    """Diagnose leaked QThreads at the end of the session."""
    yield
    from PyQt6.QtCore import QThread

    app = qapp_session
    print("\n--- Thread Diagnostics ---")

    threads = app.findChildren(QThread)

    import gc

    for obj in gc.get_objects():
        if isinstance(obj, QThread):
            threads.append(obj)

    unique_threads = list({id(t): t for t in threads}.values())

    for t in unique_threads:
        if t.isRunning():
            print(f"THREAD LEAK: {t} (isRunning=True)")
            parent = t.parent()
            if parent:
                print(f"  Parent: {parent} ({parent.objectName()})")
            else:
                print("  Parent: None")
            print(f"  ObjectName: {t.objectName()}")


@pytest.fixture
def config_manager(init_config):
    """Provide ConfigManager instance."""
    return init_config


@pytest.fixture
def key_listener(qapp_session):
    """Create and yield a KeyListener, stopping it after test."""
    from src.input_handler import KeyListener

    kl = KeyListener()
    yield kl
    with suppress(Exception):
        kl.stop()
        # Drain events to prevent late signal delivery
        qapp_session.processEvents()


@pytest.fixture(autouse=True)
def reset_signal_bridge():
    """Reset the DatabaseSignalBridge singleton between tests to ensure isolation."""
    from src.database.signal_bridge import DatabaseSignalBridge

    # Reset before test just in case
    DatabaseSignalBridge.reset()
    yield
    # Reset after test to clean up
    DatabaseSignalBridge.reset()
