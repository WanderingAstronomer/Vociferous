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
from PyQt6.QtGui import QCursor, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.constants import Colors, Typography
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
        self._variants: list[dict] = []
        self._current_variant_index = 0
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create content layout with stacked widget pages."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- CAROUSEL BAR (Refinement Navigation) ---
        self.carousel_container = QWidget()
        self.carousel_container.setObjectName("carouselContainer")
        self.carousel_container.hide()

        # Carousel Styling handled in unified_stylesheet.py (QWidget#carouselContainer)

        carousel_layout = QHBoxLayout(self.carousel_container)
        carousel_layout.setContentsMargins(12, 4, 12, 4)
        carousel_layout.setSpacing(8)
        carousel_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_prev_variant = QPushButton("<")
        self.btn_prev_variant.setFixedSize(24, 24)
        self.btn_prev_variant.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_prev_variant.setToolTip("Previous Version")
        self.btn_prev_variant.clicked.connect(self.prev_variant)

        self.lbl_variant_info = QLabel("Raw")
        self.lbl_variant_info.setObjectName("variantInfoLabel")
        self.lbl_variant_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_font = self.lbl_variant_info.font()
        info_font.setPointSize(Typography.SMALL_SIZE)
        info_font.setBold(True)
        self.lbl_variant_info.setFont(info_font)
        # self.lbl_variant_info.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};") # Handled by parent selector or object name

        self.btn_next_variant = QPushButton(">")
        self.btn_next_variant.setFixedSize(24, 24)
        self.btn_next_variant.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_next_variant.setToolTip("Next Version")
        self.btn_next_variant.clicked.connect(self.next_variant)

        carousel_layout.addWidget(self.btn_prev_variant)
        carousel_layout.addWidget(self.lbl_variant_info)
        carousel_layout.addWidget(self.btn_next_variant)

        layout.addWidget(self.carousel_container)
        # ----------------------------------------------

        # Shortcuts (Alt+Left/Right for carousel navigation)
        self.shortcut_prev = QShortcut(QKeySequence("Alt+Left"), self)
        self.shortcut_prev.activated.connect(self.prev_variant)

        self.shortcut_next = QShortcut(QKeySequence("Alt+Right"), self)
        self.shortcut_next.activated.connect(self.next_variant)

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

        # Page 1: RECORDING - Waveform visualizer + Live Text
        self.recording_container = QWidget()
        recording_layout = QVBoxLayout(self.recording_container)
        recording_layout.setContentsMargins(0, 0, 0, 0)
        recording_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.waveform = WaveformVisualizer()
        self.waveform.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.waveform.setFixedHeight(130)
        recording_layout.addWidget(self.waveform)

        self.live_text_label = QLabel()
        self.live_text_label.setObjectName("liveTextLabel")
        self.live_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.live_text_label.setWordWrap(True)
        live_font = QFont()
        live_font.setPointSize(Typography.FONT_SIZE_LG)
        self.live_text_label.setFont(live_font)
        # Style can be handled in stylesheet, or here for now
        self.live_text_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        recording_layout.addWidget(self.live_text_label)
        
        self.stack.addWidget(self.recording_container)  # Index 1

        # Page 2: VIEWING - Transcript viewer (QTextBrowser for better text selection)
        self.transcript_view = QTextBrowser()
        self.transcript_view.setObjectName("transcriptView")
        self.transcript_view.setFrameShape(QFrame.Shape.NoFrame)
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
        self.transcript_editor.setFrameShape(QFrame.Shape.NoFrame)
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

    def scroll_to_top(self) -> None:
        """Scroll current content to top."""
        if self.stack.currentIndex() == ContentPage.VIEWING:
            self.transcript_view.verticalScrollBar().setValue(0)
        elif self.stack.currentIndex() == ContentPage.EDITING:
            self.transcript_editor.verticalScrollBar().setValue(0)

    def set_audio_level(self, level: float) -> None:
        """Update waveform audio level."""
        self.waveform.current_level = level

    def set_live_text(self, text: str) -> None:
        """Update live transcription text."""
        self.live_text_label.setText(text)

    def update_for_idle(self) -> None:
        """Show welcome message."""
        self.waveform.stop()
        self.carousel_container.hide()
        self.status_label.setText(
            "Press your hotkey to start recording,\n"
            "or select a transcript from history."
        )
        self.stack.setCurrentIndex(ContentPage.IDLE)

    def update_for_recording(self) -> None:
        """Show waveform visualization during recording."""
        self.waveform.start()
        self.carousel_container.hide()
        self.stack.setCurrentIndex(ContentPage.RECORDING)

    def update_for_viewing(self) -> None:
        """Show transcript in read-only view."""
        self.waveform.stop()
        # Restore carousel if we have variants
        self._update_carousel_ui()
        self.transcript_view.setPlainText(self._current_text)
        self.stack.setCurrentIndex(ContentPage.VIEWING)

    def update_for_editing(self) -> None:
        """Show transcript in editor."""
        self.waveform.stop()
        self.carousel_container.hide()  # Hide carousel during editing
        self.transcript_editor.setPlainText(self._current_text)
        self.stack.setCurrentIndex(ContentPage.EDITING)
        self.transcript_editor.setFocus()

    def set_transcript(self, text: str, timestamp: str = "") -> None:
        """Set the current transcript text and timestamp."""
        self._current_text = text
        self._current_timestamp = timestamp

        # If clearing (empty text), also clear variants and hide carousel
        if not text and not timestamp:
            self._variants = []
            self.carousel_container.hide()

        # Update editors immediately if active, otherwise update_for_... handles it
        if self.stack.currentIndex() == ContentPage.VIEWING:
            self.transcript_view.setPlainText(text)
        elif self.stack.currentIndex() == ContentPage.EDITING:
            self.transcript_editor.setPlainText(text)

    def set_variants(self, variants: list[dict]) -> None:
        """Set the list of transcript variants and update carousel."""
        self._variants = variants

        # Determine initial index
        self._current_variant_index = 0
        if variants:
            found_current = False
            # Prefer 'is_current' flag
            for i, v in enumerate(variants):
                if v.get("is_current"):
                    self._current_variant_index = i
                    found_current = True
                    break

            # If no current flag (e.g. legacy), use last refined, or last item
            if not found_current and variants:
                self._current_variant_index = len(variants) - 1

            # Initial display update
            if 0 <= self._current_variant_index < len(variants):
                self.set_transcript(
                    variants[self._current_variant_index]["text"],
                    self._current_timestamp,
                )

        self._update_carousel_ui()

    def _update_carousel_ui(self) -> None:
        """Update visibility and labels of the carousel."""
        if not self._variants or len(self._variants) <= 1:
            self.carousel_container.hide()
            return

        # Ensure index is valid
        if self._current_variant_index >= len(self._variants):
            self._current_variant_index = len(self._variants) - 1

        self.carousel_container.show()

        current = self._variants[self._current_variant_index]
        kind = current.get("kind", "raw")

        # Label Logic
        if kind == "raw":
            label = "Original Transcript"
        elif kind == "refined":
            # Count how far along in refinements we are
            refined_list = [v for v in self._variants if v.get("kind") == "refined"]
            if len(refined_list) <= 1:
                label = "Refined Transcript"
            else:
                try:
                    # Find THIS variant's index within the refined sub-list
                    curr_id = current.get("id")
                    if curr_id:
                        matches = [
                            i
                            for i, v in enumerate(refined_list)
                            if v.get("id") == curr_id
                        ]
                        if matches:
                            idx = matches[0] + 1
                            label = f"Refined Transcript ({idx}/{len(refined_list)})"
                        else:
                            label = "Refined Transcript"
                    else:
                        label = "Refined Transcript"
                except Exception:
                    label = "Refined Transcript"
        else:
            # user_edit or other
            label = kind.replace("_", " ").title()

        self.lbl_variant_info.setText(label)

        # Button States
        self.btn_prev_variant.setEnabled(self._current_variant_index > 0)
        self.btn_next_variant.setEnabled(
            self._current_variant_index < len(self._variants) - 1
        )

    @pyqtSlot()
    def prev_variant(self) -> None:
        """Navigate to previous variant."""
        if self._variants and self._current_variant_index > 0:
            self._current_variant_index -= 1
            self.set_transcript(
                self._variants[self._current_variant_index]["text"],
                self._current_timestamp,
            )
            self._update_carousel_ui()

    @pyqtSlot()
    def next_variant(self) -> None:
        """Navigate to next variant."""
        if self._variants and self._current_variant_index < len(self._variants) - 1:
            self._current_variant_index += 1
            self.set_transcript(
                self._variants[self._current_variant_index]["text"],
                self._current_timestamp,
            )
            self._update_carousel_ui()

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
