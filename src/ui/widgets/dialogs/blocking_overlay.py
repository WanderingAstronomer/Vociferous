from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QPalette, QBrush
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QProgressBar,
)

import ui.constants.colors as c


class BlockingOverlay(QWidget):
    """
    A semi-transparent overlay that blocks user interaction with the entire window.
    Used during critical SLM loading/provisioning states.
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        # self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

        # Transparent black background
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setBrush(QPalette.ColorRole.Window, QBrush(QColor(0, 0, 0, 180)))
        self.setPalette(palette)

        self.hide()

        self._setup_ui()

    def sizeHint(self) -> QSize:
        """
        Return preferred size for the blocking overlay.
        
        Per Qt6 layout documentation, custom widgets must implement sizeHint()
        to provide layout engines with sizing information.
        
        Overlays typically fill parent, so return a reasonable default.
        
        Returns:
            QSize: Preferred size of 600x400 pixels
        
        References:
            - layout.html § "Custom Widgets in Layouts"
        """
        return QSize(600, 400)

    def minimumSizeHint(self) -> QSize:
        """
        Return minimum acceptable size for the overlay.
        
        Returns:
            QSize: Minimum size of 300x200 pixels
        """
        return QSize(300, 200)

    def _setup_ui(self) -> None:
        """Setup the overlay UI."""
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Message Container
        container = QWidget()
        container.setStyleSheet(f"""
            QWidget {{
                background-color: {c.GRAY_2};
                border: 1px solid {c.GRAY_6};
                border-radius: 8px;
            }}
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(32, 24, 32, 24)
        container_layout.setSpacing(16)

        # Title
        self.lbl_title = QLabel("System Busy")
        self.lbl_title.setStyleSheet(
            f"color: {c.GRAY_0}; font-size: 16px; font-weight: bold; border: none;"
        )
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(self.lbl_title)

        # Status
        self.lbl_status = QLabel("Initializing...")
        self.lbl_status.setStyleSheet(
            f"color: {c.GRAY_4}; font-size: 14px; border: none;"
        )
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(self.lbl_status)

        # Spinner/Progress (Indeterminate)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # Indeterminate
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {c.GRAY_1};
                border: none;
                border-radius: 2px;
                height: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {c.BLUE_4};
                border-radius: 2px;
            }}
        """)
        self.progress.setFixedWidth(200)
        container_layout.addWidget(self.progress, 0, Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(container)

    def show_message(self, message: str):
        self.lbl_status.setText(message)
        self.show()
        self.raise_()

    def resizeEvent(self, event):
        self.resize(self.parent().size())
        super().resizeEvent(event)

    def cleanup(self) -> None:
        """
        Clean up overlay resources.
        
        Per Vociferous cleanup protocol, all widgets should implement cleanup().
        BlockingOverlay has no persistent timers or threads, but implements
        this for protocol compliance.
        
        This method is idempotent and safe to call multiple times.
        """
        # No active resources to clean up, but hide if visible
        if self.isVisible():
            self.hide()
