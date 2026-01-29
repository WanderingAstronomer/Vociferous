"""
Reusable styled dialog components for Vociferous.

Provides ConfirmationDialog, InputDialog, and MessageDialog that match
the application's styling (custom title bar, specific colors, bordered areas).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.ui.components.title_bar.dialog_title_bar import DialogTitleBar
from src.ui.constants import MAJOR_GAP, MINOR_GAP
from src.ui.widgets.styled_button import ButtonStyle, StyledButton


class StyledDialog(QDialog):
    """Base class for styled dialogs with custom title bar."""

    def __init__(
        self, parent: QWidget | None = None, title: str = "Vociferous"
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setModal(True)

        # Styles are applied at app level via generate_unified_stylesheet()

        self._setup_base_ui(title)

    def _finalize_size(self, min_width: int = 400) -> None:
        """Auto-size the dialog to fit its content.

        Sets a minimum width and lets Qt compute the natural height.
        """
        self.setMinimumWidth(min_width)
        self.adjustSize()

    def _setup_base_ui(self, title: str) -> None:
        """Set up the base dialog structure."""
        # Main layout (no margins because title bar is edge-to-edge)
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # Structural Frame Wrapper (The Dialog Frame)
        self._dialog_frame = QFrame()
        self._dialog_frame.setObjectName("dialogFrame")
        self._main_layout.addWidget(self._dialog_frame)

        # Frame layout (contains title bar + content)
        self._frame_layout = QVBoxLayout(self._dialog_frame)
        self._frame_layout.setContentsMargins(0, 0, 0, 0)
        self._frame_layout.setSpacing(0)

        # Custom title bar (draggable)
        self.title_bar = DialogTitleBar(title, self)
        self.title_bar.close_requested.connect(self.reject)
        self._frame_layout.addWidget(self.title_bar)

        # Background container
        self._container = QWidget()
        self._container.setObjectName("dialogContainer")
        self._frame_layout.addWidget(self._container)

        # Container layout
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(0)

        # Content placeholder
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(
            MAJOR_GAP, MAJOR_GAP, MAJOR_GAP, MAJOR_GAP
        )
        self.content_layout.setSpacing(MINOR_GAP)
        self._container_layout.addWidget(self.content_area)

        # Button row placeholder
        self.button_container = QWidget()
        self.button_container.setObjectName("dialogButtonContainer")
        self.button_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.button_layout = QHBoxLayout(self.button_container)
        # Taller margins around buttons for better visual breathing room
        self.button_layout.setContentsMargins(MAJOR_GAP, 16, MAJOR_GAP, 16)
        self.button_layout.setSpacing(MINOR_GAP)
        self._container_layout.addWidget(self.button_container)

        # Keyboard shortcuts
        self._setup_shortcuts()

    def _setup_shortcuts(self) -> None:
        """Set up keyboard shortcuts for dialog actions."""
        # Escape to cancel/close
        escape_shortcut = QShortcut(QKeySequence.StandardKey.Cancel, self)
        escape_shortcut.activated.connect(self.reject)

    def add_button(
        self, text: str, role: str = "secondary", callback=None
    ) -> StyledButton:
        """Add a button to the bottom row."""
        style = ButtonStyle.SECONDARY
        if role == "primary":
            style = ButtonStyle.PRIMARY
        elif role == "destructive":
            style = ButtonStyle.DESTRUCTIVE

        btn = StyledButton(text, style)

        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        if callback:
            btn.clicked.connect(callback)
        else:
            if text.lower() in ("cancel", "no"):
                btn.clicked.connect(self.reject)
            elif text.lower() in ("ok", "yes", "confirm"):
                btn.clicked.connect(self.accept)

        self.button_layout.addWidget(btn)
        return btn


class ConfirmationDialog(StyledDialog):
    """
    Drop-in replacement for QMessageBox.question/warning.
    Standard 'Yes/No' or 'OK/Cancel' structure.
    """

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        message: str,
        confirm_text: str = "Yes",
        cancel_text: str = "No",
        is_destructive: bool = False,
    ) -> None:
        super().__init__(parent, title)

        lbl = QLabel(message)
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        lbl.setObjectName("dialogLabel")
        self.content_layout.addWidget(lbl)

        self.button_layout.addStretch()

        self.cancel_btn = self.add_button(cancel_text, "secondary", self.reject)

        role = "destructive" if is_destructive else "primary"
        self.confirm_btn = self.add_button(confirm_text, role, self.accept)
        self.confirm_btn.setFocus()

        self._finalize_size(min_width=420)


class InputDialog(StyledDialog):
    """
    Drop-in replacement for QInputDialog.getText.
    """

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        label: str,
        text: str = "",
    ) -> None:
        super().__init__(parent, title)

        lbl = QLabel(label)
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        lbl.setObjectName("dialogLabel")
        self.content_layout.addWidget(lbl)

        self.input_field = QLineEdit(text)
        self.input_field.setObjectName("dialogInput")
        self.content_layout.addWidget(self.input_field)
        self.input_field.selectAll()

        self.button_layout.addStretch()
        self.add_button("Cancel", "secondary", self.reject)
        self.ok_btn = self.add_button("OK", "primary", self.accept)

        self._finalize_size(min_width=450)

    def get_text(self) -> str:
        """Return the entered text."""
        return self.input_field.text()


class MessageDialog(StyledDialog):
    """
    Drop-in replacement for QMessageBox.information/warning (single button).
    """

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        message: str,
        button_text: str = "OK",
    ) -> None:
        super().__init__(parent, title)

        lbl = QLabel(message)
        lbl.setWordWrap(True)
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        lbl.setObjectName("dialogLabel")
        self.content_layout.addWidget(lbl)

        self.button_layout.addStretch()
        self.ok_btn = self.add_button(button_text, "primary", self.accept)
        self.ok_btn.setFocus()

        self._finalize_size(min_width=450)
