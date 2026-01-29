"""
Onboarding Pages - Content for each step of the onboarding wizard.
"""

from __future__ import annotations

from pathlib import Path
from src.core.resource_manager import ResourceManager
import os
import subprocess
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject, QRect, QSize
from PyQt6.QtGui import QPainter, QColor, QBrush
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QLineEdit,
    QPushButton,
    QAbstractButton,
    QSizePolicy,
    QLayout,
    QLayoutItem,
)
from src.core.config_manager import ConfigManager, get_model_cache_dir
from src.ui.widgets.hotkey_widget.hotkey_widget import HotkeyWidget
from src.services.voice_calibration import VoiceCalibrator
from src.services.slm_service import MODELS
from src.services.slm_background_workers import ProvisioningWorker
from src.ui.constants import Typography, Spacing
from src.ui.constants.dimensions import BORDER_RADIUS_SM
import src.ui.constants.colors as c


class FlowLayout(QLayout):
    """Flow layout that wraps items to new lines based on available width.

    Implements height-for-width to ensure proper sizing in scrollable containers.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._spacing = Spacing.S2

    def addItem(self, item: QLayoutItem) -> None:
        """Add an item to the layout."""
        self._items.append(item)

    def itemAt(self, index: int) -> QLayoutItem | None:
        """Get item at index."""
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:
        """Remove and return item at index."""
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def count(self) -> int:
        """Return number of items."""
        return len(self._items)

    def setSpacing(self, spacing: int) -> None:
        """Set spacing between items."""
        self._spacing = spacing

    def spacing(self) -> int:
        """Get spacing between items."""
        return self._spacing

    def hasHeightForWidth(self) -> bool:
        """Indicate that this layout's height depends on its width."""
        return True

    def heightForWidth(self, width: int) -> int:
        """Calculate required height for given width."""
        height = self._doLayoutCalculation(QRect(0, 0, width, 0))
        return height

    def sizeHint(self) -> QSize:
        """Return preferred size."""
        # If parent has a width, calculate proper height
        if self.parentWidget() and self.parentWidget().width() > 0:
            width = self.parentWidget().width()
            height = self.heightForWidth(width)
            return QSize(width, height)
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        """Return minimum size."""
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size.setWidth(size.width() + margins.left() + margins.right())
        size.setHeight(size.height() + margins.top() + margins.bottom())
        return size

    def doLayout(self, rect: QRect) -> None:
        """Layout items in flow pattern."""
        self._doLayoutCalculation(rect, apply_geometry=True)

    def _doLayoutCalculation(self, rect: QRect, apply_geometry: bool = False) -> int:
        """Calculate layout and optionally apply geometry.

        Args:
            rect: The rectangle to lay out within
            apply_geometry: If True, actually position widgets; if False, only calculate height

        Returns:
            Total height required
        """
        margins = self.contentsMargins()
        x = rect.x() + margins.left()
        y = rect.y() + margins.top()
        line_height = 0
        spacing = self._spacing

        for item in self._items:
            item_size = item.sizeHint()
            next_x = x + item_size.width() + spacing

            # Check if we need to wrap to next line
            effective_right = rect.right() - margins.right()
            if next_x - spacing > effective_right and line_height > 0:
                # Move to next line
                x = rect.x() + margins.left()
                y = y + line_height + spacing
                next_x = x + item_size.width() + spacing
                line_height = 0

            if apply_geometry:
                item.setGeometry(QRect(x, y, item_size.width(), item_size.height()))

            x = next_x
            line_height = max(line_height, item_size.height())

        # Return total height used
        return y + line_height - rect.y() + margins.bottom()

    def setGeometry(self, rect: QRect) -> None:
        """Set geometry and perform layout."""
        super().setGeometry(rect)
        self.doLayout(rect)


