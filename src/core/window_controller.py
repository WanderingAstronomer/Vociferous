"""
WindowController — pywebview window management for the frameless title bar.

Extracted from ApplicationCoordinator to keep window-specific logic
(minimize, maximize, close, native dialogs) in one place.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class WindowController:
    """Thin wrapper around the pywebview main window for frameless title-bar controls."""

    def __init__(self) -> None:
        self._main_window: Any = None  # webview.Window
        self._window_maximized: bool = False

    def set_window(self, window: Any) -> None:
        """Bind the pywebview window after creation."""
        self._main_window = window

    def minimize(self) -> None:
        """Minimize the main window."""
        if self._main_window is not None:
            self._main_window.minimize()

    def maximize(self) -> None:
        """Toggle maximize/restore on the main window."""
        if self._main_window is None:
            return
        if self._window_maximized:
            self._main_window.restore()
            self._window_maximized = False
        else:
            self._main_window.maximize()
            self._window_maximized = True

    @property
    def is_maximized(self) -> bool:
        """Return current maximize state tracked by window events."""
        return self._window_maximized

    def close(self) -> None:
        """Close the main window, triggering graceful shutdown."""
        if self._main_window is not None:
            self._main_window.destroy()

    def destroy_for_shutdown(self) -> None:
        """Destroy the window during shutdown. Swallows errors if already closing."""
        try:
            if self._main_window is not None:
                self._main_window.destroy()
        except Exception:
            logger.debug("Window destroy skipped during shutdown", exc_info=True)

    def on_maximized(self) -> None:
        """Event callback: window was maximized."""
        self._window_maximized = True

    def on_restored(self) -> None:
        """Event callback: window was restored from maximized."""
        self._window_maximized = False

    def show_save_dialog(self, suggested_name: str) -> str | None:
        """Show a native save-file dialog and return the chosen path, or None if cancelled."""
        if self._main_window is None:
            return None
        try:
            import webview

            result = self._main_window.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=suggested_name,
            )
            if result and len(result) > 0:
                return str(result[0])
            return None
        except Exception:
            logger.exception("Native save dialog failed")
            return None
