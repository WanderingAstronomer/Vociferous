"""
Title bar components for Vociferous.

Provides custom title bars for main window and dialogs.
"""

from ui.components.title_bar.dialog_title_bar import DialogTitleBar
from ui.components.title_bar.title_bar import TitleBar
from ui.components.title_bar.title_bar_styles import get_title_bar_styles

__all__ = [
    "DialogTitleBar",
    "TitleBar",
    "get_title_bar_styles",
]
