"""
TitleBar - Custom title bar widget for main window.

Provides window controls, drag-to-move, and centered title.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QPoint, QSize, Qt
from PyQt6.QtGui import QGuiApplication, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from src.core.resource_manager import ResourceManager


class TitleBar(QWidget):
    """Custom title bar with drag and window controls."""

    def __init__(self, window: QMainWindow) -> None:
        super().__init__(window)
        self._window = window
        self._drag_pos: QPoint | None = None

        self.setObjectName("titleBar")
        self.setFixedHeight(44)

        # Enforce painting of background-color from stylesheet
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        self.title_label = QLabel("Vociferous", self)
        self.title_label.setObjectName("titleBarLabel")
        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.title_label.setMinimumWidth(0)

        # Icon label for system tray icon
        self.icon_label = QLabel(self)
        self.icon_label.setObjectName("titleBarIcon")
        icon_path = ResourceManager.get_icon_path("system_tray_icon")
        pixmap = QPixmap(icon_path).scaled(
            16,
            16,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.icon_label.setPixmap(pixmap)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_size = QSize(36, 28)

        def make_btn(icon_name: str, obj: str) -> QToolButton:
            button = QToolButton(self)
            icon_path = ResourceManager.get_icon_path(icon_name)
            button.setIcon(QIcon(icon_path))
            button.setIconSize(QSize(16, 16))
            button.setObjectName(obj)
            button.setFixedSize(btn_size)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            return button

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(6)

        self.min_btn = make_btn("title_bar-minimize", "titleBarControl")
        self.min_btn.clicked.connect(self._window.showMinimized)
        button_layout.addWidget(self.min_btn)

        self.max_btn = make_btn("title_bar-maximize", "titleBarControl")
        self.max_btn.clicked.connect(self._toggle_maximize)
        button_layout.addWidget(self.max_btn)

        self.close_btn = make_btn("title_bar-close", "titleBarClose")
        self.close_btn.clicked.connect(self._window.close)
        button_layout.addWidget(self.close_btn)

        self._controls = QWidget()
        self._controls.setLayout(button_layout)
        self._controls.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        # Right slot (window controls)
        self._right_slot = QWidget(self)
        right_l = QHBoxLayout(self._right_slot)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(0)
        right_l.addStretch(1)
        right_l.addWidget(self._controls)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label, 1)
        layout.addWidget(self._right_slot)

        self.title_label.installEventFilter(self)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)

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
