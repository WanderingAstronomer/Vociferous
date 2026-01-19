"""
Vociferous UI Package.

A modular, atomic UI library for the Vociferous speech-to-text application.

Structure:
    constants/     Domain-specific constants (spacing, colors, typography, etc.)
    styles/        Stylesheet infrastructure (registry, theme)
    widgets/       Reusable UI widgets with co-located styles
    models/        Data models and proxies
    utils/         UI utility functions
    components/    High-level composed components

Usage:
    from src.ui import constants
    from src.ui.components.main_window import MainWindow
    from src.ui.widgets.styled_button import StyledButton
    from src.ui.styles import generate_unified_stylesheet
"""

# NOTE: No eager imports! Many modules import Qt at module level.
# Import subpackages explicitly when needed.

__version__ = "2.0.0-beta.2"
