import logging
import os
import sys
from typing import Callable

from src.core.resource_manager import ResourceManager

from PyQt6.QtCore import QObject
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

logger = logging.getLogger(__name__)


class SystemTrayManager(QObject):
    """
    Manages the System Tray Icon and its context menu.
    """

    def __init__(
        self,
        app: QApplication,
        main_window: QWidget,
        on_exit: Callable[[], None],
    ):
        super().__init__()
        self.app = app
        self.main_window = main_window
        self.on_exit = on_exit

        self.tray_icon: QSystemTrayIcon | None = None
        self.status_action: QAction | None = None
        self.show_hide_action: QAction | None = None
        self.settings_action: QAction | None = None

        # Explicit visibility state tracking to handle unreliable isVisible()
        # on some window managers (particularly Wayland compositors)
        self._window_is_hidden = False

        self._create_tray_icon()

    def _tray_available(self) -> bool:
        """Return True if a functional system tray is available."""
        # Check global error state from main.py if needed,
        # but for now we check environment.
        if sys.platform.startswith("linux"):
            if not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
                logger.warning("D-Bus session bus missing; skipping tray icon.")
                return False
        return True

    @staticmethod
    def build_icon(app: QApplication) -> QIcon:
        """Return a non-empty icon for the tray using bundled assets with fallbacks."""
        icon_path = ResourceManager.get_icon_path("system_tray_icon")

        icon = QIcon(icon_path) if icon_path else QIcon()

        if icon.isNull():
            icon = QIcon.fromTheme("microphone-sensitivity-high")

        if icon.isNull():
            style = app.style()
            if style:
                icon = style.standardIcon(style.StandardPixmap.SP_MediaVolume)

        return icon

    def _create_tray_icon(self) -> None:
        """Create system tray icon with context menu."""
        if not self._tray_available():
            self.tray_icon = None
            return

        try:
            icon = self.build_icon(self.app)
            self.tray_icon = QSystemTrayIcon(icon, self.app)

            tray_menu = QMenu()

            # Status indicator (non-clickable)
            status_action = QAction("Vociferous - Ready", self.app)
            status_action.setEnabled(False)
            tray_menu.addAction(status_action)
            self.status_action = status_action

            tray_menu.addSeparator()

            show_hide_action = QAction("Show/Hide Window", self.app)
            show_hide_action.triggered.connect(self.toggle_main_window)
            tray_menu.addAction(show_hide_action)
            self.show_hide_action = show_hide_action

            tray_menu.addSeparator()

            # Exit action
            exit_action = QAction("Exit", self.app)
            exit_action.triggered.connect(self.on_exit)
            tray_menu.addAction(exit_action)

            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.activated.connect(self.on_tray_activated)
            self.tray_icon.show()

            # Note: _TRAY_DBUS_ERROR_SEEN logic from main.py is global state logic
            # We might need to handle passing that state if really needed,
            # or rely on log observation. For now, we assume clean slate.

        except Exception as e:
            logger.warning(f"System tray initialization failed (non-fatal): {e}")
            self.tray_icon = None

    def toggle_main_window(self) -> None:
        """
        Toggle window between hidden and visible.

        Uses explicit state tracking instead of isVisible() to handle
        unreliable visibility reporting on some window managers (Wayland).
        """
        if self._window_is_hidden:
            self.main_window.show()
            self.main_window.activateWindow()
            self.main_window.raise_()
            self._window_is_hidden = False
        else:
            self.main_window.hide()
            self._window_is_hidden = True

    def on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon clicks."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_main_window()

    def update_status(self, is_recording: bool, is_transcribing: bool) -> None:
        """Update tray status action text."""
        if not self.tray_icon:
            return

        if is_recording:
            status = "Recording..."
        elif is_transcribing:
            status = "Transcribing..."
        else:
            status = "Ready"

        if self.status_action:
            self.status_action.setText(f"Vociferous - {status}")

        # Note: changing icon dynamically might be flashy, keeping static icon usually better
        # unless providing strong visual feedback.
