#!/usr/bin/env python3
"""
UI Smoke Test Script.

Minimally boots the UI shell to verify import integrity,
layout composition, and shutdown lifecycle.
"""

import sys
import os
from unittest.mock import MagicMock

# Ensure src and project root are in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from PyQt6.QtWidgets import QApplication
from ui.components.main_window import MainWindow


def main():
    print("Initializing QApplication...")
    app = QApplication(sys.argv)

    # Mock dependencies
    history_manager = MagicMock()
    # Mock return values to prevent crashes if consumed
    history_manager.get_recent_projects.return_value = []

    key_listener = MagicMock()
    command_bus = MagicMock()

    # Mock ConfigManager
    from core.config_manager import ConfigManager

    ConfigManager._config = {
        "refinement": {"enabled": False},
        "slm": {"default_model": "test"},
        "appearance": {"theme": "dark"},
    }
    ConfigManager._initialized = True

    print("Initializing MainWindow...")
    try:
        window = MainWindow(
            history_manager=history_manager,
            key_listener=key_listener,
            command_bus=command_bus,
        )
        window.show()
        print("MainWindow shown.")

        # Process some events
        app.processEvents()

        print("Closing MainWindow...")
        window.close()

        print("Smoke test passed.")
        return 0

    except Exception as e:
        print(f"Smoke test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
