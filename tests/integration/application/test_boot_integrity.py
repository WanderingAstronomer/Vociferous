"""
Tests for UI Integration and Boot-time consistency.
"""

import pytest

from src.ui.styles.unified_stylesheet import get_unified_stylesheet


class TestBootIntegrity:
    """Tests ensuring crucial boot-time resources are available."""

    def test_unified_stylesheet_export_exists(self):
        """
        Regression Test for Import Error.
        Main entry point relies on 'get_unified_stylesheet' being importable.
        """
        assert callable(get_unified_stylesheet)
        style = get_unified_stylesheet()
        assert isinstance(style, str)
        assert len(style) > 0
