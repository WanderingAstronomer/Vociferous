from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QWidget,
    QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QColor, QFont

from ui.constants import Typography

class TranscriptPreviewOverlay(QFrame):
    """
    Non-modal overlay to preview transcript content.
    """
    closed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("previewOverlay")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        
        # Styling handled by unified_stylesheet.py (QFrame#previewOverlay)
        
        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

        self._setup_ui()
        self.hide()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header_layout = QHBoxLayout()
        self._title_label = QLabel("Preview")
        self._title_label.setFont(QFont("Segoe UI", Typography.FONT_SIZE_MD, Typography.FONT_WEIGHT_BOLD))
        
        self._close_btn = QPushButton("×")
        self._close_btn.setFixedSize(24, 24)
        self._close_btn.setFlat(True)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self.close)
        
        header_layout.addWidget(self._title_label)
        header_layout.addStretch()
        header_layout.addWidget(self._close_btn)
        
        layout.addLayout(header_layout)

        # Content
        self._viewer = QTextBrowser()
        self._viewer.setOpenExternalLinks(False)
        layout.addWidget(self._viewer)

    def show_transcript(self, text: str, title: str = "Transcript") -> None:
        self._title_label.setText(title)
        self._viewer.setPlainText(text)
        self.show()
        self.raise_()
        self.setFocus()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def close(self) -> bool:
        self.hide()
        self.closed.emit()
        return super().close()
