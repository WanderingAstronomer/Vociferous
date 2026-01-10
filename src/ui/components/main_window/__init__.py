"""
Main Window Component Package.

Provides the primary application window integrating sidebar, workspace, and metrics.

Components:
    MainWindow: Primary application window
    ChevronButton: Sidebar toggle button
    SidebarAnimator: Animation controller for sidebar
    MenuBuilder: Menu bar factory
"""

from ui.components.main_window.chevron_button import ChevronButton
from ui.components.main_window.main_window import MainWindow
from ui.components.main_window.menu_builder import MenuBuilder
from ui.components.main_window.sidebar_animator import SidebarAnimator

__all__ = [
    "ChevronButton",
    "MainWindow",
    "MenuBuilder",
    "SidebarAnimator",
]
