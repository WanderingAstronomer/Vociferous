"""
Styled buttons for Vociferous dialogs.

Uses central stylesheet via object names instead of inline styles.
"""

from enum import Enum

from PyQt6.QtWidgets import QPushButton, QWidget


class ButtonStyle(Enum):
    """Button style variants."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    DESTRUCTIVE = "destructive"


class StyledButton(QPushButton):
    """Common button with Primary/Secondary/Destructive variations via object names."""

    def __init__(
        self,
        text: str,
        style: ButtonStyle = ButtonStyle.SECONDARY,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.style_type = style
        self.setFixedHeight(36)
        self.setMinimumWidth(80)

        # Styles are applied at app level via generate_unified_stylesheet()

        self._apply_style()

    def _apply_style(self) -> None:
        """Apply style via object name for stylesheet matching."""
        match self.style_type:
            case ButtonStyle.PRIMARY:
                self.setObjectName("styledPrimary")
            case ButtonStyle.DESTRUCTIVE:
                self.setObjectName("styledDestructive")
            case ButtonStyle.SECONDARY:
                self.setObjectName("styledSecondary")
