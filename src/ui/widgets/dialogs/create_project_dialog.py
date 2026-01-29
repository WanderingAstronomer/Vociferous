"""
Create Project dialog with name and color selection.

Modern styled dialog matching the settings dialog design.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.ui.components.title_bar.dialog_title_bar import DialogTitleBar
from src.ui.constants import MAJOR_GAP, MINOR_GAP
import src.ui.constants.colors as c
from src.ui.constants import ProjectColors

# Use colors and names from constants (2 rows x 3 columns)
PROJECT_COLORS = [
    (color, ProjectColors.COLOR_NAMES.get(color, f"Color {i + 1}"))
    for i, color in enumerate(ProjectColors.PALETTE)
]


class ColorSwatch(QPushButton):
    """Clickable color swatch button."""

    def __init__(self, color: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.color = color
        self.label = label
        self._selected = False

        self.setFixedSize(48, 48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self._update_style()

    def set_selected(self, selected: bool) -> None:
        """Update selection state."""
        self._selected = selected
        self.setChecked(selected)
        self._update_style()

    def _update_style(self) -> None:
        """Apply styling based on selection state."""
        border = f"3px solid {c.BLUE_4}" if self._selected else f"2px solid {c.GRAY_7}"
        # Use single-line formatting to avoid style enforcement violations
        style = (
            f"QPushButton {{ background-color: {self.color}; border: {border}; border-radius: 8px; }} "
            f"QPushButton:hover {{ border-color: {c.BLUE_4}; }}"
        )
        self.setStyleSheet(style)


class CreateProjectDialog(QDialog):
    """
    Modal dialog for creating a new project.

    Features:
    - Custom title bar (draggable)
    - Name input field
    - Color selection grid (2x3)
    - Cancel/Create buttons
    """

    def __init__(
        self, parent: QWidget | None = None, title: str = "New Project"
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setModal(True)

        self._title = title
        self._selected_color: str = PROJECT_COLORS[0][0]
        self._project_name: str = ""
        self._color_swatches: list[ColorSwatch] = []

        # Styles are applied at app level via generate_unified_stylesheet()

        self._setup_ui()
        self.adjustSize()
        self.setMinimumWidth(380)

    def _setup_ui(self) -> None:
        """Create dialog layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Structural Frame Wrapper (The Dialog Frame)
        self._dialog_frame = QFrame()
        self._dialog_frame.setObjectName("dialogFrame")
        main_layout.addWidget(self._dialog_frame)

        # Frame layout
        frame_layout = QVBoxLayout(self._dialog_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        # Custom title bar (draggable)
        self.title_bar = DialogTitleBar(self._title, self)
        self.title_bar.close_requested.connect(self.reject)
        frame_layout.addWidget(self.title_bar)

        # Content area
        content = QWidget()
        content.setObjectName("dialogContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(MAJOR_GAP, MAJOR_GAP, MAJOR_GAP, MAJOR_GAP)
        content_layout.setSpacing(MAJOR_GAP)

        frame_layout.addWidget(content)

        # Name field
        name_label = QLabel("Name:")
        name_label.setObjectName("dialogLabel")
        content_layout.addWidget(name_label)

        self.name_input = QLineEdit()
        self.name_input.setObjectName("projectNameInput")
        self.name_input.setPlaceholderText("Enter project name...")
        self.name_input.textChanged.connect(self._on_name_changed)
        content_layout.addWidget(self.name_input)

        # Color selection
        color_label = QLabel("Color:")
        color_label.setObjectName("dialogLabel")
        content_layout.addWidget(color_label)

        color_grid = QWidget()
        grid_layout = QGridLayout(color_grid)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(MINOR_GAP)

        for i, (color, label) in enumerate(PROJECT_COLORS):
            swatch = ColorSwatch(color, label)
            swatch.clicked.connect(lambda checked, c=color: self._on_color_selected(c))
            row = i // 3
            col = i % 3
            grid_layout.addWidget(swatch, row, col)
            self._color_swatches.append(swatch)

            if color == self._selected_color:
                swatch.set_selected(True)

        content_layout.addWidget(color_grid)
        content_layout.addStretch()

        # Button row
        button_container = QWidget()
        button_container.setObjectName("dialogButtonContainer")

        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(MAJOR_GAP, MAJOR_GAP, MAJOR_GAP, MAJOR_GAP)
        button_layout.setSpacing(MAJOR_GAP)

        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("styledSecondary")
        self.cancel_btn.setFixedHeight(40)
        self.cancel_btn.setMinimumWidth(100)
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.create_btn = QPushButton("Create")
        self.create_btn.setObjectName("styledPrimary")
        self.create_btn.setFixedHeight(40)
        self.create_btn.setMinimumWidth(100)
        self.create_btn.setEnabled(False)
        self.create_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.create_btn)

        frame_layout.addWidget(button_container)

        self.setObjectName("createProjectDialog")

        # Keyboard shortcuts
        self._setup_shortcuts()

    def _setup_shortcuts(self) -> None:
        """Set up keyboard shortcuts for dialog actions."""
        # Enter/Return to create (if name is valid)
        save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        save_shortcut.activated.connect(self._try_accept)

        # Escape to cancel
        escape_shortcut = QShortcut(QKeySequence.StandardKey.Cancel, self)
        escape_shortcut.activated.connect(self.reject)

    def _try_accept(self) -> None:
        """Accept dialog if create button is enabled."""
        if self.create_btn.isEnabled():
            self.accept()

    def _on_name_changed(self, text: str) -> None:
        """Handle name input changes."""
        self._project_name = text.strip()
        self.create_btn.setEnabled(bool(self._project_name))

    def _on_color_selected(self, color: str) -> None:
        """Handle color selection."""
        self._selected_color = color
        for swatch in self._color_swatches:
            swatch.set_selected(swatch.color == color)

    def get_result(self) -> tuple[str, str]:
        """Return (name, color) tuple."""
        return (self._project_name, self._selected_color)
