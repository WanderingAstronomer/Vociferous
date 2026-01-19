"""
OnboardingWindow - The wizard container for the first-run experience.
"""

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
    HotkeyPage,
    SetupPage,
    CalibrationPage,
)
from src.ui.constants import Spacing
from src.ui.constants.dimensions import BORDER_RADIUS_SM
from src.core.config_manager import ConfigManager
import src.ui.constants.colors as c


class OnboardingWindow(QDialog):
    completed = pyqtSignal()
    cancelled = pyqtSignal()  # Signal to request graceful app shutdown

    def __init__(self, key_listener, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(800, 800)  # Standard dialog size
        self.setWindowTitle("Vociferous Setup")

        self._key_listener = key_listener
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
        self.btn_next.setStyleSheet(
            f"background-color: {c.BLUE_4}; color: white; border-radius: {BORDER_RADIUS_SM}px; padding: 6px 16px;"
        )
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
            self.btn_next.setStyleSheet(
                f"background-color: {c.GREEN_3}; color: {c.GRAY_8}; border-radius: {BORDER_RADIUS_SM}px; padding: 6px 16px; font-weight: bold;"
            )
        else:
            self.btn_next.setText("Next")
            self.btn_next.setStyleSheet(
                f"background-color: {c.BLUE_4}; color: white; border-radius: {BORDER_RADIUS_SM}px; padding: 6px 16px;"
            )

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

        self.pages[idx].on_exit()

        if idx < total - 1:
            self.content_stack.setCurrentIndex(idx + 1)
            self.pages[idx + 1].on_enter()
            self._update_nav_buttons()
        else:
            self._finish_onboarding()

    def _finish_onboarding(self):
        # Atomic commit of configuration
        if self._pending_config:
            for keys, value in self._pending_config.items():
                ConfigManager.set_config_value(value, *keys)

        # Ensure the final page's on_exit is called for consistency
        current_idx = self.content_stack.currentIndex()
        if current_idx < len(self.pages):
            self.pages[current_idx].on_exit()

        ConfigManager.set_config_value(True, "user", "onboarding_completed")
        ConfigManager.save_config()
        self.accept()
        self.completed.emit()

    def closeEvent(self, event):
        # Stop any running background tasks (e.g., calibration threads)
        for page in self.pages:
            try:
                page.cleanup()
            except Exception:
                pass  # Ignore cleanup errors

        # "Attempting to close ... must trigger confirm ... exiting terminates app"
        # Create custom styled dialog instead of QMessageBox
        from src.ui.widgets.dialogs import ConfirmationDialog

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
