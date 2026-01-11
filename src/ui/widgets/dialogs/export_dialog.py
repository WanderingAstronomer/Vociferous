"""
Custom Export Dialog for saving history files.

Provides a styled, draggable dialog for exporting history with format selection
and file naming in a consistent UI style.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ui.components.title_bar import DialogTitleBar
from ui.constants import MAJOR_GAP, MINOR_GAP, Colors, Dimensions, Typography
from ui.widgets.styled_button import ButtonStyle, StyledButton


class ExportDialog(QDialog):
    """
    Custom export dialog for saving history files.

    Features:
    - Draggable title bar
    - File format selection (TXT, CSV, MD)
    - Filename input
    - Custom save location
    - Styled to match app theme
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setModal(True)

        self._selected_format = "txt"
        self._filename = "vociferous_history"
        self._save_directory = Path.home()

        self._setup_ui()
        self.setMinimumWidth(500)
        self.adjustSize()

    def _setup_ui(self) -> None:
        """Create dialog layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Custom title bar (draggable)
        self.title_bar = DialogTitleBar("Export History", self)
        self.title_bar.closeRequested.connect(self.reject)
        main_layout.addWidget(self.title_bar)

        # Content area
        content = QWidget()
        content.setObjectName("dialogContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(MAJOR_GAP, MAJOR_GAP, MAJOR_GAP, MAJOR_GAP)
        content_layout.setSpacing(MAJOR_GAP)

        # File format selection
        format_label = QLabel("Export Format:")
        format_label.setObjectName("dialogLabel")
        content_layout.addWidget(format_label)

        format_container = QWidget()
        format_layout = QHBoxLayout(format_container)
        format_layout.setContentsMargins(0, 0, 0, 0)
        format_layout.setSpacing(MAJOR_GAP)

        self.format_group = QButtonGroup(self)
        
        self.txt_radio = QRadioButton("Plain Text (.txt)")
        self.txt_radio.setChecked(True)
        self.txt_radio.toggled.connect(lambda: self._on_format_changed("txt"))
        self.format_group.addButton(self.txt_radio)
        format_layout.addWidget(self.txt_radio)

        self.csv_radio = QRadioButton("CSV (.csv)")
        self.csv_radio.toggled.connect(lambda: self._on_format_changed("csv"))
        self.format_group.addButton(self.csv_radio)
        format_layout.addWidget(self.csv_radio)

        self.md_radio = QRadioButton("Markdown (.md)")
        self.md_radio.toggled.connect(lambda: self._on_format_changed("md"))
        self.format_group.addButton(self.md_radio)
        format_layout.addWidget(self.md_radio)

        format_layout.addStretch()
        content_layout.addWidget(format_container)

        # Filename input
        filename_label = QLabel("Filename:")
        filename_label.setObjectName("dialogLabel")
        content_layout.addWidget(filename_label)

        filename_container = QWidget()
        filename_row = QHBoxLayout(filename_container)
        filename_row.setContentsMargins(0, 0, 0, 0)
        filename_row.setSpacing(MINOR_GAP)

        self.filename_input = QLineEdit()
        self.filename_input.setObjectName("dialogInput")
        self.filename_input.setText(self._filename)
        self.filename_input.textChanged.connect(self._on_filename_changed)
        self.filename_input.setPlaceholderText("Enter filename...")
        filename_row.addWidget(self.filename_input, 1)

        self.extension_label = QLabel(f".{self._selected_format}")
        self.extension_label.setObjectName("dialogLabel")
        filename_row.addWidget(self.extension_label)

        content_layout.addWidget(filename_container)

        # Save location
        location_label = QLabel("Save Location:")
        location_label.setObjectName("dialogLabel")
        content_layout.addWidget(location_label)

        location_container = QWidget()
        location_row = QHBoxLayout(location_container)
        location_row.setContentsMargins(0, 0, 0, 0)
        location_row.setSpacing(MINOR_GAP)

        self.location_input = QLineEdit()
        self.location_input.setObjectName("dialogInput")
        self.location_input.setText(str(self._save_directory))
        self.location_input.setReadOnly(True)
        location_row.addWidget(self.location_input, 1)

        browse_btn = StyledButton("Browse...", ButtonStyle.SECONDARY)
        browse_btn.setFixedHeight(42)
        browse_btn.clicked.connect(self._browse_location)
        location_row.addWidget(browse_btn)

        content_layout.addWidget(location_container)

        # Full path preview
        preview_label = QLabel("Full Path:")
        preview_label.setObjectName("dialogLabel")
        content_layout.addWidget(preview_label)

        self.path_preview = QLabel()
        self.path_preview.setObjectName("dialogLabelMuted")
        self.path_preview.setWordWrap(True)
        content_layout.addWidget(self.path_preview)
        self._update_path_preview()

        content_layout.addStretch()
        main_layout.addWidget(content, 1)

        # Button row
        button_container = QWidget()
        button_container.setObjectName("dialogButtonContainer")

        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(MAJOR_GAP, 20, MAJOR_GAP, 20)
        button_layout.setSpacing(MAJOR_GAP)
        button_layout.addStretch()

        cancel_btn = StyledButton("Cancel", ButtonStyle.SECONDARY)
        cancel_btn.setFixedHeight(46)
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self.export_btn = StyledButton("Export", ButtonStyle.PRIMARY)
        self.export_btn.setFixedHeight(46)
        self.export_btn.setMinimumWidth(100)
        self.export_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.export_btn)

        main_layout.addWidget(button_container)

    def _on_format_changed(self, fmt: str) -> None:
        """Handle format selection change."""
        self._selected_format = fmt
        self.extension_label.setText(f".{fmt}")
        self._update_path_preview()

    def _on_filename_changed(self, text: str) -> None:
        """Handle filename input change."""
        self._filename = text.strip()
        self.export_btn.setEnabled(bool(self._filename))
        self._update_path_preview()

    def _browse_location(self) -> None:
        """Browse for save location using Qt-styled file dialog."""
        from PyQt6.QtWidgets import QFileDialog, QTreeView, QPushButton, QDialogButtonBox
        from PyQt6.QtCore import QTimer
        
        # Create a custom file dialog instance
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Select Save Location")
        dialog.setDirectory(str(self._save_directory))
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
        
        # Configure dialog widgets after it's fully constructed
        def configure_dialog():
            # Hide extra columns in tree view
            tree_view = dialog.findChild(QTreeView)
            if tree_view:
                for i in range(4, tree_view.header().count()):
                    tree_view.setColumnHidden(i, True)
            
            # Style the buttons to match app design
            button_box = dialog.findChild(QDialogButtonBox)
            if button_box:
                # Find and style the buttons
                for button in button_box.buttons():
                    role = button_box.buttonRole(button)
                    
                    # Style Choose/Open button (AcceptRole)
                    if role == QDialogButtonBox.ButtonRole.AcceptRole:
                        button.setStyleSheet(f"""
                            QPushButton {{
                                background-color: {Colors.PRIMARY};
                                color: {Colors.TEXT_ON_ACCENT};
                                border: none;
                                border-radius: {Dimensions.BORDER_RADIUS}px;
                                padding: 12px 24px;
                                font-size: {Typography.BODY_SIZE}pt;
                                font-weight: {Typography.FONT_WEIGHT_MEDIUM};
                                min-width: 100px;
                            }}
                            QPushButton:hover {{
                                background-color: {Colors.PRIMARY_HOVER};
                            }}
                            QPushButton:pressed {{
                                background-color: {Colors.PRIMARY_PRESSED};
                            }}
                        """)
                    
                    # Style Cancel button (RejectRole)
                    elif role == QDialogButtonBox.ButtonRole.RejectRole:
                        button.setStyleSheet(f"""
                            QPushButton {{
                                background-color: {Colors.BG_TERTIARY};
                                color: {Colors.TEXT_PRIMARY};
                                border: 1px solid {Colors.BORDER_DEFAULT};
                                border-radius: {Dimensions.BORDER_RADIUS}px;
                                padding: 12px 24px;
                                font-size: {Typography.BODY_SIZE}pt;
                                font-weight: {Typography.FONT_WEIGHT_MEDIUM};
                                min-width: 100px;
                            }}
                            QPushButton:hover {{
                                background-color: {Colors.HOVER_BG_ITEM};
                                border-color: {Colors.ACCENT_PRIMARY};
                            }}
                            QPushButton:pressed {{
                                background-color: {Colors.BG_SECONDARY};
                            }}
                        """)
        
        # Apply configuration after dialog is shown
        QTimer.singleShot(0, configure_dialog)
        
        if dialog.exec():
            selected = dialog.selectedFiles()
            if selected:
                self._save_directory = Path(selected[0])
                self.location_input.setText(str(self._save_directory))
                self._update_path_preview()

    def _update_path_preview(self) -> None:
        """Update the full path preview label."""
        if self._filename:
            full_path = self._save_directory / f"{self._filename}.{self._selected_format}"
            self.path_preview.setText(str(full_path))
        else:
            self.path_preview.setText("(enter a filename)")

    def get_export_path(self) -> tuple[Path, str]:
        """Return (full_path, format) tuple."""
        full_path = self._save_directory / f"{self._filename}.{self._selected_format}"
        return (full_path, self._selected_format)
