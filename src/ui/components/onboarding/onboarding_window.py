"""
OnboardingWindow - The wizard container for the first-run experience.
"""

import logging
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal
from src.ui.components.title_bar.title_bar import TitleBar
from src.ui.components.onboarding.pages import (
    WelcomePage,
    IdentityPage,
    RefinementPage,
    ASRModelPage,
    HotkeyPage,
    SetupPage,
    CalibrationPage,
)
from src.ui.constants import Spacing
from src.core.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class OnboardingWindow(QDialog):
    completed = pyqtSignal()
    cancelled = pyqtSignal()  # Signal to request graceful app shutdown

    def __init__(self, key_listener, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        # Use min/max size instead of fixed - allows flexibility for DPI/fonts
        self.setMinimumSize(700, 650)
        self.setMaximumSize(900, 900)
        self.resize(800, 800)  # Default size
        self.setWindowTitle("Vociferous Setup")

        self._key_listener = key_listener
        self._is_finishing = False  # Flag to track if we're finishing normally
        self._setup_ui()
        self._update_nav_buttons()

    def _setup_ui(self):
        # Main Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # 1. Title Bar
        self.title_bar = TitleBar(self)
        self.layout.addWidget(self.title_bar)

        # 2. Content Area (Stacked)
        self.content_stack = QStackedWidget()

        # Pages
        self.pages = [
            WelcomePage(),
            IdentityPage(),
            RefinementPage(),
            ASRModelPage(),
            HotkeyPage(key_listener=self._key_listener),
            SetupPage(),
            CalibrationPage(),
        ]

        # Inject config collector for atomic commit
        self._pending_config = {}
        for page in self.pages:
            if hasattr(page, "set_config_collector"):
                page.set_config_collector(self._pending_config)

            self.content_stack.addWidget(page)
            # Connect completeness signal to navigation update
            page.completeness_changed.connect(self._update_nav_buttons)

        self.layout.addWidget(self.content_stack, 1)  # Expanding

        # 3. Footer / Nav Bar
        self.footer = QWidget()
        self.footer.setObjectName("onboardingFooter")
        # Ensure footer respects background-color from stylesheet
        self.footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.footer_layout = QHBoxLayout(self.footer)
        self.footer_layout.setContentsMargins(
            Spacing.S3, Spacing.S2, Spacing.S3, Spacing.S2
        )

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.close)  # Triggers closeEvent
        self.btn_cancel.setProperty("styleClass", "destructiveButton")
        self.btn_cancel.setFlat(True)

        self.btn_prev = QPushButton("Previous")
        self.btn_prev.clicked.connect(self.go_prev)
        self.btn_prev.setProperty("styleClass", "secondaryButton")

        self.btn_next = QPushButton("Next")
        self.btn_next.setObjectName("primaryButton")
        self.btn_next.setProperty("styleClass", "primaryButton")
        self.btn_next.clicked.connect(self.go_next)

        self.footer_layout.addWidget(self.btn_cancel)
        self.footer_layout.addStretch()
        self.footer_layout.addWidget(self.btn_prev)
        self.footer_layout.addWidget(self.btn_next)

        self.layout.addWidget(self.footer)

    def _update_nav_buttons(self):
        idx = self.content_stack.currentIndex()
        total = self.content_stack.count()
        current_page = self.pages[idx]

        # Prev State
        self.btn_prev.setEnabled(idx > 0)
        self.btn_prev.setVisible(idx > 0)

        # Next/Finish State
        is_last = idx == total - 1
        is_complete = current_page.is_complete()

        if is_last:
            self.btn_next.setText("Finish")
            self.btn_next.setProperty("state", "finish")
            self.btn_next.style().unpolish(self.btn_next)
            self.btn_next.style().polish(self.btn_next)
        else:
            self.btn_next.setText("Next")
            self.btn_next.setProperty("state", "")
            self.btn_next.style().unpolish(self.btn_next)
            self.btn_next.style().polish(self.btn_next)

        self.btn_next.setEnabled(is_complete)

    def go_prev(self):
        idx = self.content_stack.currentIndex()
        if idx > 0:
            self.pages[idx].on_exit()
            self.content_stack.setCurrentIndex(idx - 1)
            self.pages[idx - 1].on_enter()
            self._update_nav_buttons()

    def go_next(self):
        idx = self.content_stack.currentIndex()
        total = self.content_stack.count()
        logger.debug(f"go_next(): current_index={idx}, total_pages={total}")

        self.pages[idx].on_exit()

        if idx < total - 1:
            logger.debug(f"Moving to next page {idx + 1}")
            self.content_stack.setCurrentIndex(idx + 1)
            self.pages[idx + 1].on_enter()
            self._update_nav_buttons()
        else:
            logger.info(f"On last page (idx={idx}), calling _finish_onboarding()")
            self._finish_onboarding()

    def _finish_onboarding(self):
        logger.info("=== ONBOARDING FINISH CALLED ===")

        # Atomic commit of configuration
        if self._pending_config:
            logger.info(f"Committing pending config: {self._pending_config}")
            for keys, value in self._pending_config.items():
                logger.debug(f"  Setting {keys} = {value}")
                ConfigManager.set_config_value(value, *keys)

        # Ensure the final page's on_exit is called for consistency
        current_idx = self.content_stack.currentIndex()
        if current_idx < len(self.pages):
            logger.debug(f"Calling on_exit() for page {current_idx}")
            self.pages[current_idx].on_exit()

        try:
            logger.info("Setting onboarding_completed = True in config")
            ConfigManager.set_config_value(True, "user", "onboarding_completed")

            logger.info("Saving config to disk...")
            ConfigManager.save_config()
            logger.info("Config saved successfully")
        except Exception as e:
            logger.error(f"ERROR saving config: {e}", exc_info=True)
            raise

        # Set flag BEFORE calling accept() to prevent confirmation dialog
        self._is_finishing = True
        logger.info("Calling self.accept()")
        self.accept()

        logger.info("Emitting completed signal")
        self.completed.emit()
        logger.info("=== ONBOARDING FINISH COMPLETE ===")

    def closeEvent(self, event):
        # If we're finishing normally, just accept and don't show confirmation
        if self._is_finishing:
            logger.debug("closeEvent: Finishing normally, skipping confirmation dialog")
            event.accept()
            return

        # Stop any running background tasks (e.g., calibration threads)
        for page in self.pages:
            try:
                page.cleanup()
            except Exception:
                pass  # Ignore cleanup errors

        # "Attempting to close ... must trigger confirm ... exiting terminates app"
        # Create custom styled dialog instead of QMessageBox
        from src.ui.widgets.dialogs.custom_dialog import ConfirmationDialog

        dialog = ConfirmationDialog(
            parent=self,
            title="Exit Setup?",
            message="Completing the setup is required to use Vociferous.\n\nExiting now will close the application.",
            confirm_text="Yes, Exit",
            cancel_text="No, Continue",
            is_destructive=True,
        )

        if dialog.exec() == ConfirmationDialog.DialogCode.Accepted:
            event.accept()
            self.cancelled.emit()  # Signal main app to cleanup and exit
        else:
            event.ignore()
