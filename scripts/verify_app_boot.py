#!/usr/bin/env python3
"""
Verify that the application can boot far enough to create the main window
and apply styles, then exit cleanly. Safe for CI/offscreen environments.
"""

import sys
import os
from pathlib import Path

# Ensure project root and src are in the python path
PROJECT_ROOT = Path(__file__).parents[1].resolve()
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Set offscreen platform for headless environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"
# Ensure we don't try to use a real tray if D-Bus is missing
os.environ["QT_LOGGING_RULES"] = "qt.qpa.wayland=false"

import logging  # noqa: E402

# Minimal logging for verification
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
# Suppress noisy modules
logging.getLogger("core_runtime.client").setLevel(logging.WARNING)
logging.getLogger("input_handler").setLevel(logging.WARNING)

from PyQt6.QtWidgets import QApplication  # noqa: E402
from PyQt6.QtCore import QTimer  # noqa: E402
from src.core.application_coordinator import ApplicationCoordinator  # noqa: E402


def main():
    print("=== App Boot Verification ===")

    # 1. Initialize QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("Vociferous-Boot-Verify")

    # 2. Instantiate Coordinator
    coordinator = ApplicationCoordinator(app)

    result = {"success": False, "error": None}

    def perform_checks():
        print("Starting verification checks...")
        try:
            # Check MainWindow creation
            if coordinator.main_window is None:
                result["error"] = "MainWindow was not created"
                return

            print(f"[OK] Main Window created: {coordinator.main_window.objectName()}")

            # Check Stylesheet application
            sheet = app.styleSheet()
            if not sheet or len(sheet) < 1000:
                result["error"] = (
                    f"Stylesheet missing or suspiciously small ({len(sheet) if sheet else 0} bytes)"
                )
                return

            print(f"[OK] Unified Stylesheet applied ({len(sheet)} bytes)")

            # Check Tray initialization (might be None if no D-Bus, but shouldn't crash)
            if coordinator.tray_manager:
                print("[OK] Tray Manager initialized")
            else:
                print("[INFO] Tray Manager skipped (likely no D-Bus/headless)")

            result["success"] = True

        except Exception as e:
            result["error"] = str(e)
        finally:
            print("Shutting down...")
            coordinator.cleanup()
            app.quit()

    # 3. Attempt Boot
    try:
        # We use a short timer to run checks after start() returns
        # start() is synchronous for most setup but some parts are threaded
        QTimer.singleShot(500, perform_checks)

        print("Booting coordinator...")
        coordinator.start()

        # Run event loop to allow signals and timers to process
        app.exec()

    except Exception as e:
        print(f"[CRITICAL] Boot process crashed: {e}")
        sys.exit(1)

    # 4. Final Verdict
    if result["success"]:
        print("\n[PASS] Application boot verification successful.")
        sys.exit(0)
    else:
        print(f"\n[FAIL] Application boot verification failed: {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
