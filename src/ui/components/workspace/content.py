"""
WorkspaceContent - Content display area that adapts to workspace state.

Displays:
- IDLE: Welcome message
- RECORDING: Waveform visualization
- VIEWING: Read-only transcript
- EDITING: Editable transcript
"""

from __future__ import annotations

from enum import IntEnum

from PyQt6.QtCore import QPoint, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QLabel,
    QMenu,
    QSizePolicy,
    QStackedWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.components.workspace.transcript_metrics import TranscriptMetrics
from ui.utils.clipboard_utils import copy_text
from ui.widgets.waveform_visualizer import WaveformVisualizer


class ContentPage(IntEnum):
    """Indices for the content stacked widget pages."""

    IDLE = 0
    RECORDING = 1
    VIEWING = 2
    EDITING = 3


class WorkspaceContent(QWidget):
    """
    Content display area that adapts to workspace state.

    Uses QStackedWidget to manage mutually exclusive content pages.

    Signals:
        textChanged(): Emitted when editor text changes
        copyRequested(): Emitted when copy is triggered
        editRequested(): Emitted when edit action is triggered
        deleteRequested(): Emitted when delete action is triggered
    """

    textChanged = pyqtSignal()
    copyRequested = pyqtSignal()
    editRequested = pyqtSignal()
    deleteRequested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("workspaceContent")
        self._current_text = ""
        self._current_timestamp = ""
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create content layout with stacked widget pages."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Stacked widget for mutually exclusive content
        self.stack = QStackedWidget()
        self.stack.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Page 0: IDLE - Welcome/Status label
        self.status_label = QLabel()
        self.status_label.setObjectName("contentLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.status_label.setContentsMargins(16, 0, 16, 0)
        self.stack.addWidget(self.status_label)  # Index 0

        # Page 1: RECORDING - Waveform visualizer
        self.waveform = WaveformVisualizer()
        self.waveform.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.waveform.setFixedHeight(130)
        self.stack.addWidget(self.waveform)  # Index 1

        # Page 2: VIEWING - Transcript viewer (QTextBrowser for better text selection)
        self.transcript_view = QTextBrowser()
        self.transcript_view.setObjectName("transcriptView")
        self.transcript_view.setReadOnly(True)
        self.transcript_view.setOpenExternalLinks(False)
        self.transcript_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.transcript_view.document().setDocumentMargin(16)
        self.transcript_view.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.transcript_view.customContextMenuRequested.connect(self._show_context_menu)
        self.stack.addWidget(self.transcript_view)  # Index 2

        # Page 3: EDITING - Transcript editor
        self.transcript_editor = QTextEdit()
        self.transcript_editor.setObjectName("transcriptEditor")
        self.transcript_editor.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.transcript_editor.document().setDocumentMargin(6)
        self.transcript_editor.setContentsMargins(16, 0, 16, 0)
        self.transcript_editor.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.transcript_editor.customContextMenuRequested.connect(
            self._show_context_menu
        )
        self.transcript_editor.textChanged.connect(self.textChanged.emit)
        self.stack.addWidget(self.transcript_editor)  # Index 3

        layout.addWidget(self.stack)

    def update_for_idle(self) -> None:
        """Show welcome message."""
        self.waveform.stop()
        self.status_label.setText(
            "Press your hotkey to start recording,\n"
            "or select a transcript from history."
        )
        self.stack.setCurrentIndex(ContentPage.IDLE)

    def update_for_recording(self) -> None:
        """Show waveform visualization during recording."""
        self.waveform.start()
        self.stack.setCurrentIndex(ContentPage.RECORDING)

    def update_for_viewing(self) -> None:
        """Show transcript in read-only view."""
        self.waveform.stop()
        self.transcript_view.setPlainText(self._current_text)
        self.stack.setCurrentIndex(ContentPage.VIEWING)

    def update_for_editing(self) -> None:
        """Show transcript in editor."""
        self.waveform.stop()
        self.transcript_editor.setPlainText(self._current_text)
        self.stack.setCurrentIndex(ContentPage.EDITING)
        self.transcript_editor.setFocus()

    def set_transcript(self, text: str, timestamp: str = "") -> None:
        """Set the current transcript text and timestamp."""
        self._current_text = text
        self._current_timestamp = timestamp

    def get_text(self) -> str:
        """Get current text (from editor if editing, otherwise stored)."""
        if self.stack.currentIndex() == ContentPage.EDITING:
            return self.transcript_editor.toPlainText()
        return self._current_text

    def get_timestamp(self) -> str:
        """Get timestamp of current transcript."""
        return self._current_timestamp

    def clear(self) -> None:
        """Clear transcript state."""
        self._current_text = ""
        self._current_timestamp = ""
        self.transcript_view.clear()
        self.transcript_editor.clear()
        self.metrics.clear()
        self.metrics.hide()

    @pyqtSlot(QPoint)
    def _show_context_menu(self, position: QPoint) -> None:
        """Show context menu for transcript actions."""
        if not self._current_text:
            return

        menu = QMenu(self)

        # Copy action
        copy_action = menu.addAction("Copy to Clipboard")
        copy_action.triggered.connect(self._copy_transcript)

        # Edit action (only in viewing mode)
        if self.stack.currentIndex() == ContentPage.VIEWING:
            menu.addSeparator()
            edit_action = menu.addAction("Edit")
            edit_action.triggered.connect(self.editRequested.emit)

        # Delete action
        menu.addSeparator()
        delete_action = menu.addAction("Delete Entry")
        delete_action.triggered.connect(self.deleteRequested.emit)

        menu.exec(QCursor.pos())

    @pyqtSlot()
    def _copy_transcript(self) -> None:
        """Copy current transcript to clipboard."""
        text = self.get_text()
        if text:
            copy_text(text)
            self.copyRequested.emit()

    def add_audio_level(self, level: float) -> None:
        """
        Add audio level to waveform visualization.

        Args:
            level: Normalized amplitude (0.0 to 1.0)
        """
        self.waveform.add_level(level)
