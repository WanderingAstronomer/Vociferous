"""
Stylesheet Registry.

Central management for loading and deduplicating widget stylesheets.
Each widget registers its styles here to avoid duplicates and enable theming.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication


class StylesheetRegistry:
    """
    Manages stylesheet loading and deduplication.

    Widgets register their stylesheets here. The registry ensures each
    stylesheet is only applied once and provides a central point for
    theme switching.
    """

    _instance: StylesheetRegistry | None = None
    _registered: set[str]
    _stylesheets: list[str]

    def __new__(cls) -> StylesheetRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._registered = set()
            cls._instance._stylesheets = []
        return cls._instance

    @classmethod
    def instance(cls) -> StylesheetRegistry:
        """Get the singleton instance."""
        return cls()

    def register(self, name: str, stylesheet: str) -> None:
        """
        Register a widget's stylesheet.

        Args:
            name: Unique identifier (e.g., 'collapsible_section')
            stylesheet: QSS string
        """
        if name not in self._registered:
            self._registered.add(name)
            self._stylesheets.append(stylesheet)

    def is_registered(self, name: str) -> bool:
        """Check if a stylesheet is already registered."""
        return name in self._registered

    def get_combined_stylesheet(self) -> str:
        """Get all registered stylesheets combined."""
        return "\n".join(self._stylesheets)

    def apply_to_app(self, app: QApplication) -> None:
        """Apply all registered stylesheets to the application."""
        app.setStyleSheet(self.get_combined_stylesheet())

    def clear(self) -> None:
        """Clear all registered stylesheets (for testing/theme switching)."""
        self._registered.clear()
        self._stylesheets.clear()
