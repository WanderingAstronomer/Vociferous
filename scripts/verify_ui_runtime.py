#!/usr/bin/env python3
import sys
import os
import logging
from PyQt6.QtWidgets import QApplication, QPushButton
from PyQt6.QtGui import QPalette, QColor, QFontMetrics

# Setup path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
src_path = os.path.join(project_root, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Use imports matching the application's internal structure (assuming src in path)
from core.application_coordinator import ApplicationCoordinator  # noqa: E402
from ui.components.main_window.icon_rail import IconRail, RailButton  # noqa: E402
from ui.components.main_window.action_dock import ActionDock  # noqa: E402
from ui.components.title_bar import TitleBar  # noqa: E402
import ui.constants.colors as c  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ui_validator")

# --- APPROVED FALLBACKS ---
APPROVED_FONTS = ["Inter", "Sans Serif", "Ubuntu", "DejaVu Sans", "Segoe UI", "Arial"]
SHELL_BG_TOKEN = QColor("#1e1e1e").name()  # GRAY_9
CONTENT_BG_TOKEN = QColor("#2a2a2a").name()  # GRAY_8


def verify_ui():
    # Don't require X server if possible, but for UI tests we likely need one.
    app = QApplication(sys.argv)

    # 1. Config Font (mimic main.py)
    font = app.font()
    font.setPointSize(18)
    app.setFont(font)

    # 2. Coordinator (sets stylesheet)
    coordinator = ApplicationCoordinator(app)
    coordinator.start()

    # Allow event loop to process for a moment to ensure polish
    app.processEvents()

    errors = []

    # Check Stylesheet
    stylesheet = app.styleSheet()
    if not stylesheet:
        errors.append("CRITICAL: QApplication.styleSheet() is empty.")
    else:
        logger.info(f"Stylesheet length: {len(stylesheet)} chars")
        if "QMainWindow" not in stylesheet:
            errors.append("Stylesheet might be missing QMainWindow selectors.")

        # INVARIANT: Primary Button Focus Outline MUST use BLUE_4
        if f"outline: 2px solid {c.BLUE_4}" not in stylesheet:
            errors.append(
                f"Stylesheet missing primaryButton focus invariant: outline: 2px solid {c.BLUE_4}"
            )
        else:
            logger.info("Verified primaryButton focus invariant in QSS.")

    # Locate Sentinel Widgets
    window = coordinator.main_window
    if window is None:
        errors.append("CRITICAL: MainWindow not created.")
        return errors

    # --- FONT ASSERTION ---
    app_font = app.font()
    family = app_font.family()
    if family not in APPROVED_FONTS:
        errors.append(
            f"App font family '{family}' not in approved list {APPROVED_FONTS}"
        )
    else:
        logger.info(f"Verified App Font: {family} ({app_font.pointSize()}pt)")

    # --- COLOR ASSERTIONS (SENTINELS) ---

    # 1. MainWindow Foreground (Token GRAY_0)
    win_fg = window.palette().color(QPalette.ColorRole.WindowText).name()
    if win_fg != QColor("#ffffff").name():
        errors.append(f"MainWindow foreground {win_fg} does not match GRAY_0 (#ffffff)")
    else:
        logger.info(f"Verified MainWindow foreground: {win_fg}")

    # 2. IconRail Background (Token SHELL_BACKGROUND / GRAY_9)
    icon_rails = window.findChildren(IconRail)
    if not icon_rails:
        errors.append("IconRail not found.")
    else:
        rail = icon_rails[0]
        rail_bg = rail.palette().color(QPalette.ColorRole.Window).name()
        if rail_bg != SHELL_BG_TOKEN:
            errors.append(
                f"IconRail background {rail_bg} does not match SHELL_BG {SHELL_BG_TOKEN}"
            )
        else:
            logger.info(f"Verified IconRail background: {rail_bg}")

    # 3. TitleBar Background (Token SHELL_BACKGROUND / GRAY_9)
    title_bars = window.findChildren(TitleBar)
    if not title_bars:
        errors.append("TitleBar not found.")
    else:
        tb = title_bars[0]
        tb_bg = tb.palette().color(QPalette.ColorRole.Window).name()
        if tb_bg != SHELL_BG_TOKEN:
            errors.append(
                f"TitleBar background {tb_bg} does not match SHELL_BG {SHELL_BG_TOKEN}"
            )
        else:
            logger.info(f"Verified TitleBar background: {tb_bg}")

    # 4. ActionDock Button (Token GRAY_0)
    # 3. ActionDock Button (Token GRAY_0)
    action_docks = window.findChildren(ActionDock)
    if action_docks:
        dock = action_docks[0]
        btn = dock.findChild(QPushButton)
        if btn:
            btn.style().polish(btn)
            btn_fg = btn.palette().color(QPalette.ColorRole.ButtonText).name()
            logger.info(
                f"ActionDock button foreground roles: ButtonText={btn_fg}, WindowText={btn.palette().color(QPalette.ColorRole.WindowText).name()}"
            )

            target = QColor("#ffffff").name()
            # If QSS didn't update palette, we might have issues in headless
            # But we try to be thorough.
            if (
                btn_fg != target
                and btn.palette().color(QPalette.ColorRole.WindowText).name() != target
            ):
                errors.append(
                    f"ActionDock button foreground does not match GRAY_0 ({target})"
                )

    # 4. IconRail Button Foreground (Token GRAY_2 or GRAY_0 depending on state)
    if icon_rails:
        rail = icon_rails[0]
        btn = rail.findChild(RailButton)
        if btn:
            btn.style().polish(btn)
            rail_btn_fg = btn.palette().color(QPalette.ColorRole.ButtonText).name()
            logger.info(f"IconRail button foreground: {rail_btn_fg}")
            # GRAY_2 = #d4d4d4
            # We don't necessarily error here yet, just gathering info for now.

    # --- TRUNCATION & ICON CHECKS (SENTINELS) ---
    if icon_rails:
        rail = icon_rails[0]
        buttons = rail.findChildren(RailButton)
        for btn in buttons:
            # Check Icon
            if btn.icon().isNull():
                errors.append(f"IconRail button {btn.text()} has NULL icon.")

            # Check Truncation (using 13px font from QSS, but we check computed font)
            metrics = QFontMetrics(btn.font())
            available_w = btn.width() - 32  # 120 (rail) - 32 (margins) = 88
            text = btn.text()
            # If text is elided, it's a failure
            if metrics.horizontalAdvance(text) > available_w:
                errors.append(
                    f"IconRail button text '{text}' is truncated (Needs > {metrics.horizontalAdvance(text)}px, has {available_w}px)"
                )
            else:
                logger.info(f"Verified no truncation for button: {text}")

    coordinator.cleanup()

    return errors


if __name__ == "__main__":
    try:
        errors = verify_ui()
        if errors:
            print("\nFAILED: UI Verification Errors Found:")
            for e in errors:
                print(f"- {e}")
            sys.exit(1)
        else:
            print("\nSUCCESS: UI Runtime Styling Verified.")
            sys.exit(0)
    except Exception as e:
        print(f"CRITICAL EXCEPTION: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
