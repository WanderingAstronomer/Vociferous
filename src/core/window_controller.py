"""WindowController — pywebview window management.

Platform-specific:
  Windows — DwmSetWindowAttribute(DWMWA_USE_IMMERSIVE_DARK_MODE) to
            force the native title bar to dark mode.
  Linux   — gtk-application-prefer-dark-theme set on GtkSettings to
            force the dark variant of whatever GTK theme is installed.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)


class WindowController:
    """Thin wrapper around the pywebview main window."""

    def __init__(self) -> None:
        self._main_window: Any = None  # webview.Window
        self._window_maximized: bool = False

    def set_window(self, window: Any) -> None:
        """Bind the pywebview window after creation."""
        self._main_window = window
        window.events.shown += self._on_shown

    def _on_shown(self) -> None:
        """Apply platform-specific title bar theming after the window is visible."""
        if sys.platform == "win32":
            try:
                form = getattr(self._main_window, "native", None)
                if form is None:
                    return
                from System import Action  # type: ignore[import-untyped]

                form.Invoke(Action(self._apply_dark_titlebar))
            except Exception:
                logger.warning("Failed to apply dark title bar", exc_info=True)
        elif sys.platform.startswith("linux"):
            self._apply_dark_titlebar_gtk()

    def _apply_dark_titlebar_gtk(self) -> None:
        """Request the dark theme variant from GTK (Linux only).

        Sets gtk-application-prefer-dark-theme on the default GtkSettings
        object, which covers only this process and forces the title bar to
        honour the dark variant of whatever GTK theme is installed.
        """
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # type: ignore[import-untyped]

            settings = Gtk.Settings.get_default()
            if settings is not None:
                settings.set_property("gtk-application-prefer-dark-theme", True)
                logger.info("GTK dark title bar applied")
        except Exception:
            logger.warning("Failed to apply GTK dark title bar", exc_info=True)

    def _apply_dark_titlebar(self) -> None:
        """Use DWM to force the native title bar to dark mode (Windows only).

        MUST be called on the WinForms UI thread (via Form.Invoke).
        """
        import ctypes

        form = self._main_window.native
        hwnd = form.Handle.ToInt32()

        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            20,
            ctypes.byref(value),
            ctypes.sizeof(value),
        )

        # Replace the default Python icon — pywebview's WinForms backend
        # hardcodes ExtractIconW(sys.executable) and ignores the icon param.
        self._apply_icon(form)

        logger.info("Dark title bar applied (HWND %#x)", hwnd)

    def _apply_icon(self, form: Any) -> None:
        """Load vociferous_icon.png and set it as the Form icon."""
        try:
            import ctypes

            from System.Drawing import Bitmap, Icon  # type: ignore[import-untyped]

            from src.core.resource_manager import ResourceManager

            icon_path = ResourceManager.get_icon_path("vociferous_icon")
            bitmap = Bitmap(icon_path)
            hicon = bitmap.GetHicon()
            form.Icon = Icon.FromHandle(hicon).Clone()
            ctypes.windll.user32.DestroyIcon(hicon.ToInt32())
            bitmap.Dispose()
            logger.info("Custom icon set from %s", icon_path)
        except Exception:
            logger.warning("Failed to set custom icon", exc_info=True)

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

    def show_open_dialog(self, file_types: tuple[str, ...] = ()) -> str | None:
        """Show a native open-file dialog and return the chosen path, or None if cancelled."""
        if self._main_window is None:
            return None
        try:
            import webview

            result = self._main_window.create_file_dialog(
                webview.OPEN_DIALOG,
                file_types=file_types,
            )
            if result and len(result) > 0:
                return str(result[0])
            return None
        except Exception:
            logger.exception("Native open dialog failed")
            return None
