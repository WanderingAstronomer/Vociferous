"""
Settings View implementation.
The sole UI surface for mutating persistent configuration values.
"""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
    QFrame,
    QFormLayout,
    QComboBox,
    QCheckBox,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QPushButton,
    QHBoxLayout,
    QScrollArea,
)

from ui.views.base_view import BaseView
from ui.constants.view_ids import VIEW_SETTINGS
from ui.constants import Colors, Spacing, Typography
from ui.widgets.hotkey_widget import HotkeyWidget
from ui.widgets.dialogs import ConfirmationDialog, show_error_dialog
from utils import ConfigManager

if TYPE_CHECKING:
    from input_handler import KeyListener

logger = logging.getLogger(__name__)


def _has_gpu() -> bool:
    """Check if CUDA/GPU is available."""
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


class SettingsView(BaseView):
    """
    Settings view - the sole surface for configuration changes.
    
    Contains:
    - Model preferences (device, compute type, language)
    - Recording preferences (hotkey, mode, backend)
    - Refinement feature toggle
    - History controls (export, clear all)
    - Application controls (restart, exit)
    """
    
    # Signals for actions that require orchestrator involvement
    exportHistoryRequested = pyqtSignal()
    clearAllHistoryRequested = pyqtSignal()
    restartRequested = pyqtSignal()
    exitRequested = pyqtSignal()

    # Valid ISO-639-1 language codes for Whisper (same as SettingsDialog)
    VALID_LANGUAGES: set[str] = {
        "en", "zh", "de", "es", "ru", "ko", "fr", "ja", "pt", "tr", "pl", "ca",
        "nl", "ar", "sv", "it", "id", "hi", "fi", "vi", "he", "uk", "el", "ms",
        "cs", "ro", "da", "hu", "ta", "no", "th", "ur", "hr", "bg", "lt", "la",
        "mi", "ml", "cy", "sk", "te", "fa", "lv", "bn", "sr", "az", "sl", "kn",
        "et", "mk", "br", "eu", "is", "hy", "ne", "mn", "bs", "kk", "sq", "sw",
        "gl", "mr", "pa", "si", "km", "sn", "yo", "so", "af", "oc", "ka", "be",
        "tg", "sd", "gu", "am", "yi", "lo", "uz", "fo", "ht", "ps", "tk", "nn",
        "mt", "sa", "lb", "my", "bo", "tl", "mg", "as", "tt", "haw", "ln", "ha",
        "ba", "jw", "su",
    }

    def __init__(self, key_listener: KeyListener | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsView")
        self.key_listener = key_listener
        self.schema = ConfigManager.get_schema()
        self.widgets: dict[tuple[str, str], QWidget] = {}
        self._validation_labels: dict[tuple[str, str], QLabel] = {}
        self._validation_errors: dict[tuple[str, str], str] = {}
        self.has_gpu = _has_gpu()
        self._setup_ui()

    def get_view_id(self) -> str:
        return VIEW_SETTINGS
        
    def set_key_listener(self, key_listener: KeyListener) -> None:
        """Set key listener (for hotkey widget)."""
        self.key_listener = key_listener
        # Update hotkey widget if it exists
        hotkey_widget = self.widgets.get(("recording_options", "activation_key"))
        if isinstance(hotkey_widget, HotkeyWidget):
            hotkey_widget.key_listener = key_listener

    def _setup_ui(self) -> None:
        """Initialize the UI layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Title Bar
        title_bar = self._create_title_bar()
        main_layout.addWidget(title_bar)

        # Scrollable content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setObjectName("settingsScrollArea")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(Spacing.MAJOR_GAP, Spacing.MAJOR_GAP, Spacing.MAJOR_GAP, Spacing.MAJOR_GAP)
        content_layout.setSpacing(Spacing.MAJOR_GAP)

        # Settings Form
        self.form_layout = QFormLayout()
        self.form_layout.setSpacing(8)
        self.form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        
        self._populate_settings()
        content_layout.addLayout(self.form_layout)

        # Divider
        content_layout.addWidget(self._create_divider())

        # History Controls Section
        history_section = self._create_history_controls()
        content_layout.addWidget(history_section)

        # Divider
        content_layout.addWidget(self._create_divider())

        # Application Controls Section
        app_section = self._create_app_controls()
        content_layout.addWidget(app_section)

        content_layout.addStretch()

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area, 1)

        # Apply/Cancel buttons at bottom
        button_row = self._create_button_row()
        main_layout.addWidget(button_row)

    def _create_title_bar(self) -> QWidget:
        """Create title bar with label."""
        title_bar = QWidget()
        title_bar.setObjectName("viewTitleBar")
        title_bar.setFixedHeight(60)
        
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(Spacing.MAJOR_GAP, 0, Spacing.MAJOR_GAP, 0)
        
        title = QLabel("Settings")
        title.setObjectName("viewTitle")
        layout.addWidget(title)
        layout.addStretch()
        
        return title_bar

    def _create_divider(self) -> QFrame:
        """Create horizontal divider."""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setObjectName("settingsDivider")
        return line

    def _populate_settings(self) -> None:
        """Build settings form from schema."""
        # Model Options
        self._add_section_header("Model Settings")
        self._add_setting("model_options", "device")
        self._add_setting("model_options", "compute_type")
        self._add_setting("model_options", "language")

        # Recording Options
        self._add_section_header("Recording")
        self._add_setting("recording_options", "activation_key")

        # Output Options
        self._add_section_header("Output")
        self._add_setting("output_options", "add_trailing_space")

        # Refinement
        self._add_section_header("Grammar Refinement")
        self._add_setting("refinement", "enabled")

    def _add_section_header(self, title: str) -> None:
        """Add a visual section separator."""
        header = QLabel(title)
        header.setObjectName("settingsSectionHeader")
        header.setStyleSheet(f"font-weight: bold; font-size: {Typography.FONT_SIZE_LG}px; margin-top: 8px;")
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

        # Container with widget and validation
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(2)

        widget_row = QWidget()
        widget_row_layout = QHBoxLayout(widget_row)
        widget_row_layout.setContentsMargins(0, 0, 0, 0)

        if isinstance(widget, QCheckBox):
            widget_row_layout.addWidget(widget)
            widget_row_layout.addStretch()
        else:
            widget_row_layout.addWidget(widget, 1)

        container_layout.addWidget(widget_row)

        validation_label = QLabel()
        validation_label.setObjectName("settingsValidationLabel")
        validation_label.setWordWrap(True)
        validation_label.hide()
        container_layout.addWidget(validation_label)
        self._validation_labels[(section, key)] = validation_label

        self.form_layout.addRow(label, container)
        self._connect_validation_signals(section, key, widget)

    def _create_widget(self, section: str, key: str, spec: dict[str, Any]) -> QWidget:
        """Create appropriate widget for setting type."""
        value = ConfigManager.get_config_value(section, key)
        value_type = spec.get("type")
        options = spec.get("options")

        if section == "recording_options" and key == "activation_key":
            widget: QWidget = HotkeyWidget(self.key_listener, self)
            widget.set_hotkey(str(value))
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

        widget = QLineEdit()
        widget.setText(str(value))
        return widget

    def _filter_compute_type_options(self, options: list[str], device: str) -> list[str]:
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

    def _connect_validation_signals(self, section: str, key: str, widget: QWidget) -> None:
        """Connect widget value change signals to validation."""
        if isinstance(widget, QComboBox):
            widget.currentTextChanged.connect(lambda _: self._validate_all())
        elif isinstance(widget, QLineEdit):
            widget.textChanged.connect(lambda _: self._validate_all())
        elif isinstance(widget, QSpinBox):
            widget.valueChanged.connect(lambda _: self._validate_all())
        elif isinstance(widget, QDoubleSpinBox):
            widget.valueChanged.connect(lambda _: self._validate_all())
        elif isinstance(widget, QCheckBox):
            widget.stateChanged.connect(lambda _: self._validate_all())
        elif isinstance(widget, HotkeyWidget):
            widget.hotkeyChanged.connect(lambda _: self._validate_all())

    def _validate_all(self) -> bool:
        """Validate all settings and update UI. Returns True if valid."""
        self._validation_errors.clear()
        self._validate_device_compute_type()
        self._validate_language()
        self._validate_hotkey()
        self._update_validation_labels()
        
        has_errors = bool(self._validation_errors)
        if hasattr(self, 'apply_btn'):
            self.apply_btn.setEnabled(not has_errors)
        return not has_errors

    def _validate_device_compute_type(self) -> None:
        """Validate device and compute_type are compatible."""
        device_widget = self.widgets.get(("model_options", "device"))
        compute_widget = self.widgets.get(("model_options", "compute_type"))

        if not device_widget or not compute_widget:
            return

        device = device_widget.currentText() if isinstance(device_widget, QComboBox) else "auto"
        compute_type = compute_widget.currentText() if isinstance(compute_widget, QComboBox) else "float32"

        actual_device = device if device != "auto" else ("cuda" if self.has_gpu else "cpu")

        if actual_device == "cpu" and compute_type == "float16":
            self._validation_errors[("model_options", "compute_type")] = \
                "float16 is not supported on CPU. Use float32 or int8."

        if actual_device == "cuda" and compute_type == "int8":
            self._validation_errors[("model_options", "compute_type")] = \
                "int8 is not supported on CUDA. Use float16 or float32."

    def _validate_language(self) -> None:
        """Validate language code is valid."""
        lang_widget = self.widgets.get(("model_options", "language"))
        if not lang_widget:
            return

        language = ""
        if isinstance(lang_widget, QComboBox):
            language = lang_widget.currentText().strip().lower()
        elif isinstance(lang_widget, QLineEdit):
            language = lang_widget.text().strip().lower()

        if language and language not in self.VALID_LANGUAGES:
            self._validation_errors[("model_options", "language")] = \
                f"'{language}' is not a valid ISO-639-1 language code."

    def _validate_hotkey(self) -> None:
        """Validate hotkey is set."""
        hotkey_widget = self.widgets.get(("recording_options", "activation_key"))
        if not hotkey_widget:
            return

        if isinstance(hotkey_widget, HotkeyWidget):
            hotkey = hotkey_widget.get_hotkey()
            if not hotkey or hotkey.strip() == "":
                self._validation_errors[("recording_options", "activation_key")] = \
                    "Activation key is required."

    def _update_validation_labels(self) -> None:
        """Update validation label visibility and text."""
        for (section, key), label in self._validation_labels.items():
            error = self._validation_errors.get((section, key))
            widget = self.widgets.get((section, key))

            if error:
                label.setText(f"⚠ {error}")
                label.setStyleSheet(
                    f"color: {Colors.DESTRUCTIVE}; font-size: {Typography.FONT_SIZE_XS}px;"
                )
                label.show()
                if widget:
                    widget.setProperty("validation", "error")
                    widget.style().polish(widget)
            else:
                label.hide()
                label.setText("")
                if widget:
                    widget.setProperty("validation", "")
                    widget.style().polish(widget)

    def _create_history_controls(self) -> QWidget:
        """Create history control section."""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.MINOR_GAP)

        header = QLabel("History Management")
        header.setObjectName("settingsSectionHeader")
        header.setStyleSheet(f"font-weight: bold; font-size: {Typography.FONT_SIZE_LG}px;")
        layout.addWidget(header)

        # Export button
        export_btn = QPushButton("Export History...")
        export_btn.clicked.connect(self.exportHistoryRequested.emit)
        export_btn.setFixedHeight(36)
        layout.addWidget(export_btn)

        # Clear all button with warning
        clear_container = QWidget()
        clear_layout = QVBoxLayout(clear_container)
        clear_layout.setContentsMargins(0, 0, 0, 0)
        clear_layout.setSpacing(4)

        warning = QLabel("⚠ Clearing history is permanent and cannot be undone.")
        warning.setObjectName("warningLabel")
        warning.setStyleSheet(f"color: {Colors.DESTRUCTIVE}; font-size: {Typography.FONT_SIZE_SM}px;")
        warning.setWordWrap(True)
        clear_layout.addWidget(warning)

        clear_btn = QPushButton("Clear All History...")
        clear_btn.clicked.connect(self._on_clear_all_history)
        clear_btn.setObjectName("destructiveButton")
        clear_btn.setFixedHeight(36)
        clear_layout.addWidget(clear_btn)

        layout.addWidget(clear_container)

        return section

    def _create_app_controls(self) -> QWidget:
        """Create application control section."""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.MINOR_GAP)

        header = QLabel("Application")
        header.setObjectName("settingsSectionHeader")
        header.setStyleSheet(f"font-weight: bold; font-size: {Typography.FONT_SIZE_LG}px;")
        layout.addWidget(header)

        # Restart button
        restart_btn = QPushButton("Restart Application")
        restart_btn.clicked.connect(self.restartRequested.emit)
        restart_btn.setFixedHeight(36)
        layout.addWidget(restart_btn)

        # Exit button
        exit_btn = QPushButton("Exit Application")
        exit_btn.clicked.connect(self.exitRequested.emit)
        exit_btn.setFixedHeight(36)
        layout.addWidget(exit_btn)

        return section

    def _create_button_row(self) -> QWidget:
        """Create Apply/Cancel button row."""
        button_container = QWidget()
        button_container.setObjectName("settingsButtonContainer")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(Spacing.MAJOR_GAP, 12, Spacing.MAJOR_GAP, 12)
        button_layout.setSpacing(Spacing.MINOR_GAP)
        button_layout.addStretch()

        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(self._on_cancel)
        button_layout.addWidget(cancel_btn)

        # Apply button
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setFixedHeight(36)
        self.apply_btn.setMinimumWidth(100)
        self.apply_btn.clicked.connect(self._on_apply)
        button_layout.addWidget(self.apply_btn)

        return button_container

    def _on_apply(self) -> None:
        """Apply settings changes."""
        if not self._validate_all():
            logger.warning("Settings validation failed")
            return

        try:
            for (section, key), widget in self.widgets.items():
                new_value = self._read_widget_value(widget)
                current_value = ConfigManager.get_config_value(section, key)
                if new_value != current_value:
                    ConfigManager.set_config_value(new_value, section, key)

            ConfigManager.save_config()
            logger.info("Settings applied successfully")
        except Exception as e:
            logger.exception("Failed to apply settings")
            show_error_dialog("Settings Error", "Failed to save settings.", str(e), parent=self)

    def _on_cancel(self) -> None:
        """Cancel changes and reload from config."""
        # Reload widgets from ConfigManager
        for (section, key), widget in self.widgets.items():
            value = ConfigManager.get_config_value(section, key)
            self._set_widget_value(widget, value)
        self._validate_all()

    def _on_clear_all_history(self) -> None:
        """Show confirmation dialog before clearing history."""
        dialog = ConfirmationDialog(
            title="Clear All History",
            message="Are you sure you want to clear all transcription history?",
            detail="This action cannot be undone. All transcripts will be permanently deleted.",
            parent=self
        )
        if dialog.exec() == ConfirmationDialog.DialogCode.Accepted:
            self.clearAllHistoryRequested.emit()

    def _read_widget_value(self, widget: QWidget) -> Any:
        """Extract value from widget."""
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QSpinBox):
            return widget.value()
        if isinstance(widget, QDoubleSpinBox):
            return widget.value()
        if isinstance(widget, QComboBox):
            return widget.currentText()
        if isinstance(widget, QLineEdit):
            return widget.text()
        if isinstance(widget, HotkeyWidget):
            return widget.get_hotkey()
        return None

    def _set_widget_value(self, widget: QWidget, value: Any) -> None:
        """Set widget value."""
        if isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QSpinBox):
            widget.setValue(int(value))
        elif isinstance(widget, QDoubleSpinBox):
            widget.setValue(float(value))
        elif isinstance(widget, QComboBox):
            widget.setCurrentText(str(value))
        elif isinstance(widget, QLineEdit):
            widget.setText(str(value))
        elif isinstance(widget, HotkeyWidget):
            widget.set_hotkey(str(value))

    def cleanup(self) -> None:
        """Clean up resources."""
        for widget in self.widgets.values():
            if isinstance(widget, HotkeyWidget):
                widget.cleanup()
        super().cleanup()

