"""
Styles Package.

Provides centralized style management and theming support.

IMPORTANT: All styles are consolidated in unified_stylesheet.py and applied
ONCE at application startup. Individual widgets should NOT call setStyleSheet().
"""

# NOTE: No eager imports! Style modules import src.ui.constants which may trigger Qt.
# Import functions directly from their modules when needed:
#   from src.ui.styles.unified_stylesheet import generate_unified_stylesheet
# etc.
