"""
DialogTitleBar - Simplified title bar for dialogs.

Features close button only (no minimize/maximize) and is draggable.
Works on both X11 and Wayland via platform-specific dragging methods.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QIcon
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QToolButton,
    QWidget,
)


class DialogTitleBar(QWidget):
    """
    Simplified title bar for dialogs.

    Features:
    - Custom title text
    - Close button only (no minimize/maximize)
    - Draggable

    Signals:
        closeRequested(): Emitted when close button is clicked
        minimizeRequested(): Emitted when minimize is requested
    """

    closeRequested = pyqtSignal()
    minimizeRequested = pyqtSignal()

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self._drag_pos: QPoint | None = None

        self.setObjectName("dialogTitleBar")
        self.setFixedHeight(44)

        # Enforce painting of background-color from stylesheet
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 10, 8)
        layout.setSpacing(8)

        # Title label (left-aligned for dialogs)
        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("dialogTitleLabel")
        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        # Close button
        icons_dir = Path(__file__).parents[4] / "assets" / "icons"
        self.close_btn = QToolButton(self)
        self.close_btn.setIcon(QIcon(str(icons_dir / "title_bar-close.svg")))
        self.close_btn.setIconSize(QSize(16, 16))
        self.close_btn.setObjectName("titleBarClose")
        self.close_btn.setFixedSize(QSize(36, 28))
        self.close_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.close_btn.setToolTip("Close")
        self.close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.close_btn.clicked.connect(self.closeRequested)

        layout.addWidget(self.title_label, 1)
        layout.addWidget(self.close_btn)

    def mousePressEvent(self, event) -> None:
        """Enable window dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            parent = self.window()
            if parent:
                # On Wayland, use compositor-driven move (system move)
                if QGuiApplication.platformName() == "wayland":
                    if self._try_wayland_system_move(parent):
                        event.accept()
                        self._drag_pos = None
                        return

                # On X11, track position for manual dragging
                self._drag_pos = (
                    event.globalPosition().toPoint() - parent.frameGeometry().topLeft()
                )
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        """Handle window dragging (X11 only; Wayland uses system move)."""
        # Only manual drag on X11; Wayland is handled by compositor in mousePressEvent
        if (
            QGuiApplication.platformName() != "wayland"
            and event.buttons() & Qt.MouseButton.LeftButton
            and self._drag_pos
        ):
            parent = self.window()
            if parent:
                parent.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        """End dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = None
            event.accept()

    def _try_wayland_system_move(self, parent: QWidget) -> bool:
        """Request compositor-driven move on Wayland."""
        parent.winId()  # Ensure window ID is created
        window_handle = parent.windowHandle()
        if not window_handle:
            return False
        if hasattr(window_handle, "startSystemMove"):
            return bool(window_handle.startSystemMove())
        return False

    def cleanup(self) -> None:
        """
        Clean up title bar resources.
        
        Per Vociferous cleanup protocol, all widgets should implement cleanup().
        DialogTitleBar has no persistent timers or threads.
        
        This method is idempotent and safe to call multiple times.
        """
        # Reset drag state
        self._drag_pos = None
