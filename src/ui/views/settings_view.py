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
    QComboBox,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QPushButton,
    QHBoxLayout,
    QScrollArea,
)

from src.ui.views.base_view import BaseView
from src.ui.constants.view_ids import VIEW_SETTINGS
import src.ui.constants.colors as c
from src.ui.constants import Spacing, Typography
from src.ui.contracts.capabilities import Capabilities, SelectionState, ActionId
from src.ui.widgets.hotkey_widget import HotkeyWidget
from src.ui.widgets.slider_field import SliderField
from src.ui.widgets.toggle_switch import ToggleSwitch
from src.ui.widgets.dialogs import ConfirmationDialog, show_error_dialog
from src.ui.styles.settings_view_styles import get_settings_view_stylesheet
from src.core.config_manager import ConfigManager
from src.core.model_registry import ASR_MODELS
from src.services.slm_service import SLMState, SLMService

if TYPE_CHECKING:
    from src.input_handler import KeyListener

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
    export_history_requested = pyqtSignal()
    clear_all_history_requested = pyqtSignal()
    restart_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    # Valid ISO-639-1 language codes for Whisper (same as SettingsDialog)
    VALID_LANGUAGES: set[str] = {
        "en",
        "zh",
        "de",
        "es",
        "ru",
        "ko",
        "fr",
        "ja",
        "pt",
        "tr",
        "pl",
        "ca",
        "nl",
        "ar",
        "sv",
        "it",
        "id",
        "hi",
        "fi",
        "vi",
        "he",
        "uk",
        "el",
        "ms",
        "cs",
        "ro",
        "da",
        "hu",
        "ta",
        "no",
        "th",
        "ur",
        "hr",
        "bg",
        "lt",
        "la",
        "mi",
        "ml",
        "cy",
        "sk",
        "te",
        "fa",
        "lv",
        "bn",
        "sr",
        "az",
        "sl",
        "kn",
        "et",
        "mk",
        "br",
        "eu",
        "is",
        "hy",
        "ne",
        "mn",
        "bs",
        "kk",
        "sq",
        "sw",
        "gl",
        "mr",
        "pa",
        "si",
        "km",
        "sn",
        "yo",
        "so",
        "af",
        "oc",
        "ka",
        "be",
        "tg",
        "sd",
        "gu",
        "am",
        "yi",
        "lo",
        "uz",
        "fo",
        "ht",
        "ps",
        "tk",
        "nn",
        "mt",
        "sa",
        "lb",
        "my",
        "bo",
        "tl",
        "mg",
        "as",
        "tt",
        "haw",
        "ln",
        "ha",
        "ba",
        "jw",
        "su",
    }

    def __init__(
        self, key_listener: KeyListener | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsView")
        self.key_listener = key_listener
        self.schema = ConfigManager.get_schema()
        self.widgets: dict[tuple[str, str], QWidget] = {}
        self._validation_labels: dict[tuple[str, str], QLabel] = {}
        self._validation_errors: dict[tuple[str, str], str] = {}
        self.has_gpu = _has_gpu()
        self._setup_ui()

        # Apply view-specific stylesheet
        self.setStyleSheet(get_settings_view_stylesheet())

        # Listen for config changes to refresh view state
        self._config_manager = ConfigManager.instance()
        self._config_manager.config_changed.connect(self._on_config_changed)

    def get_view_id(self) -> str:
        return VIEW_SETTINGS

    def get_capabilities(self) -> Capabilities:
        """Settings view has no action capabilities (configuration-only)."""
        return Capabilities()

    def get_selection(self) -> SelectionState:
        """Settings view has no selection."""
        return SelectionState()

    def dispatch_action(self, action_id: ActionId) -> None:
        """Settings view does not handle standard actions."""
        pass

    def set_key_listener(self, key_listener: KeyListener) -> None:
        """Set key listener (for hotkey widget)."""
        self.key_listener = key_listener
        # Update hotkey widget if it exists
        hotkey_widget = self.widgets.get(("recording_options", "activation_key"))
        if isinstance(hotkey_widget, HotkeyWidget):
            hotkey_widget.key_listener = key_listener

    def _setup_ui(self) -> None:
        """Initialize the UI layout with fixed widths and centered content."""
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
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Centered container with min/max width for responsiveness
        center_container = QWidget()
        center_container.setMinimumWidth(800)
        center_container.setMaximumWidth(1200)
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(
            Spacing.MAJOR_GAP,
            Spacing.MAJOR_GAP * 2,
            Spacing.MAJOR_GAP,
            Spacing.MAJOR_GAP * 2,
        )
        center_layout.setSpacing(Spacing.MAJOR_GAP * 2)

        # Settings sections
        self._populate_settings(center_layout)

        # Divider
        center_layout.addSpacing(Spacing.MAJOR_GAP * 2)
        center_layout.addWidget(self._create_divider())
        center_layout.addSpacing(Spacing.MAJOR_GAP * 2)

        # History Controls Section
        history_section = self._create_history_controls()
        center_layout.addWidget(history_section)

        # Divider
        center_layout.addSpacing(Spacing.MAJOR_GAP * 2)
        center_layout.addWidget(self._create_divider())
        center_layout.addSpacing(Spacing.MAJOR_GAP * 2)

        # Application Controls Section
        app_section = self._create_app_controls()
        center_layout.addWidget(app_section)

        # Add centered container to content layout
        h_layout = QHBoxLayout()
        h_layout.addStretch()
        h_layout.addWidget(center_container)
        h_layout.addStretch()
        content_layout.addLayout(h_layout)
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
        title_bar.setFixedHeight(80)  # Increased height for larger title

        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(Spacing.MAJOR_GAP, 0, Spacing.MAJOR_GAP, 0)

        title = QLabel("Settings")
        title.setObjectName("viewTitle")
        # Override to ensure it's largest and centered
        title.setStyleSheet(
            f"font-size: {Typography.FONT_SIZE_XXL}px; font-weight: bold; color: {c.BLUE_4};"
        )
        layout.addWidget(title, 0, Qt.AlignmentFlag.AlignCenter)

        return title_bar

    def _create_divider(self) -> QFrame:
        """Create horizontal divider."""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setObjectName("settingsDivider")
        return line

    def _populate_settings(self, layout: QVBoxLayout) -> None:
        """Build settings sections with consistent card-based form layout."""

        # Whisper ASR Settings Section
        model_card, model_content = self._create_settings_card("Whisper ASR Settings")

        # Whisper Model Selection
        model_widget = self._create_widget(
            "model_options", "model", self.schema["model_options"]["model"]
        )
        if isinstance(model_widget, QComboBox):
            model_widget.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToContents
            )
            model_widget.setMinimumWidth(300)
        self.widgets[("model_options", "model")] = model_widget
        model_content.addLayout(
            self._create_form_row("Whisper Architecture", model_widget)
        )

        # Device
        device_widget = self._create_widget(
            "model_options", "device", self.schema["model_options"]["device"]
        )
        device_widget.setFixedWidth(200)
        self.widgets[("model_options", "device")] = device_widget
        self._connect_validation_signals("model_options", "device", device_widget)
        model_content.addLayout(self._create_form_row("Device", device_widget))

        # Compute Type
        compute_widget = self._create_widget(
            "model_options",
            "compute_type",
            self.schema["model_options"]["compute_type"],
        )
        compute_widget.setFixedWidth(200)
        self.widgets[("model_options", "compute_type")] = compute_widget
        self._connect_validation_signals(
            "model_options", "compute_type", compute_widget
        )
        model_content.addLayout(self._create_form_row("Compute Type", compute_widget))

        # Language
        lang_widget = QLineEdit()
        lang_widget.setObjectName("languageField")
        lang_value = ConfigManager.get_config_value("model_options", "language")
        lang_widget.setText(str(lang_value))
        lang_widget.setFixedWidth(120)
        self.widgets[("model_options", "language")] = lang_widget
        self._connect_validation_signals("model_options", "language", lang_widget)
        model_content.addLayout(self._create_form_row("Language", lang_widget))

        layout.addWidget(model_card)
        layout.addSpacing(Spacing.MAJOR_GAP * 2)
        layout.addWidget(self._create_divider())
        layout.addSpacing(Spacing.MAJOR_GAP * 2)

        # Recording Section
        recording_card, recording_content = self._create_settings_card("Recording")

        # Activation Key
        hotkey_widget = HotkeyWidget(self.key_listener, self)
        hotkey_value = ConfigManager.get_config_value(
            "recording_options", "activation_key"
        )
        hotkey_widget.set_hotkey(str(hotkey_value))
        self.widgets[("recording_options", "activation_key")] = hotkey_widget
        self._connect_validation_signals(
            "recording_options", "activation_key", hotkey_widget
        )
        recording_content.addLayout(
            self._create_form_row("Activation Key", hotkey_widget)
        )

        # Recording Mode
        mode_widget = self._create_widget(
            "recording_options",
            "recording_mode",
            self.schema["recording_options"]["recording_mode"],
        )
        mode_widget.setFixedWidth(200)
        self.widgets[("recording_options", "recording_mode")] = mode_widget
        self._connect_validation_signals(
            "recording_options", "recording_mode", mode_widget
        )
        recording_content.addLayout(
            self._create_form_row(
                "Recording Mode",
                mode_widget,
                help_text="Toggle: Press once to start, again to stop. Talk: Hold to record, release to stop.",
            )
        )

        layout.addWidget(recording_card)
        layout.addSpacing(Spacing.MAJOR_GAP * 2)
        layout.addWidget(self._create_divider())
        layout.addSpacing(Spacing.MAJOR_GAP * 2)

        # Visualization Section
        vis_card, vis_content = self._create_settings_card("Visualization")

        visualizer_widget = self._create_widget(
            "visualization",
            "visualizer_type",
            self.schema["visualization"]["visualizer_type"],
        )
        visualizer_widget.setFixedWidth(200)
        self.widgets[("visualization", "visualizer_type")] = visualizer_widget
        self._connect_validation_signals(
            "visualization", "visualizer_type", visualizer_widget
        )
        vis_content.addLayout(self._create_form_row("Spectrum Type", visualizer_widget))

        layout.addWidget(vis_card)
        layout.addSpacing(Spacing.MAJOR_GAP * 2)
        layout.addWidget(self._create_divider())
        layout.addSpacing(Spacing.MAJOR_GAP * 2)

        # Output & Processing Section
        output_card, output_content = self._create_settings_card("Output & Processing")

        # Add Trailing Space
        trailing_toggle = ToggleSwitch()
        trailing_value = ConfigManager.get_config_value(
            "output_options", "add_trailing_space"
        )
        trailing_toggle.setChecked(bool(trailing_value))
        self.widgets[("output_options", "add_trailing_space")] = trailing_toggle
        self._connect_validation_signals(
            "output_options", "add_trailing_space", trailing_toggle
        )
        output_content.addLayout(
            self._create_form_row("Add Trailing Space", trailing_toggle)
        )

        # Grammar Refinement
        refinement_toggle = ToggleSwitch()
        refinement_value = ConfigManager.get_config_value("refinement", "enabled")
        refinement_toggle.setChecked(bool(refinement_value))
        self.widgets[("refinement", "enabled")] = refinement_toggle
        self._connect_validation_signals("refinement", "enabled", refinement_toggle)
        output_content.addLayout(
            self._create_form_row("Grammar Refinement", refinement_toggle)
        )

        # Refinement Model Selection (conditionally visible)
        model_select = QComboBox()
        model_select.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        model_select.setMinimumWidth(280)

        # Populate models
        sorted_models = sorted(
            SLMService.get_supported_models(), key=lambda x: x.required_vram_mb
        )
        for model in sorted_models:
            model_select.addItem(model.name, model.id)

        current_model_id = (
            ConfigManager.get_config_value("refinement", "model_id") or "qwen4b"
        )
        idx = model_select.findData(current_model_id)
        if idx >= 0:
            model_select.setCurrentIndex(idx)
        else:
            model_select.setCurrentIndex(0)

        self.widgets[("refinement", "model_id")] = model_select
        self._connect_validation_signals("refinement", "model_id", model_select)

        # Model selector row
        self._refinement_model_row = self._create_form_row(
            "Refinement Model", model_select
        )
        output_content.addLayout(self._refinement_model_row)

        # Status Label on its own row (placed in the left label column)
        self.refinement_status_label = QLabel("")
        self.refinement_status_label.setStyleSheet(
            f"color: {c.BLUE_4}; font-style: italic;"
        )
        self.refinement_status_label.setWordWrap(True)
        # Place status in a row that occupies the left label column area
        status_row = QHBoxLayout()
        status_row.setSpacing(Spacing.MINOR_GAP)
        status_row.addStretch()
        self.refinement_status_label.setMinimumWidth(200)
        self.refinement_status_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter
        )
        status_row.addWidget(self.refinement_status_label)
        status_row.addStretch()
        output_content.addLayout(status_row)

        # Store references for visibility control
        self._refinement_model_select = model_select
        self._refinement_status_label = self.refinement_status_label

        # Connect toggle to update visibility
        refinement_toggle.toggled.connect(self._update_refinement_visibility)

        # Set initial visibility
        self._update_refinement_visibility(refinement_toggle.isChecked())

        layout.addWidget(output_card)
        layout.addSpacing(Spacing.MAJOR_GAP)

    def _update_refinement_visibility(self, enabled: bool) -> None:
        """Show or hide refinement model selector and status based on toggle."""
        # Hide/show the model selector form row
        for i in range(self._refinement_model_row.count()):
            widget = self._refinement_model_row.itemAt(i).widget()
            if widget:
                widget.setVisible(enabled)
            layout = self._refinement_model_row.itemAt(i).layout()
            if layout:
                for j in range(layout.count()):
                    sub_widget = layout.itemAt(j).widget()
                    if sub_widget:
                        sub_widget.setVisible(enabled)

        # Hide/show the status label
        self.refinement_status_label.setVisible(enabled)

    def update_refinement_state(self, state: SLMState) -> None:
        """Handle state updates from SLM Service."""

        # Map state to friendly text
        status_text = ""
        is_busy = False

        match state:
            case SLMState.DISABLED:
                status_text = ""
            case SLMState.CHECKING_RESOURCES:
                status_text = "Checking system..."
                is_busy = True
            case SLMState.WAITING_FOR_USER:
                status_text = "Action required (see notification)"
            case SLMState.DOWNLOADING_SOURCE:
                status_text = "Downloading model..."
                is_busy = True
            case SLMState.CONVERTING_MODEL:
                status_text = "Optimizing model..."
                is_busy = True
            case SLMState.LOADING:
                status_text = "Loading engine..."
                is_busy = True
            case SLMState.READY:
                status_text = "Available"
            case SLMState.INFERRING:
                status_text = "Active"
            case SLMState.ERROR:
                status_text = "Error (see logs)"
            case _:
                status_text = str(state.value)

        self.refinement_status_label.setText(status_text)

        # Disable Apply button if busy/downloading to prevent inconsistent state
        # But wait, Apply button is general. user might want to change other things.
        # Ideally we only disable "Refinement" toggle or Model Select?
        # But user requirement says: "disable Apply while downloading".
        self.apply_btn.setEnabled(not is_busy)
        if is_busy:
            self.apply_btn.setText("Processing...")
        else:
            self.apply_btn.setText("Apply")

    def update_refinement_status(self, message: str) -> None:
        """Handle transient detailed messages."""
        # e.g. "Downloading: 45%"
        self.refinement_status_label.setText(message)

    def _on_config_changed(self, section: str, key: str, value) -> None:
        """Handle configuration changes to refresh view state."""
        # When refinement is toggled and applied, refresh the view
        if section == "refinement" and key == "enabled":
            # Update widget to reflect saved state
            widget = self.widgets.get(("refinement", "enabled"))
            if widget and isinstance(widget, ToggleSwitch):
                # Block signals to prevent triggering validation during programmatic update
                widget.blockSignals(True)
                widget.setChecked(bool(value))
                widget.blockSignals(False)
                # Update visibility of refinement model selector
                self._update_refinement_visibility(bool(value))

    def showEvent(self, event) -> None:
        """Refresh settings when view is shown."""
        super().showEvent(event)
        self.refresh_widgets()

    def refresh_widgets(self) -> None:
        """Refresh all widgets to match current configuration."""
        for (section, key), widget in self.widgets.items():
            value = ConfigManager.get_config_value(section, key)
            if value is not None:
                widget.blockSignals(True)
                self._set_widget_value(widget, value)
                widget.blockSignals(False)

        # Ensure refinement visibility is updated
        refine_enabled = ConfigManager.get_config_value("refinement", "enabled")
        self._update_refinement_visibility(bool(refine_enabled))

        # Clear any validation errors
        self._validation_errors.clear()
        self._update_validation_labels()

    def _populate_bar_spectrum(self, layout: QVBoxLayout) -> None:
        """Populate Bar Spectrum settings section."""
        # Bar Spectrum Section
        spectrum_section = self._create_settings_section("Bar Spectrum")

        spectrum_row = QHBoxLayout()
        spectrum_row.setSpacing(Spacing.MINOR_GAP)
        spectrum_row.addStretch()

        gate_label = QLabel("Gate Aggression")
        gate_widget = SliderField(
            minimum=0.0,
            maximum=0.5,
            step=0.05,
            initial=float(
                ConfigManager.get_config_value("bar_spectrum", "gate_aggression") or 0.0
            ),
            is_float=True,
        )
        self.widgets[("bar_spectrum", "gate_aggression")] = gate_widget
        self._connect_validation_signals("bar_spectrum", "gate_aggression", gate_widget)

        spectrum_row.addWidget(gate_label)
        spectrum_row.addWidget(gate_widget)

        spectrum_row.addStretch()
        spectrum_section.addLayout(spectrum_row)

        layout.addWidget(self._wrap_in_container(spectrum_section))

    def _create_settings_card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        """Create a settings card container with header and layout.

        Returns:
            tuple of (card_frame, content_layout) where content_layout is where
            you add settings rows.
        """
        card = QFrame()
        card.setObjectName("settingsCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)

        # Allow card to expand horizontally to fill available width
        from PyQt6.QtWidgets import QSizePolicy

        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        main_layout = QVBoxLayout(card)
        main_layout.setContentsMargins(
            Spacing.MAJOR_GAP * 2,
            Spacing.MAJOR_GAP,
            Spacing.MAJOR_GAP * 2,
            Spacing.MAJOR_GAP,
        )
        main_layout.setSpacing(Spacing.MAJOR_GAP)

        # Header
        header = QLabel(title)
        header.setObjectName("settingsSectionHeader")
        header.setStyleSheet(
            f"font-weight: bold; font-size: {Typography.FONT_SIZE_XL}px; "
            f"color: {c.BLUE_4}; margin-bottom: 8px;"
        )
        main_layout.addWidget(header, 0, Qt.AlignmentFlag.AlignCenter)

        # Content layout (where settings rows go)
        content_layout = QVBoxLayout()
        content_layout.setSpacing(Spacing.MAJOR_GAP)
        main_layout.addLayout(content_layout)

        return card, content_layout

    def _create_form_row(
        self, label_text: str, widget: QWidget, help_text: str | None = None
    ) -> QHBoxLayout:
        """Create a form row with label | control pattern.

        Args:
            label_text: The label for the control
            widget: The control widget
            help_text: Optional help text below the control

        Returns:
            QHBoxLayout containing the row
        """
        row = QHBoxLayout()
        row.setSpacing(Spacing.MAJOR_GAP)

        # Label (minimum width for alignment, allows text to render fully)
        label = QLabel(label_text)
        label.setMinimumWidth(200)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(label)

        # Widget container (supports help text to the right)
        if help_text:
            # Horizontal layout: control | help text
            widget_container = QHBoxLayout()
            widget_container.setSpacing(Spacing.MAJOR_GAP)
            widget_container.addWidget(widget)

            help_label = QLabel(help_text)
            help_label.setStyleSheet(
                f"color: {c.TEXT_SECONDARY}; font-size: {Typography.FONT_SIZE_SM}px; "
                f"font-style: italic;"
            )
            help_label.setWordWrap(True)
            help_label.setMaximumWidth(500)  # Limit width for readability
            widget_container.addWidget(help_label)
        else:
            # Vertical layout: just the control
            widget_container = QVBoxLayout()
            widget_container.setSpacing(Spacing.MINOR_GAP // 2)
            widget_container.addWidget(widget)

        row.addLayout(widget_container)
        row.addStretch()

        return row

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
            # Use toggle switch instead of checkbox
            widget = ToggleSwitch()
            widget.setChecked(bool(value))
            return widget

        if options:
            if key == "compute_type":
                device = ConfigManager.get_config_value("model_options", "device")
                options = self._filter_compute_type_options(options, device)

            widget = QComboBox()

            # Custom handling for Whisper model selector to show VRAM
            if section == "model_options" and key == "model":
                for model_id in options:
                    model_meta = ASR_MODELS.get(model_id)
                    if model_meta:
                        vram_gb = model_meta.required_vram_mb / 1024
                        label = f"{model_meta.name} (~{vram_gb:.1f} GB VRAM)"
                        widget.addItem(label, model_id)
                    else:
                        widget.addItem(model_id, model_id)

                idx = widget.findData(value)
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            elif section == "recording_options" and key == "recording_mode":
                # Special mapping for recording mode display names
                display_map = {
                    "press_to_toggle": "Toggle",
                    "push_to_talk": "Talk",
                }
                for opt in options:
                    display_text = display_map.get(opt, opt.replace("_", " ").title())
                    widget.addItem(display_text, opt)

                idx = widget.findData(value)
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            else:
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

        if value_type == "float_slider":
            minimum = float(spec.get("min", 0.0))
            maximum = float(spec.get("max", 1.0))
            step = float(spec.get("step", 0.05))
            widget = SliderField(minimum, maximum, step, float(value), is_float=True)
            return widget

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

    def _connect_validation_signals(
        self, section: str, key: str, widget: QWidget
    ) -> None:
        """Connect widget value change signals to validation."""
        if isinstance(widget, QComboBox):
            widget.currentTextChanged.connect(lambda _: self._validate_all())
        elif isinstance(widget, QLineEdit):
            widget.textChanged.connect(lambda _: self._validate_all())
        elif isinstance(widget, QSpinBox):
            widget.valueChanged.connect(lambda _: self._validate_all())
        elif isinstance(widget, QDoubleSpinBox):
            widget.valueChanged.connect(lambda _: self._validate_all())
        elif isinstance(widget, SliderField):
            widget.valueChanged.connect(lambda _: self._validate_all())
        elif isinstance(widget, ToggleSwitch):
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
        if hasattr(self, "apply_btn"):
            self.apply_btn.setEnabled(not has_errors)
        return not has_errors

    def _validate_device_compute_type(self) -> None:
        """Validate device and compute_type are compatible."""
        device_widget = self.widgets.get(("model_options", "device"))
        compute_widget = self.widgets.get(("model_options", "compute_type"))

        if not device_widget or not compute_widget:
            return

        device = (
            device_widget.currentText()
            if isinstance(device_widget, QComboBox)
            else "auto"
        )
        compute_type = (
            compute_widget.currentText()
            if isinstance(compute_widget, QComboBox)
            else "float32"
        )

        actual_device = (
            device if device != "auto" else ("cuda" if self.has_gpu else "cpu")
        )

        if actual_device == "cpu" and compute_type == "float16":
            self._validation_errors[("model_options", "compute_type")] = (
                "float16 is not supported on CPU. Use float32 or int8."
            )

        if actual_device == "cuda" and compute_type == "int8":
            self._validation_errors[("model_options", "compute_type")] = (
                "int8 is not supported on CUDA. Use float16 or float32."
            )

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
            self._validation_errors[("model_options", "language")] = (
                f"'{language}' is not a valid ISO-639-1 language code."
            )

    def _validate_hotkey(self) -> None:
        """Validate hotkey is set."""
        hotkey_widget = self.widgets.get(("recording_options", "activation_key"))
        if not hotkey_widget:
            return

        if isinstance(hotkey_widget, HotkeyWidget):
            hotkey = hotkey_widget.get_hotkey()
            if not hotkey or hotkey.strip() == "":
                self._validation_errors[("recording_options", "activation_key")] = (
                    "Activation key is required."
                )

    def _update_validation_labels(self) -> None:
        """Update validation label visibility and text."""
        for (section, key), label in self._validation_labels.items():
            error = self._validation_errors.get((section, key))
            widget = self.widgets.get((section, key))

            if error:
                label.setText(f"⚠ {error}")
                label.setStyleSheet(
                    f"color: {c.RED_5}; font-size: {Typography.FONT_SIZE_XS}px;"
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
        """Create history control section with modern card-like layout."""
        section = QFrame()
        section.setObjectName("settingsCard")
        section.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(section)
        layout.setContentsMargins(
            Spacing.MAJOR_GAP, Spacing.MAJOR_GAP, Spacing.MAJOR_GAP, Spacing.MAJOR_GAP
        )
        layout.setSpacing(Spacing.MINOR_GAP)

        header = QLabel("History Management")
        header.setObjectName("settingsSectionHeader")
        header.setStyleSheet(
            f"font-weight: bold; font-size: {Typography.FONT_SIZE_LG}px; "
            f"color: {c.GRAY_4};"
        )
        layout.addWidget(header, 0, Qt.AlignmentFlag.AlignCenter)

        # Button row
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 12, 0, 0)
        btn_layout.setSpacing(Spacing.MAJOR_GAP)

        btn_layout.addStretch()

        # Export button
        export_btn = QPushButton("Export History...")
        export_btn.setObjectName("secondaryButton")
        export_btn.clicked.connect(self.export_history_requested.emit)
        export_btn.setFixedHeight(40)
        export_btn.setMinimumWidth(160)
        btn_layout.addWidget(export_btn)

        # Clear all button
        clear_btn = QPushButton("Clear All History...")
        clear_btn.clicked.connect(self._on_clear_all_history)
        clear_btn.setObjectName("destructiveButton")
        clear_btn.setFixedHeight(40)
        clear_btn.setMinimumWidth(160)
        btn_layout.addWidget(clear_btn)

        btn_layout.addStretch()

        layout.addWidget(btn_container)

        # Warning label
        warning = QLabel("⚠ Clearing history is permanent and cannot be undone.")
        warning.setObjectName("warningLabel")
        warning.setStyleSheet(
            f"color: {c.RED_5}; font-size: {Typography.FONT_SIZE_SM}px; "
            f"margin-top: 8px; font-style: italic;"
        )
        warning.setWordWrap(False)
        layout.addWidget(warning, 0, Qt.AlignmentFlag.AlignCenter)

        return section

    def _create_app_controls(self) -> QWidget:
        """Create application control section with modern card-like layout."""
        section = QFrame()
        section.setObjectName("settingsCard")
        section.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(section)
        layout.setContentsMargins(
            Spacing.MAJOR_GAP, Spacing.MAJOR_GAP, Spacing.MAJOR_GAP, Spacing.MAJOR_GAP
        )
        layout.setSpacing(Spacing.MINOR_GAP)

        header = QLabel("Application")
        header.setObjectName("settingsSectionHeader")
        header.setStyleSheet(
            f"font-weight: bold; font-size: {Typography.FONT_SIZE_LG}px; "
            f"color: {c.GRAY_4};"
        )
        layout.addWidget(header, 0, Qt.AlignmentFlag.AlignCenter)

        # Button row
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 8, 0, 0)
        btn_layout.setSpacing(Spacing.MINOR_GAP)

        btn_layout.addStretch()

        # Restart button
        restart_btn = QPushButton("Restart Application")
        restart_btn.setObjectName("secondaryButton")
        restart_btn.clicked.connect(self.restart_requested.emit)
        restart_btn.setFixedHeight(40)
        restart_btn.setMinimumWidth(140)
        btn_layout.addWidget(restart_btn)

        # Exit button
        exit_btn = QPushButton("Exit Application")
        exit_btn.setObjectName("secondaryButton")
        exit_btn.clicked.connect(self.exit_requested.emit)
        exit_btn.setFixedHeight(40)
        exit_btn.setMinimumWidth(140)
        btn_layout.addWidget(exit_btn)

        btn_layout.addStretch()

        layout.addWidget(btn_container)

        return section

    def _create_button_row(self) -> QWidget:
        """Create Apply/Cancel button row with better visual hierarchy."""
        button_container = QWidget()
        button_container.setObjectName("settingsButtonContainer")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(
            Spacing.MAJOR_GAP, Spacing.MAJOR_GAP, Spacing.MAJOR_GAP, Spacing.MAJOR_GAP
        )
        button_layout.setSpacing(Spacing.MAJOR_GAP)
        button_layout.addStretch()

        # Apply button (primary action)
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setObjectName("primaryButton")
        self.apply_btn.setFixedHeight(40)
        self.apply_btn.setMinimumWidth(120)
        self.apply_btn.clicked.connect(self._on_apply)
        button_layout.addWidget(self.apply_btn)

        button_layout.addStretch()
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
            show_error_dialog(
                "Settings Error", "Failed to save settings.", str(e), parent=self
            )

    def _on_clear_all_history(self) -> None:
        """Show confirmation dialog before clearing history."""
        dialog = ConfirmationDialog(
            title="Clear All History",
            message="Are you sure you want to clear all transcription history?\n\nThis action cannot be undone. All transcripts will be permanently deleted.",
            parent=self,
        )
        if dialog.exec() == ConfirmationDialog.DialogCode.Accepted:
            self.clear_all_history_requested.emit()

    def _read_widget_value(self, widget: QWidget) -> Any:
        """Extract value from widget."""
        if isinstance(widget, ToggleSwitch):
            return widget.isChecked()
        if isinstance(widget, QSpinBox):
            return widget.value()
        if isinstance(widget, QDoubleSpinBox):
            return widget.value()
        if isinstance(widget, QComboBox):
            val = widget.currentData()
            return val if val is not None else widget.currentText()
        if isinstance(widget, QLineEdit):
            return widget.text()
        if isinstance(widget, SliderField):
            return widget.value()
        if isinstance(widget, HotkeyWidget):
            return widget.get_hotkey()
        return None

    def _set_widget_value(self, widget: QWidget, value: Any) -> None:
        """Set widget value."""
        if isinstance(widget, ToggleSwitch):
            widget.setChecked(bool(value))
        elif isinstance(widget, QSpinBox):
            widget.setValue(int(value))
        elif isinstance(widget, QDoubleSpinBox):
            widget.setValue(float(value))
        elif isinstance(widget, QComboBox):
            idx = widget.findData(str(value))
            if idx >= 0:
                widget.setCurrentIndex(idx)
            else:
                widget.setCurrentText(str(value))
        elif isinstance(widget, QLineEdit):
            widget.setText(str(value))
        elif isinstance(widget, SliderField):
            widget.set_value(float(value))
        elif isinstance(widget, HotkeyWidget):
            widget.set_hotkey(str(value))

    def cleanup(self) -> None:
        """Clean up resources."""
        # Disconnect config change listener
        try:
            self._config_manager.config_changed.disconnect(self._on_config_changed)
        except (RuntimeError, TypeError, AttributeError):
            # Signal already disconnected or object deleted
            pass

        for widget in self.widgets.values():
            if isinstance(widget, HotkeyWidget):
                widget.cleanup()
            elif isinstance(widget, ToggleSwitch):
                if widget.animation:
                    widget.animation.stop()
        super().cleanup()