class ToggleSwitch(QAbstractButton):
    """Custom toggle switch (sliding pill)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(50, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        height = rect.height()
        width = rect.width()

        if self.isChecked():
            bg_color = QColor(c.BLUE_4)
            circle_x = width - height + 3
        else:
            bg_color = QColor(c.GRAY_6)
            circle_x = 3

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(bg_color))
        p.drawRoundedRect(0, 0, width, height, height / 2, height / 2)

        p.setBrush(QBrush(QColor(c.GRAY_0)))
        circle_size = height - 6
        p.drawEllipse(circle_x, 3, circle_size, circle_size)


class BasePage(QWidget):
    """Base class for onboarding pages."""

    completeness_changed = pyqtSignal(bool)

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent)
        self.config_collector: dict | None = None

        # Ensure pages respect background-color in stylesheet
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(Spacing.S4, Spacing.S2, Spacing.S4, Spacing.S2)
        self.layout.setSpacing(Spacing.S2)
        self.setup_ui(**kwargs)

    def set_config_collector(self, collector: dict):
        self.config_collector = collector

    def update_config(self, value, *keys):
        if self.config_collector is not None:
            self.config_collector[keys] = value
        else:
            ConfigManager.set_config_value(value, *keys)
            ConfigManager.save_config()

    def read_config(self, *keys):
        if self.config_collector is not None and keys in self.config_collector:
            return self.config_collector[keys]
        return ConfigManager.get_config_value(*keys)

    def setup_ui(self, **kwargs):
        pass

    def is_complete(self) -> bool:
        return True

    def on_enter(self):
        """Called when page becomes active."""
        pass

    def on_exit(self):
        """Called when leaving page."""
        pass

    def cleanup(self):
        """Called to clean up resources (e.g., stop threads). Override in subclasses."""
        pass


class WelcomePage(BasePage):
    def setup_ui(self, **kwargs):
        title = QLabel("Welcome to Vociferous")
        title.setObjectName("onboardingTitle")
        title.setProperty("class", "onboardingTitleXL")
        title.setWordWrap(True)

        content = QLabel(
            "Your local, private, voice-powered transcription assistant.\n\n"
            "This wizard will configure:\n"
            "• Greeting Personalization\n"
            "• AI Refinement\n"
            "• Voice Calibration"
        )
        content.setObjectName("onboardingDesc")
        content.setWordWrap(True)
        content.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        content.setStyleSheet(
            f"font-size: {Typography.FONT_SIZE_MD}pt; color: {c.GRAY_2};"
        )

        self.layout.addWidget(title)
        self.layout.addSpacing(Spacing.S3)  # Use layout spacing instead of margins
        self.layout.addWidget(content)
        self.layout.addStretch()


class IdentityPage(BasePage):
    def setup_ui(self, **kwargs):
        title = QLabel("Who are you?")
        title.setStyleSheet(
            f"font-size: {Typography.FONT_SIZE_LG}pt; font-weight: bold;"
        )
        title.setWordWrap(True)

        desc = QLabel("Vociferous addresses you by first name. How should we call you?")
        desc.setWordWrap(True)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter your first name")
        self.name_input.setFixedHeight(48)
        self.name_input.setMaximumWidth(350)
        self.name_input.setStyleSheet(
            f"border: 2px solid {c.GRAY_6}; border-radius: {BORDER_RADIUS_SM}px; padding: 8px; "
            f"background-color: {c.GRAY_8}; color: {c.GRAY_2};"
        )

        privacy = QLabel(
            "We do not share your name with anyone. Your name never leaves your local system configuration. "
            "This is used only for custom greetings."
        )
        privacy.setWordWrap(True)
        privacy.setStyleSheet(
            f"color: {c.GRAY_4}; font-size: {Typography.SMALL_SIZE}pt;"
        )

        self.layout.addWidget(title)
        self.layout.addSpacing(Spacing.S2)
        self.layout.addWidget(desc)
        self.layout.addSpacing(Spacing.S3)
        self.layout.addWidget(self.name_input)
        self.layout.addSpacing(Spacing.S2)
        self.layout.addWidget(privacy)
        self.layout.addStretch()

    def is_complete(self):
        # Explicitly optional
        return True

    def on_exit(self):
        name = self.name_input.text().strip()
        ConfigManager.set_config_value(name, "user", "name")


class RefinementPage(BasePage):
    def setup_ui(self, **kwargs):
        from src.ui.widgets.toggle_pill import TogglePill

        title = QLabel("AI Refinement Setup")
        title.setStyleSheet(
            f"font-size: {Typography.FONT_SIZE_LG}pt; font-weight: bold;"
        )
        title.setWordWrap(True)

        desc = QLabel(
            "Vociferous uses Small Language Models to refine your transcripts—fixing punctuation, "
            "capitalization, and formatting.\n\n"
            "Choose at least one model to download. Models run locally on your GPU and vary in speed/quality trade-offs."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        desc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        desc.setStyleSheet(f"color: {c.GRAY_2};")

        self.layout.addWidget(title)
        self.layout.addSpacing(Spacing.S2)
        self.layout.addWidget(desc)

        # Model Selection with TogglePills
        models_label = QLabel("Select Models:")
        models_label.setStyleSheet(
            f"font-weight: 600; font-size: {Typography.FONT_SIZE_MD}pt;"
        )

        self.layout.addSpacing(Spacing.S3)
        self.layout.addWidget(models_label)

        # Import service to get models
        from src.services.slm_service import SLMService

        models = SLMService.get_supported_models()

        self.model_pills = {}
        pills_container = QWidget()
        pills_layout = FlowLayout(pills_container)
        pills_layout.setContentsMargins(0, Spacing.S2, 0, 0)
        pills_layout.setSpacing(Spacing.S2)

        for model in models:
            pill = TogglePill(model.name)
            pill.toggled.connect(
                lambda checked, m=model: self._on_pill_toggled(m.id, checked)
            )
            self.model_pills[model.id] = pill
            pills_layout.addWidget(pill)

        self.layout.addWidget(pills_container)

        # Info display for selected models
        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(
            f"color: {c.GRAY_4}; margin-top: {Spacing.S2}px; font-size: {Typography.SMALL_SIZE}pt;"
        )
        self.layout.addWidget(self.info_label)

        # Validation message
        self.validation_label = QLabel("")
        self.validation_label.setStyleSheet(
            f"color: {c.RED_4}; font-weight: 600; margin-top: {Spacing.S1}px;"
        )
        self.layout.addWidget(self.validation_label)

        self.layout.addStretch()

        self.selected_models = set()

    def _on_pill_toggled(self, model_id: str, checked: bool):
        """Handle pill toggle."""
        if checked:
            self.selected_models.add(model_id)
        else:
            self.selected_models.discard(model_id)

        self._update_info()
        self._check_completeness()

    def _update_info(self):
        """Update info display with selected model details."""
        if not self.selected_models:
            self.info_label.setText("")
            return

        from src.services.slm_service import MODELS

        info_parts = []
        total_vram = 0

        for model_id in sorted(self.selected_models):
            model = MODELS[model_id]
            info_parts.append(
                f"• {model.name}: ~{model.required_vram_mb // 1024}GB VRAM"
            )
            total_vram += model.required_vram_mb

        info_parts.append(f"\nTotal VRAM Required: ~{total_vram // 1024}GB")
        self.info_label.setText("\n".join(info_parts))

    def _check_completeness(self):
        """Validate selection."""
        is_valid = len(self.selected_models) > 0

        if not is_valid:
            self.validation_label.setText("Please select a model to continue.")
        else:
            self.validation_label.setText("")

        self.completeness_changed.emit(is_valid)

    def is_complete(self):
        return len(self.selected_models) > 0

    def on_exit(self):
        """Save selected models to config."""
        if self.selected_models:
            ConfigManager.set_config_value(True, "refinement", "enabled")
            # Save the list of selected models for download later
            ConfigManager.set_config_value(
                list(self.selected_models), "refinement", "models_to_download"
            )
            ConfigManager.save_config()


class ASRModelPage(BasePage):
    """Page for selecting Whisper ASR model for transcription."""

    def setup_ui(self, **kwargs):
        from src.ui.widgets.toggle_pill import TogglePill

        title = QLabel("Transcription Model Setup")
        title.setStyleSheet(
            f"font-size: {Typography.FONT_SIZE_LG}pt; font-weight: bold;"
        )
        title.setWordWrap(True)

        desc = QLabel(
            "Vociferous uses OpenAI Whisper models for speech-to-text transcription.\n\n"
            "Choose one model to download. Models vary in speed, quality, and resource requirements."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        desc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        desc.setStyleSheet(f"color: {c.GRAY_2};")

        self.layout.addWidget(title)
        self.layout.addSpacing(Spacing.S2)
        self.layout.addWidget(desc)

        # Model Selection with TogglePills
        models_label = QLabel("Select ASR Model:")
        models_label.setStyleSheet(
            f"font-weight: 600; font-size: {Typography.FONT_SIZE_MD}pt;"
        )

        self.layout.addSpacing(Spacing.S3)
        self.layout.addWidget(models_label)

        # Import ASR models from registry
        from src.core.model_registry import ASR_MODELS, DEFAULT_ASR_MODEL_ID

        self.model_pills = {}
        pills_container = QWidget()
        pills_layout = FlowLayout(pills_container)
        pills_layout.setContentsMargins(0, Spacing.S2, 0, 0)
        pills_layout.setSpacing(Spacing.S2)

        for model_id, model in ASR_MODELS.items():
            pill = TogglePill(model.name)
            pill.toggled.connect(
                lambda checked, m=model: self._on_pill_toggled(m.id, checked)
            )
            self.model_pills[model.id] = pill
            pills_layout.addWidget(pill)

            # Pre-select the default model
            if model.id == DEFAULT_ASR_MODEL_ID:
                pill.setChecked(True)

        self.layout.addWidget(pills_container)

        # Info display for selected model
        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(
            f"color: {c.GRAY_4}; margin-top: {Spacing.S2}px; font-size: {Typography.SMALL_SIZE}pt;"
        )
        self.layout.addWidget(self.info_label)

        # Validation message
        self.validation_label = QLabel("")
        self.validation_label.setStyleSheet(
            f"color: {c.RED_4}; font-weight: 600; margin-top: {Spacing.S1}px;"
        )
        self.layout.addWidget(self.validation_label)

        self.layout.addStretch()

        # Track selected model (only one allowed)
        self.selected_model = DEFAULT_ASR_MODEL_ID
        self._update_info()

    def _on_pill_toggled(self, model_id: str, checked: bool):
        """Handle pill toggle - only one can be selected at a time."""
        if checked:
            # Uncheck all other pills
            for pill_id, pill in self.model_pills.items():
                if pill_id != model_id:
                    pill.setChecked(False)
            self.selected_model = model_id
        else:
            # Don't allow unchecking if it's the only selection
            if self.selected_model == model_id:
                self.model_pills[model_id].setChecked(True)
                return

        self._update_info()
        self._check_completeness()

    def _update_info(self):
        """Update info display with selected model details."""
        from src.core.model_registry import ASR_MODELS

        if not self.selected_model:
            self.info_label.setText("")
            return

        model = ASR_MODELS[self.selected_model]
        info = (
            f"• {model.name}\n"
            f"• VRAM Required: ~{model.required_vram_mb // 1024}GB\n"
            f"• Repo: {model.repo_id}"
        )
        self.info_label.setText(info)

    def _check_completeness(self):
        """Validate selection - exactly one model must be selected."""
        is_valid = self.selected_model is not None

        if not is_valid:
            self.validation_label.setText("Please select an ASR model to continue.")
        else:
            self.validation_label.setText("")

        self.completeness_changed.emit(is_valid)

    def is_complete(self):
        return self.selected_model is not None

    def on_exit(self):
        """Save selected ASR model to config."""
        if self.selected_model:
            ConfigManager.set_config_value(
                self.selected_model, "transcription", "model_id"
            )
            ConfigManager.save_config()


class HotkeyPage(BasePage):
    def setup_ui(self, key_listener=None, **kwargs):
        title = QLabel("Transcription Hotkey")
        title.setStyleSheet(
            f"font-size: {Typography.FONT_SIZE_LG}pt; font-weight: bold;"
        )
        title.setWordWrap(True)

        desc = QLabel(
            "Press the key combination you want to use to start/stop recording."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {c.GRAY_2};")

        # HotkeyWidget is complex, it expects full app context occasionally.
        # But here we just want to update config.
        # Note: We rely on the KeyListener passed from MainWindow.
        self.hotkey_widget = HotkeyWidget(key_listener)
        self.hotkey_widget.setMinimumHeight(60)

        # Pre-fill with current config default
        current = ConfigManager.get_config_value("recording_options", "activation_key")
        self.hotkey_widget.display.setText(current)

        self.layout.addWidget(title)
        self.layout.addSpacing(Spacing.S2)
        self.layout.addWidget(desc)
        self.layout.addSpacing(Spacing.S3)
        self.layout.addWidget(self.hotkey_widget)
        self.layout.addStretch()

    def on_exit(self):
        hotkey = self.hotkey_widget.get_hotkey()
        self.update_config(hotkey, "recording_options", "activation_key")


class SetupPage(BasePage):
    """Downloads models and setup desktop integration."""

    def setup_ui(self, **kwargs):
        title = QLabel("System Setup")
        title.setObjectName("onboardingTitle")
        title.setProperty("class", "onboardingTitleLG")
        title.setWordWrap(True)

        desc = QLabel(
            "This step will configure your system for optimal use.\n\n"
            "Actions performed:\n"
            "• Create desktop launcher entry\n"
            "• Configure application shortcuts\n"
            "• Set up system integration"
        )
        desc.setObjectName("onboardingDesc")
        desc.setWordWrap(True)
        desc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.status = QLabel("Ready to begin...")
        self.status.setObjectName("onboardingStatus")

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)

        # Launcher Toggle
        toggle_row = QWidget()
        toggle_layout = QHBoxLayout(toggle_row)
        toggle_layout.setContentsMargins(0, Spacing.S1, 0, Spacing.S1)
        toggle_layout.setSpacing(Spacing.S2)

        self.toggle_desktop = ToggleSwitch()
        self.toggle_desktop.setChecked(True)

        lbl_desktop = QLabel("Add Vociferous to Application Launcher")

        toggle_layout.addWidget(self.toggle_desktop)
        toggle_layout.addWidget(lbl_desktop)
        toggle_layout.addStretch()

        self.btn_run = QPushButton("Run Setup")
        self.btn_run.setObjectName("primaryButton")
        self.btn_run.setStyleSheet(
            f"background-color: {c.BLUE_4}; color: white; border-radius: {BORDER_RADIUS_SM}px; padding: 8px 16px; font-weight: bold;"
        )
        self.btn_run.clicked.connect(self.run_setup)

        self.layout.addWidget(title)
        self.layout.addWidget(desc)
        self.layout.addWidget(self.status)
        self.layout.addWidget(self.progress)
        self.layout.addWidget(toggle_row)
        self.layout.addWidget(self.btn_run)
        self.layout.addStretch()

        self._complete = False

    def run_setup(self):
        self.btn_run.setEnabled(False)
        self.toggle_desktop.setEnabled(False)
        self.progress.setRange(0, 0)  # Indeterminate
        self.status.setText("Configuring system integration...")

        refinement_enabled = self.read_config("refinement", "enabled")
        models_to_download = self.read_config("refinement", "models_to_download")

        # Create thread and worker using moveToThread pattern
        self._thread = QThread()
        self._worker = SetupWorker(
            self.toggle_desktop.isChecked(), refinement_enabled, models_to_download
        )

        # Move worker to thread
        self._worker.moveToThread(self._thread)

        # Connect signals BEFORE starting thread
        self._thread.started.connect(self._worker.do_work)
        self._worker.progress_update.connect(self.status.setText)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        # Start thread
        self._thread.start()

    def _on_finished(self, success: bool, message: str):
        """Handle worker completion with (success, message) from finished signal."""
        if not success:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.status.setText(f"Error: {message}")
            self.status.setStyleSheet(f"color: {c.RED_4}; font-weight: bold;")
            self.btn_run.setEnabled(True)
            self.toggle_desktop.setEnabled(True)
            self.btn_run.setText("Retry")
            self._complete = False
            self.completeness_changed.emit(False)
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(100)
            self.status.setText("Setup & Integration Complete!")
            self.status.setStyleSheet(f"color: {c.GREEN_3}; font-weight: bold;")
            self.btn_run.setText("Configured")
            self._complete = True
            self.completeness_changed.emit(True)

    def is_complete(self):
        return self._complete

    def cleanup(self):
        """Clean up thread resources if still running."""
        if hasattr(self, "_thread") and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()


class SetupWorker(QObject):
    """
    Worker for background onboarding setup tasks.

    Uses Qt6 moveToThread pattern instead of QThread subclass.
    This is the recommended approach per Qt6 threading documentation.

    Signals:
        finished(bool, str): Emitted when setup completes (success, message)
        progress_update(str): Emitted during progress updates

    References:
        - Qt6 Threading: https://doc.qt.io/qt-6/threads-qobject.html
    """

    finished = pyqtSignal(bool, str)
    progress_update = pyqtSignal(str)

    def __init__(self, install_desktop, refinement_enabled, models_to_download):
        super().__init__()
        self.install_desktop = install_desktop
        self.refinement_enabled = refinement_enabled
        self.models_to_download = models_to_download

    def _validate_model_artifacts(self, model_dir: Path) -> bool:
        """Check if all required model artifacts exist."""
        if not model_dir.exists():
            return False

        # CTranslate2 can produce vocabulary.json OR vocabulary.txt, check loosely
        has_vocab = (model_dir / "vocabulary.json").exists() or (
            model_dir / "vocabulary.txt"
        ).exists()
        has_model = (model_dir / "model.bin").exists()
        has_config = (model_dir / "config.json").exists()

        return has_vocab and has_model and has_config

    def do_work(self):
        # 1. Desktop Integration
        if self.install_desktop:
            self.progress_update.emit("Configuring desktop integration...")
            try:
                project_root = ResourceManager.get_app_root()
                script_path = project_root / "scripts" / "install-desktop-entry.sh"

                if not script_path.exists():
                    raise FileNotFoundError(f"Script not found: {script_path}")

                # Ensure executable
                os.chmod(script_path, script_path.stat().st_mode | 0o111)

                result = subprocess.run(
                    [str(script_path)],
                    capture_output=True,
                    text=True,
                    cwd=str(project_root),
                )

                if result.returncode != 0:
                    raise RuntimeError(
                        f"Desktop integration failed (Code {result.returncode}): {result.stderr}"
                    )

            except Exception as e:
                self.finished.emit(False, str(e))
                return

        # 2. Refinement Provisioning
        try:
            if self.refinement_enabled and self.models_to_download:
                cache_dir = get_model_cache_dir()
                cache_dir.mkdir(parents=True, exist_ok=True)

                for model_id in self.models_to_download:
                    if model_id not in MODELS:
                        continue

                    model = MODELS[model_id]
                    model_dir = cache_dir / model.dir_name

                    # Skip if model already exists and is valid
                    if self._validate_model_artifacts(model_dir):
                        self.progress_update.emit(
                            f"Model {model.name} already downloaded. Skipping..."
                        )
                        continue

                    self.progress_update.emit(f"Downloading model: {model.name}...")

                    worker = ProvisioningWorker(model, cache_dir)
                    worker.signals.progress.connect(self.progress_update.emit)

                    success = False
                    error_msg = ""

                    def on_finished(s, m):
                        nonlocal success, error_msg
                        success = s
                        error_msg = m

                    worker.signals.finished.connect(on_finished)

                    # Run synchronously in this thread
                    worker.run()

                    if not success:
                        raise RuntimeError(
                            f"Failed to provision {model.name}: {error_msg}"
                        )

            # Success - emit completion
            self.finished.emit(True, "Setup complete")

        except Exception as e:
            # Error - emit failure
            self.finished.emit(False, f"Model setup error: {e}")
            return


class CalibrationPage(BasePage):
    def setup_ui(self, **kwargs):
        title = QLabel("Voice Calibration")
        title.setStyleSheet(
            f"font-size: {Typography.FONT_SIZE_LG}pt; font-weight: bold;"
        )
        title.setWordWrap(True)

        desc = QLabel(
            "We'll record a brief sample to optimize the audio visualizer for your voice.\n\n"
            "When you click 'Start', please read the text below at your normal speaking pace."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        desc.setStyleSheet(f"color: {c.GRAY_2};")

        self.prompt = QLabel(
            "Artificial intelligence continues to advance rapidly, enabling new possibilities for human-computer interaction. Speech recognition systems can now understand natural language with remarkable accuracy, providing a significant productivity boost for many!"
        )
        self.prompt.setStyleSheet(
            f"font-style: italic; color: {c.BLUE_4}; font-size: {Typography.FONT_SIZE_MD}pt; padding: {Spacing.S3}px;"
        )
        self.prompt.setWordWrap(True)
        self.prompt.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_start = QPushButton("Start Calibration")
        self.btn_start.setProperty("styleClass", "primaryButton")
        self.btn_start.clicked.connect(self.start_calibration)

        self.btn_skip = QPushButton("Skip Calibration")
        self.btn_skip.setProperty("styleClass", "secondaryButton")
        self.btn_skip.setFlat(True)
        self.btn_skip.clicked.connect(self.skip_calibration)
        self.btn_skip.hide()

        self.output_log = QLabel("")
        self.output_log.setWordWrap(True)
        self.output_log.setStyleSheet(f"color: {c.GRAY_4};")

        self.layout.addWidget(title)
        self.layout.addSpacing(Spacing.S2)
        self.layout.addWidget(desc)
        self.layout.addSpacing(Spacing.S3)
        self.layout.addWidget(self.prompt)
        self.layout.addSpacing(Spacing.S3)
        self.layout.addWidget(self.btn_start)
        self.layout.addWidget(self.btn_skip)
        self.layout.addSpacing(Spacing.S2)
        self.layout.addWidget(self.output_log)
        self.layout.addStretch()

        self._complete = False
        self.thread: CalibrationWorker | None = None

    def cleanup(self):
        """Stop calibration thread if running."""
        if self.thread and self.thread.isRunning():
            try:
                self.thread.calibrator.request_cancel()  # Signal calibrator to cancel
            except Exception:
                pass  # Calibrator might not support request_cancel
            self.thread.quit()  # Gracefully stop the thread
            self.thread.wait(2000)  # Wait up to 2 seconds for thread to finish
            if self.thread.isRunning():
                self.thread.terminate()  # Force terminate if still running
                self.thread.wait(500)

    def start_calibration(self):
        self.btn_start.setEnabled(False)
        self.btn_skip.hide()
        self.output_log.setText("Initializing recording device...")

        self.calibrator = VoiceCalibrator()

        self.thread = CalibrationWorker(self.calibrator)
        self.thread.progress.connect(self.output_log.setText)
        self.thread.calibration_finished.connect(self._on_finished)  # Use custom signal
        self.thread.error_occurred.connect(self._on_error)
        self.thread.start()

    def _on_error(self, error_msg):
        self.output_log.setText(f"Calibration Failed: {error_msg}")
        self.output_log.setStyleSheet(
            f"color: {c.RED_4}; margin-top: 10px; font-weight: bold;"
        )
        self.btn_start.setText("Retry")
        self.btn_start.setEnabled(True)
        self.btn_skip.show()

        self._complete = False
        self.completeness_changed.emit(False)

    def skip_calibration(self):
        self.output_log.setText("Calibration skipped. Using default settings.")
        self.output_log.setStyleSheet(
            f"color: {c.GRAY_2}; margin-top: 10px; font-style: italic;"
        )
        self.btn_start.setEnabled(True)
        self.btn_skip.hide()
        self._complete = True
        self.completeness_changed.emit(True)

    def _on_finished(self, results):
        self.calibrator.save_calibration(results)
        # Assuming results can be roughly formatted or user just sees success
        self.output_log.setText(
            f"Calibration Saved!\nFundamental: {results.get('fundamental_freq', 0):.0f}Hz"
        )
        self.output_log.setStyleSheet(f"color: {c.GREEN_3}; margin-top: 10px;")

        self.btn_start.setText("Recalibrate")
        self.btn_start.setEnabled(True)

        self._complete = True
        self.completeness_changed.emit(True)

    def is_complete(self):
        return self._complete


class CalibrationWorker(QThread):
    """
    Worker thread for voice calibration.

    Signals:
        progress(object): Emitted during calibration progress
        calibration_finished(dict): Emitted when calibration completes successfully with results
        error_occurred(str): Emitted when an error occurs
    """

    progress = pyqtSignal(object)
    calibration_finished = pyqtSignal(object)  # Custom signal for results
    error_occurred = pyqtSignal(str)

    def __init__(self, calibrator):
        super().__init__()
        self.calibrator = calibrator

    def run(self):
        try:
            results = self.calibrator.calibrate(on_progress=self.progress.emit)
            self.calibration_finished.emit(
                results
            )  # Use custom signal instead of QThread.finished
        except Exception as e:
            self.error_occurred.emit(str(e))
            self.progress.emit(f"Error: {e}")
