"""
Styled buttons for Vociferous dialogs.

Uses central stylesheet via styleClass attribute selector pattern.
"""

from enum import Enum

from PyQt6.QtWidgets import QPushButton, QWidget


class ButtonStyle(Enum):
    """Button style variants."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    DESTRUCTIVE = "destructive"


class StyledButton(QPushButton):
    """Common button with Primary/Secondary/Destructive variations via styleClass attribute."""

    def __init__(
        self,
        text: str,
        style: ButtonStyle = ButtonStyle.SECONDARY,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.style_type = style
        self.setMinimumHeight(44)
        self.setMinimumWidth(100)

        # Styles are applied via unified_stylesheet using styleClass attribute
        self._apply_style()

    def _apply_style(self) -> None:
        """Apply style via styleClass attribute for stylesheet matching."""
        match self.style_type:
            case ButtonStyle.PRIMARY:
                self.setProperty("styleClass", "primaryButton")
            case ButtonStyle.DESTRUCTIVE:
                self.setProperty("styleClass", "destructiveButton")
            case ButtonStyle.SECONDARY:
                self.setProperty("styleClass", "secondaryButton")
