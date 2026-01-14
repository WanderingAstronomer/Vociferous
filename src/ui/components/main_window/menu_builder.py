"""
MenuBuilder - Creates menu bar with all menus for main window.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import QMenuBar

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow


class MenuBuilder:
    """
    Builds and manages the main window menu bar.

    Creates File, History, View, Settings, and Help menus.
    """

    def __init__(self, menu_bar: QMenuBar, window: QMainWindow) -> None:
        self._menu_bar = menu_bar
        self._window = window

        # Store actions for external access
        self.export_action: QAction | None = None
        self.settings_action: QAction | None = None
        self.metrics_action: QAction | None = None
        self.focus_history_action: QAction | None = None

    def build(
        self,
        *,
        on_exit: Callable[[], None],
        on_restart: Callable[[], None],
        on_export: Callable[[], None],
        on_clear: Callable[[], None],
        on_toggle_metrics: Callable[[bool], None],
        on_focus_history: Callable[[], None],
        on_about: Callable[[], None],
        on_metrics_explanation: Callable[[], None],
    ) -> None:
        """Build all menus with action handlers."""
        self._create_file_menu(on_exit, on_restart)
        self._create_history_menu(on_export, on_clear)
        self._create_view_menu(
            on_toggle_metrics, on_focus_history
        )
        self._create_settings_menu()
        self._create_help_menu(on_about, on_metrics_explanation)

    def _create_file_menu(
        self, on_exit: Callable[[], None], on_restart: Callable[[], None]
    ) -> None:
        """Create File menu."""
        file_menu = self._menu_bar.addMenu("&File")

        restart_action = QAction("Restart", self._window)
        restart_action.setShortcut(QKeySequence("Ctrl+Shift+R"))
        restart_action.triggered.connect(on_restart)
        file_menu.addAction(restart_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self._window)
        exit_action.triggered.connect(on_exit)
        file_menu.addAction(exit_action)

    def _create_history_menu(
        self,
        on_export: Callable[[], None],
        on_clear: Callable[[], None],
    ) -> None:
        """Create History menu."""
        history_menu = self._menu_bar.addMenu("&History")

        self.export_action = QAction("Export...", self._window)
        self.export_action.setShortcut(QKeySequence("Ctrl+E"))
        self.export_action.triggered.connect(on_export)
        history_menu.addAction(self.export_action)

        clear_action = QAction("Clear All...", self._window)
        clear_action.triggered.connect(on_clear)
        history_menu.addAction(clear_action)

    def _create_view_menu(
        self,
        on_toggle_metrics: Callable[[bool], None],
        on_focus_history: Callable[[], None],
    ) -> None:
        """Create View menu."""
        view_menu = self._menu_bar.addMenu("&View")
        self.focus_history_action = QAction("Project History", self._window)
        self.focus_history_action.setShortcut(QKeySequence("Ctrl+H"))
        self.focus_history_action.triggered.connect(on_focus_history)
        view_menu.addAction(self.focus_history_action)

        view_menu.addSeparator()

        self.metrics_action = QAction("Metrics Strip", self._window)
        self.metrics_action.setCheckable(True)
        self.metrics_action.setChecked(True)
        self.metrics_action.triggered.connect(on_toggle_metrics)
        view_menu.addAction(self.metrics_action)

    def _create_settings_menu(self) -> None:
        """Create Settings menu."""
        settings_menu = self._menu_bar.addMenu("&Settings")

        self.settings_action = QAction("Preferences...", self._window)
        self.settings_action.setEnabled(True)
        settings_menu.addAction(self.settings_action)

    def _create_help_menu(
        self, on_about: Callable[[], None], on_metrics_explanation: Callable[[], None]
    ) -> None:
        """Create Help menu."""
        help_menu = self._menu_bar.addMenu("&Help")

        metrics_explanation_action = QAction("Metrics Calculations...", self._window)
        metrics_explanation_action.triggered.connect(on_metrics_explanation)
        help_menu.addAction(metrics_explanation_action)

        help_menu.addSeparator()

        about_action = QAction("About Vociferous", self._window)
        about_action.triggered.connect(on_about)
        help_menu.addAction(about_action)
