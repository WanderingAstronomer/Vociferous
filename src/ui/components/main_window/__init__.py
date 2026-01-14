"""
Main Window Component Package.

Provides the primary application window integrating icon rail, workspace, and metrics.

Components:
    MainWindow: Primary application window
    MenuBuilder: Menu bar factory
"""

from ui.components.main_window.main_window import MainWindow
from ui.components.main_window.menu_builder import MenuBuilder

__all__ = [
    "MainWindow",
    "MenuBuilder",
]
