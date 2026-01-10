"""
TitleBar - Custom title bar widget for main window.

Provides window controls, drag-to-move, and centered title with menu bar.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEvent, QPoint, QSize, Qt
from PyQt6.QtGui import QGuiApplication, QIcon
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenuBar,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from ui.constants import defer_call


class TitleBar(QWidget):
    """Custom title bar with menu, drag, and window controls."""

    def __init__(self, window: QMainWindow, menu_bar: QMenuBar) -> None:
        super().__init__(window)
        self._window = window
        self._drag_pos: QPoint | None = None
        self._menu_bar = menu_bar

        self.setObjectName("titleBar")
        self.setFixedHeight(44)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        self._menu_bar.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed
        )

        self.title_label = QLabel("Vociferous", self)
        self.title_label.setObjectName("titleBarLabel")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setMinimumWidth(0)

        btn_size = QSize(36, 28)
        icons_dir = Path(__file__).parents[4] / "icons"

        def make_btn(icon_name: str, obj: str, tooltip: str) -> QToolButton:
            button = QToolButton(self)
            button.setIcon(QIcon(str(icons_dir / f"{icon_name}.svg")))
            button.setIconSize(QSize(16, 16))
            button.setObjectName(obj)
            button.setFixedSize(btn_size)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            button.setToolTip(tooltip)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            return button

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(6)

        self.min_btn = make_btn("minimize", "titleBarControl", "Minimize")
        self.min_btn.clicked.connect(self._window.showMinimized)
        button_layout.addWidget(self.min_btn)

        self.max_btn = make_btn("maximize", "titleBarControl", "Maximize")
        self.max_btn.clicked.connect(self._toggle_maximize)
        button_layout.addWidget(self.max_btn)

        self.close_btn = make_btn("close", "titleBarClose", "Close")
        self.close_btn.clicked.connect(self._window.close)
        button_layout.addWidget(self.close_btn)

        self._controls = QWidget()
        self._controls.setLayout(button_layout)
        self._controls.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        self._left_slot = QWidget(self)
        left_l = QHBoxLayout(self._left_slot)
        left_l.setContentsMargins(0, 0, 0, 0)
        left_l.setSpacing(0)
        left_l.addWidget(self._menu_bar)
        left_l.addStretch(1)

        self._right_slot = QWidget(self)
        right_l = QHBoxLayout(self._right_slot)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(0)
        right_l.addStretch(1)
        right_l.addWidget(self._controls)

        layout.addWidget(self._left_slot)
        layout.addWidget(self.title_label, 1)
        layout.addWidget(self._right_slot)

        self.title_label.installEventFilter(self)
        defer_call(self._sync_side_slots)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_side_slots()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if QGuiApplication.platformName() == "wayland":
                if self._try_wayland_system_move():
                    event.accept()
                    self._drag_pos = None
                    return
            self._drag_pos = (
                event.globalPosition().toPoint()
                - self._window.frameGeometry().topLeft()
            )
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if (
            QGuiApplication.platformName() != "wayland"
            and event.buttons() & Qt.MouseButton.LeftButton
            and self._drag_pos
            and not self._window.isMaximized()
        ):
            self._window.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_maximize()
        super().mouseDoubleClickEvent(event)

    def _toggle_maximize(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
            self.max_btn.setText("▢")
        else:
            self._window.showMaximized()
            self.max_btn.setText("❐")

    def sync_state(self) -> None:
        """Sync maximize icon with window state."""
        self.max_btn.setText("❐" if self._window.isMaximized() else "▢")

    def _try_wayland_system_move(self) -> bool:
        """Request compositor-driven move on Wayland."""
        if self._window.isMaximized():
            return False
        self._window.winId()
        window_handle = self._window.windowHandle()
        if not window_handle:
            return False
        if hasattr(window_handle, "startSystemMove"):
            return bool(window_handle.startSystemMove())
        return False

    def eventFilter(self, source, event):
        if source is self.title_label:
            if (
                event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.LeftButton
            ):
                if (
                    QGuiApplication.platformName() == "wayland"
                    and self._try_wayland_system_move()
                ):
                    self._drag_pos = None
                    event.accept()
                    return True
                self._drag_pos = (
                    event.globalPosition().toPoint()
                    - self._window.frameGeometry().topLeft()
                )
            elif (
                event.type() == QEvent.Type.MouseMove
                and event.buttons() & Qt.MouseButton.LeftButton
            ):
                if (
                    QGuiApplication.platformName() != "wayland"
                    and self._drag_pos
                    and not self._window.isMaximized()
                ):
                    self._window.move(event.globalPosition().toPoint() - self._drag_pos)
                    return True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                self._drag_pos = None
        return super().eventFilter(source, event)

    def _sync_side_slots(self) -> None:
        """Match left/right slot widths so the title stays centered."""
        menu_w = self._menu_bar.sizeHint().width()
        ctrl_w = self._controls.sizeHint().width()
        width = max(menu_w, ctrl_w)
        self._left_slot.setFixedWidth(width)
        self._right_slot.setFixedWidth(width)
