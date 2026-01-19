"""Targeted regression test for ActionDock startup layout.

This test exists because ActionDock used to render off-screen on initial startup
and would "fix itself" only after navigating away and back.

It also saves screenshots to `.pytest_cache/vociferous_screenshots/` to help
visually confirm the layout when debugging UI changes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from PyQt6.QtCore import QPoint

from src.ui.components.main_window.main_window import MainWindow
from src.ui.constants.view_ids import VIEW_HISTORY, VIEW_TRANSCRIBE
from src.ui.contracts.capabilities import ActionId


pytestmark = pytest.mark.ui_dependent


def _save_screenshot(window: MainWindow, name: str) -> None:
    out_dir = Path(".pytest_cache") / "vociferous_screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.png"
    window.grab().save(str(path))


def test_action_dock_is_onscreen_at_startup(qtbot):
    window = MainWindow(history_manager=None, key_listener=None)
    qtbot.addWidget(window)

    window.show()

    # Wait for deferred default view activation.
    qtbot.waitUntil(
        lambda: window.view_host.get_current_view_id() == VIEW_TRANSCRIBE, timeout=2000
    )
    qtbot.wait(50)

    _save_screenshot(window, "startup_transcribe")

    # Ensure Start Recording is visible and fully inside the ActionDock.
    start_btn = window.action_dock.get_button(ActionId.START_RECORDING)
    assert start_btn is not None

    qtbot.waitUntil(lambda: start_btn.isVisible(), timeout=2000)

    btn_bottom_global = start_btn.mapToGlobal(QPoint(0, start_btn.height() - 1)).y()
    dock_bottom_global = window.action_dock.mapToGlobal(
        QPoint(0, window.action_dock.height() - 1)
    ).y()
    window_bottom_global = window.mapToGlobal(QPoint(0, window.height() - 1)).y()

    assert btn_bottom_global <= dock_bottom_global
    assert dock_bottom_global <= window_bottom_global

    # Reproduce the user workflow (navigate away and back) and ensure geometry remains stable.
    window.view_host.switch_to_view(VIEW_HISTORY)
    qtbot.waitUntil(
        lambda: window.view_host.get_current_view_id() == VIEW_HISTORY, timeout=2000
    )
    qtbot.wait(50)

    _save_screenshot(window, "after_switch_to_history")

    window.view_host.switch_to_view(VIEW_TRANSCRIBE)
    qtbot.waitUntil(
        lambda: window.view_host.get_current_view_id() == VIEW_TRANSCRIBE, timeout=2000
    )
    qtbot.wait(50)

    _save_screenshot(window, "after_switch_back_to_transcribe")

    # If it was ever going to shove the dock offscreen, this tends to flush it out.
    dock_bottom_global_2 = window.action_dock.mapToGlobal(
        QPoint(0, window.action_dock.height() - 1)
    ).y()
    window_bottom_global_2 = window.mapToGlobal(QPoint(0, window.height() - 1)).y()
    assert dock_bottom_global_2 <= window_bottom_global_2
