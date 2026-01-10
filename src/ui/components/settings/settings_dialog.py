"""
SettingsDialog - Modern settings dialog with custom title bar.

Features:
- Custom title bar (draggable)
- Consolidated single-page layout
- Schema-driven form generation
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from key_listener import KeyListener
from ui.components.title_bar import DialogTitleBar
from ui.constants import Spacing
from ui.widgets.hotkey_widget import HotkeyWidget
from utils import ConfigManager


def _has_gpu() -> bool:
    """Check if CUDA/GPU is available."""
    try:
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


class SettingsDialog(QDialog):
    """
    Modern settings dialog matching main window styling.

    Features:
    - Custom title bar (draggable)
    - Consolidated single-page layout (no tabs)
    - Schema-driven form generation
    - Focused on essential user-facing options
    """

    HIDDEN_SECTIONS: set[str] = {"_internal", "ui_state"}

    def __init__(
        self, key_listener: KeyListener, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        # Use Window flag instead of Dialog for better Wayland compatibility
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.key_listener = key_listener
        self.schema = ConfigManager.get_schema()
        self.widgets: dict[tuple[str, str], QWidget] = {}
        self.has_gpu = _has_gpu()

        self._setup_ui()
        self._populate_settings()

        self.setMinimumWidth(600)
        self.adjustSize()

    def _setup_ui(self) -> None:
        """Create dialog layout with custom title bar."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Custom title bar
        self.title_bar = DialogTitleBar("Settings", self)
        self.title_bar.closeRequested.connect(self.reject)
        self.title_bar.minimizeRequested.connect(self.showMinimized)
        main_layout.addWidget(self.title_bar)

        # Content area with scroll
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setObjectName("settingsScrollArea")

        # Scrollable content widget
        content_widget = QWidget()
        content_widget.setObjectName("dialogContent")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(
            Spacing.MAJOR_GAP, 12, Spacing.MAJOR_GAP, 12
        )
        content_layout.setSpacing(12)

        # Settings form
        self.form_layout = QFormLayout()
        self.form_layout.setSpacing(8)
        self.form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        content_layout.addLayout(self.form_layout)

        content_layout.addStretch()
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area, 1)

        # Button row
        button_row = self._create_button_row()
        main_layout.addWidget(button_row)

        self.setObjectName("settingsDialog")

        # Keyboard shortcuts
        self._setup_shortcuts()

    def _setup_shortcuts(self) -> None:
        """Set up keyboard shortcuts for dialog actions."""
        # Ctrl+S to apply and accept (save)
        save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        save_shortcut.activated.connect(self._apply_and_accept)

        # Escape to cancel (already handled by QDialog, but explicit is clearer)
        escape_shortcut = QShortcut(QKeySequence.StandardKey.Cancel, self)
        escape_shortcut.activated.connect(self._on_reject)

        # Ctrl+W to close (common dialog shortcut)
        close_shortcut = QShortcut(QKeySequence.StandardKey.Close, self)
        close_shortcut.activated.connect(self._on_reject)

    def _create_button_row(self) -> QWidget:
        """Create OK/Cancel/Apply button row."""
        button_container = QWidget()
        button_container.setObjectName("settingsButtonContainer")

        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(
            Spacing.MAJOR_GAP, 12, Spacing.MAJOR_GAP, 12
        )
        button_layout.setSpacing(Spacing.MINOR_GAP)

        button_layout.addStretch()

        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedHeight(36)
        self.cancel_btn.setMinimumWidth(100)
        self.cancel_btn.clicked.connect(self._on_reject)
        self.cancel_btn.setObjectName("settingsCancelBtn")
        button_layout.addWidget(self.cancel_btn)

        # Apply button
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setFixedHeight(36)
        self.apply_btn.setMinimumWidth(100)
        self.apply_btn.clicked.connect(self._apply_only)
        self.apply_btn.setObjectName("settingsApplyBtn")
        button_layout.addWidget(self.apply_btn)

        # OK button
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setFixedHeight(36)
        self.ok_btn.setMinimumWidth(100)
        self.ok_btn.clicked.connect(self._apply_and_accept)
        self.ok_btn.setObjectName("settingsOkBtn")
        button_layout.addWidget(self.ok_btn)

        return button_container

    def _populate_settings(self) -> None:
        """Build settings form from schema."""
        # Group 1: Model Options
        self._add_section_header("Model Settings")
        self._add_setting("model_options", "device")
        self._add_setting("model_options", "compute_type")
        self._add_setting("model_options", "language")

        # Group 2: Recording Options
        self._add_section_header("Recording")
        self._add_setting("recording_options", "activation_key")

        # Group 3: Output Options
        self._add_section_header("Output")
        self._add_setting("output_options", "add_trailing_space")

    def _add_section_header(self, title: str) -> None:
        """Add a visual section separator."""
        header = QLabel(title)
        header.setObjectName("settingsSectionHeader")
        self.form_layout.addRow(header)

    def _add_setting(self, section: str, key: str) -> None:
        """Add a single setting row to the form."""
        section_schema = self.schema.get(section, {})
        spec = section_schema.get(key)

        if not spec or spec.get("_internal", False):
            return

        widget = self._create_widget(section, key, spec)
        self.widgets[(section, key)] = widget

        label = QLabel(self._format_label(key))
        if desc := spec.get("description"):
            label.setToolTip(desc)
            widget.setToolTip(desc)

        # For checkboxes, wrap in container with center alignment to match label
        if isinstance(widget, QCheckBox):
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            layout.addWidget(widget)
            layout.addStretch()
            layout.setAlignment(widget, Qt.AlignmentFlag.AlignVCenter)
            self.form_layout.addRow(label, container)
        else:
            self.form_layout.addRow(label, widget)

    def _create_widget(self, section: str, key: str, spec: dict[str, Any]) -> QWidget:
        """Create appropriate widget for setting type."""
        value = ConfigManager.get_config_value(section, key)
        value_type = spec.get("type")
        options = spec.get("options")

        if section == "recording_options" and key == "activation_key":
            widget: QWidget = HotkeyWidget(self.key_listener, self)
            widget.set_hotkey(str(value))  # type: ignore[attr-defined]
            return widget

        if value_type == "bool":
            widget = QCheckBox()
            widget.setChecked(bool(value))
            return widget

        if options:
            if key == "compute_type":
                device = ConfigManager.get_config_value("model_options", "device")
                options = self._filter_compute_type_options(options, device)

            widget = QComboBox()
            widget.addItems(options)
            if value in options:
                widget.setCurrentText(str(value))
            return widget

        if value_type == "int":
            widget = QSpinBox()
            widget.setMinimum(spec.get("min", 0))
            widget.setMaximum(spec.get("max", 9999))
            widget.setSingleStep(spec.get("step", 1))
            widget.setValue(int(value))
            return widget

        if value_type == "float":
            widget = QDoubleSpinBox()
            widget.setMinimum(spec.get("min", 0.0))
            widget.setMaximum(spec.get("max", 9999.0))
            widget.setSingleStep(spec.get("step", 0.1))
            widget.setValue(float(value))
            return widget

        # Default: text input
        widget = QLineEdit()
        widget.setText(str(value))
        return widget

    def _filter_compute_type_options(
        self, options: list[str], device: str
    ) -> list[str]:
        """Filter compute_type options based on selected device."""
        match device:
            case "cpu":
                return [opt for opt in options if opt != "float16"]
            case "cuda":
                return [opt for opt in options if opt != "int8"]
            case _:
                return options

    def _format_label(self, key: str) -> str:
        """Convert snake_case to Title Case."""
        return key.replace("_", " ").title()

    def _apply_and_accept(self) -> None:
        """Apply changes and close dialog."""
        if self._apply_changes():
            self._cleanup_widgets()
            self.accept()

    def _apply_only(self) -> None:
        """Apply changes without closing."""
        self._apply_changes()

    def _on_reject(self) -> None:
        """Handle cancel button with cleanup."""
        self._cleanup_widgets()
        self.reject()

    def _cleanup_widgets(self) -> None:
        """Clean up widgets before closing dialog."""
        for widget in self.widgets.values():
            if isinstance(widget, HotkeyWidget):
                widget.cleanup()

    def closeEvent(self, event) -> None:
        """Override close event to ensure cleanup happens."""
        self._cleanup_widgets()
        super().closeEvent(event)

    def _apply_changes(self) -> bool:
        """Write widget values back to ConfigManager."""
        for (section, key), widget in self.widgets.items():
            new_value = self._read_widget_value(widget)
            current_value = ConfigManager.get_config_value(section, key)
            if new_value != current_value:
                ConfigManager.set_config_value(new_value, section, key)

        ConfigManager.save_config()
        return True

    def _read_widget_value(self, widget: QWidget) -> Any:
        """Extract value from widget."""
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QSpinBox):
            return int(widget.value())
        if isinstance(widget, QDoubleSpinBox):
            return float(widget.value())
        if isinstance(widget, QComboBox):
            return widget.currentText()
        if isinstance(widget, QLineEdit):
            return widget.text()
        if isinstance(widget, HotkeyWidget):
            return widget.get_hotkey()
        return None

    # Make dialog draggable via title bar
    def mousePressEvent(self, event):
        """Enable window dragging from title bar."""
        if event.button() == Qt.MouseButton.LeftButton:
            if event.position().y() < self.title_bar.height():
                self._drag_position = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
                event.accept()

    def mouseMoveEvent(self, event):
        """Handle window dragging."""
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(
            self, "_drag_position"
        ):
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()
