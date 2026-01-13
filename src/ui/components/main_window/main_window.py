"""
MainWindow - Primary application window for Vociferous.

Integrates sidebar, main workspace, and metrics strip in a responsive layout.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import (
    QEvent,
    QSettings,
    Qt,
    QTimer,
    QUrl,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import (
    QDesktopServices,
    QGuiApplication,
)
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenuBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.components.main_window.intent_feedback import IntentFeedbackHandler
from ui.components.main_window.menu_builder import MenuBuilder
from ui.components.title_bar import TitleBar
from ui.constants import (
    Colors,
    Spacing,
    WindowSize,
)
from ui.widgets.dialogs import ConfirmationDialog, MessageDialog, show_error_dialog
from ui.widgets.metrics_strip import MetricsStrip

# New shell components
from ui.components.icon_rail import IconRail
from ui.components.view_host import ViewHost
from ui.components.action_grid import ActionGrid

# Views
from ui.views.transcribe_view import TranscribeView
from ui.views.recent_view import RecentView
from ui.views.projects_view import ProjectsView
from ui.views.search_view import SearchView
from ui.views.refine_view import RefineView
from ui.views.edit_view import EditView
from ui.constants.view_ids import (
    VIEW_TRANSCRIBE, VIEW_RECENT, VIEW_PROJECTS, VIEW_SEARCH, VIEW_REFINE, VIEW_EDIT
)

if TYPE_CHECKING:
    from history_manager import HistoryEntry, HistoryManager

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """
    Primary application window with sidebar, workspace, and metrics strip.

    Layout:
    ┌─────────────────────────────────────────┐
    │              Title Bar                  │
    ├─────────┬───────────────────────────────┤
    │         │                               │
    │ Sidebar │     Main Workspace            │
    │         │                               │
    ├─────────┴───────────────────────────────┤
    │           Metrics Strip                 │
    └─────────────────────────────────────────┘

    Signals:
        windowCloseRequested(): Window is closing
        cancelRecordingRequested(): Cancel recording
        startRecordingRequested(): Start recording
        stopRecordingRequested(): Stop recording
    """

    windowCloseRequested = pyqtSignal()
    cancelRecordingRequested = pyqtSignal()
    startRecordingRequested = pyqtSignal()
    stopRecordingRequested = pyqtSignal()

    def __init__(self, history_manager: HistoryManager | None = None) -> None:
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)

        self.settings = QSettings("Vociferous", "MainWindow")
        self.history_manager = history_manager

        # Menu bar (created before title bar)
        self._menu_bar = QMenuBar(self)

        # Custom title bar
        self.title_bar = TitleBar(self, self._menu_bar)

        # Debounce timer for metrics refresh (avoid blocking on rapid transcripts)
        self._metrics_refresh_timer = QTimer()
        self._metrics_refresh_timer.setSingleShot(True)
        self._metrics_refresh_timer.setInterval(1000)  # 1s debounce

        self._init_ui()
        self._create_menu_bar()
        self._restore_state()

    def _init_ui(self) -> None:
        """Initialize the main UI layout."""
        self.setWindowTitle("Vociferous")
        self.setMinimumSize(WindowSize.MIN_WIDTH, WindowSize.MIN_HEIGHT)

        # Title bar as menu widget
        self.setMenuWidget(self.title_bar)

        # Central widget with outer padding
        central = QWidget(self)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(
            Spacing.APP_OUTER, Spacing.APP_OUTER, Spacing.APP_OUTER, Spacing.APP_OUTER
        )
        main_layout.setSpacing(Spacing.MAJOR_GAP)

        # Main horizontal container (Rail | Content)
        container_layout = QHBoxLayout()
        container_layout.setSpacing(Spacing.MAJOR_GAP)
        
        # 1. Icon Rail (Navigation)
        self.icon_rail = IconRail()
        self.icon_rail.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )
        self.icon_rail.view_changed.connect(self._on_view_changed)
        container_layout.addWidget(self.icon_rail, 0)

        # 2. Content Column (Views + ActionGrid + Metrics)
        content_column = QVBoxLayout()
        content_column.setSpacing(Spacing.MAJOR_GAP)

        # 2.1 View Host (The stack of screens)
        self.view_host = ViewHost()
        
        # 2.2 Action Grid (Contextual Actions)
        self.action_grid = ActionGrid()

        # 2.3 Metrics Strip
        self.metrics_strip = MetricsStrip(self.history_manager)

        # Build Layout
        content_column.addWidget(self.view_host, 1) # Expanding
        content_column.addWidget(self.action_grid, 0) # Fixed height
        content_column.addWidget(self.metrics_strip, 0) # Fixed height

        container_layout.addLayout(content_column, 1)
        main_layout.addLayout(container_layout)

        # Connect debounce timer now that metrics_strip exists
        self._metrics_refresh_timer.timeout.connect(self.metrics_strip.refresh)

        central.setLayout(main_layout)
        self.setCentralWidget(central)

        # Status bar for intent feedback
        self._status_bar = self.statusBar()
        self._status_bar.setSizeGripEnabled(True)
        self._status_bar.hide()
        
        self._status_bar.setStyleSheet(f"""
            QStatusBar {{
                background: {Colors.BACKGROUND};
                color: {Colors.TEXT_SECONDARY};
                border-top: 1px solid {Colors.BORDER_DEFAULT};
                padding: 4px 8px;
            }}
            QStatusBar::item {{
                border: none;
            }}
        """)
        
        from PyQt6.QtWidgets import QLabel
        self._status_label = QLabel()
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_bar.addWidget(self._status_label, 1)

        # Intent feedback handler
        self._intent_feedback = IntentFeedbackHandler(self._status_bar, self)
        
        # Initialize views (Must be after ActionGrid and ViewHost)
        self._init_views()

    def _init_views(self) -> None:
        """Instantiate and register all application views."""
        # Instantiate
        self.view_transcribe = TranscribeView()
        self.view_recent = RecentView() 
        if self.history_manager:
            self.view_recent.set_history_manager(self.history_manager)
            
        self.view_recent.editRequested.connect(self._on_edit_view_requested)
        self.view_recent.refineRequested.connect(self._on_refine_view_requested)
        # Refine requested via View -> passes to validation -> Orchestrator?
        # Typically Refine needs "Text" + "Profile". 
        # For now, let's just use the Orchestrator signal if possible, or a local handler.
        # But RecentView emits (id). We need to show the refinement dialog first? 
        # Or does "Refine" action jump to a specific flow?
        # The Orchestrator has `_on_refine_requested`.
        # Let's direct connect for now to a stub handler or MainWindow handler.
            
        self.view_projects = ProjectsView()
        self.view_search = SearchView()
        self.view_refine = RefineView()
        self.view_edit = EditView()
        
        # Register
        self.view_host.register_view(self.view_transcribe, VIEW_TRANSCRIBE)
        self.view_host.register_view(self.view_recent, VIEW_RECENT)
        self.view_host.register_view(self.view_projects, VIEW_PROJECTS)
        self.view_host.register_view(self.view_search, VIEW_SEARCH)
        self.view_host.register_view(self.view_refine, VIEW_REFINE)
        self.view_host.register_view(self.view_edit, VIEW_EDIT)
        
        # Map for ActionGrid lookup
        self._view_map = {
            VIEW_TRANSCRIBE: self.view_transcribe,
            VIEW_RECENT: self.view_recent,
            VIEW_PROJECTS: self.view_projects,
            VIEW_SEARCH: self.view_search,
            VIEW_REFINE: self.view_refine,
            VIEW_EDIT: self.view_edit,
        }

        # Set default view
        self.icon_rail.set_active_view(VIEW_TRANSCRIBE)
        self._on_view_changed(VIEW_TRANSCRIBE)

    @pyqtSlot(str)
    def _on_view_changed(self, view_id: str) -> None:
        """Handle view switching logic."""
        self.view_host.switch_to_view(view_id)
        self.icon_rail.set_active_view(view_id)
        
        current_view = self._view_map.get(view_id)
        if current_view:
            self.action_grid.set_active_view(current_view)

    def _create_menu_bar(self) -> None:
        """Create menu bar with all menus."""
        self._menu_builder = MenuBuilder(self._menu_bar, self)
        self._menu_builder.build(
            on_exit=lambda: (self.close(), None)[1],
            on_restart=self._restart_application,
            on_export=self._export_history,
            on_clear=self._clear_all_history,
            on_toggle_metrics=self._toggle_metrics,
            on_focus_history=self._switch_to_history, # Modified
            on_about=self._show_about_dialog,
            on_metrics_explanation=self._show_metrics_explanation,
            on_toggle_sidebar=lambda: None, # Deprecated
        )

        # Connect metrics strip collapse signal
        self.metrics_strip.collapsedChanged.connect(self._on_metrics_collapsed_changed)

    # Slot handlers

    @pyqtSlot(int)
    def _on_edit_view_requested(self, transcript_id: int) -> None:
        """Switch to EditView for a specific transcript."""
        self._on_view_changed(VIEW_EDIT)
        if hasattr(self.view_edit, "load_transcript_by_id"):
             self.view_edit.load_transcript_by_id(transcript_id)

    @pyqtSlot(int)
    def _on_refine_view_requested(self, transcript_id: int) -> None:
        """Switch to RefineView for a specific transcript."""
        self._on_view_changed(VIEW_REFINE)
        if hasattr(self.view_refine, "load_transcript_by_id"):
             self.view_refine.load_transcript_by_id(transcript_id)

    @pyqtSlot()
    def _on_start_requested(self) -> None:
        try:
            self.startRecordingRequested.emit()
        except Exception:
            logger.exception("Error in _on_start_requested")

    @pyqtSlot()
    def _on_stop_requested(self) -> None:
        try:
            self.stopRecordingRequested.emit()
        except Exception:
            logger.exception("Error in _on_stop_requested")

    @pyqtSlot()
    def _on_cancel_requested(self) -> None:
        """Handle cancel signal from workspace.

        Note: Workspace's _apply_cancel_recording already set state to IDLE.
        This handler only forwards to orchestrator.
        """
        try:
            self.cancelRecordingRequested.emit()
        except Exception:
            logger.exception("Error in _on_cancel_requested")

    @pyqtSlot(str)
    def _on_save_requested(self, text: str) -> None:
        pass

    @pyqtSlot()
    def _on_delete_requested(self) -> None:
        pass
        
    def show_refinement(self, transcript_id: int, original: str, refined: str) -> None:
        """Switch to RefineView and show comparison."""
        self._on_view_changed(VIEW_REFINE)
        if hasattr(self.view_refine, "set_comparison"):
            self.view_refine.set_comparison(transcript_id, original, refined)


    def _toggle_metrics(self, checked: bool) -> None:
        try:
            if self.metrics_strip.is_collapsed() == checked:
                self.metrics_strip.toggle_collapse()
        except Exception:
            logger.exception("Error toggling metrics")

    @pyqtSlot()
    # Removed duplicate definition of _toggle_sidebar
    # def _toggle_sidebar(self) -> None:
    #     """Deprecated."""
    #     pass

    @pyqtSlot(bool)
    def _on_metrics_collapsed_changed(self, collapsed: bool) -> None:
        try:
            if self._menu_builder.metrics_action:
                self._menu_builder.metrics_action.setChecked(not collapsed)
        except Exception:
            logger.exception("Error in _on_metrics_collapsed_changed")

    def _restart_application(self) -> None:
        """Restart the application by launching a new process and exiting."""
        import os
        import subprocess
        import sys

        try:
            # Use the run.py script for proper GPU library loading
            scripts_dir = os.path.join(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                ),
                "scripts",
            )
            run_script = os.path.join(scripts_dir, "run.py")

            if os.path.exists(run_script):
                # Launch via run.py for proper LD_LIBRARY_PATH setup
                subprocess.Popen(
                    [sys.executable, run_script],
                    start_new_session=True,
                )
            else:
                # Fallback: launch main.py directly
                main_script = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    "main.py",
                )
                subprocess.Popen(
                    [sys.executable, main_script],
                    start_new_session=True,
                )

            # Close the current application
            self.close()
        except Exception as e:
            logger.exception("Failed to restart application")
            show_error_dialog(
                title="Restart Error",
                message=f"Failed to restart: {e}",
                parent=self,
            )

    def _show_about_dialog(self) -> None:
        """Show the About Vociferous dialog."""
        from ui.components.title_bar import DialogTitleBar

        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        dialog.setModal(True)

        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Add draggable title bar
        title_bar = DialogTitleBar("About Vociferous", dialog)
        title_bar.closeRequested.connect(dialog.reject)
        main_layout.addWidget(title_bar)

        # Content container
        content = QWidget()
        content.setObjectName("dialogContent")
        layout = QVBoxLayout(content)
        layout.setSpacing(8)
        layout.setContentsMargins(20, 16, 20, 16)
        main_layout.addWidget(content)

        # App title
        title = QLabel("Vociferous")
        title.setObjectName("aboutTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Version/subtitle
        subtitle = QLabel("Modern Speech-to-Text for Linux")
        subtitle.setObjectName("aboutSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        # Description
        description = QLabel(
            "Vociferous was created to bring seamless, privacy-focused speech-to-text "
            "to the Linux desktop. Built with OpenAI's Whisper model, it runs entirely "
            "locally—no cloud services, no data collection, just fast and accurate "
            "transcription on your own machine."
        )
        description.setWordWrap(True)
        description.setObjectName("aboutDescription")
        layout.addWidget(description)

        # Creator info
        creator_label = QLabel("Created by Andrew Brown")
        creator_label.setObjectName("aboutCreator")
        creator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(creator_label)

        # Links
        links_layout = QHBoxLayout()
        links_layout.setSpacing(8)
        links_layout.setContentsMargins(0, 0, 0, 0)

        linkedin_btn = QPushButton("LinkedIn Profile")
        linkedin_btn.setObjectName("secondaryButton")
        linkedin_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://www.linkedin.com/in/abrown7521/")
            )
        )
        links_layout.addWidget(linkedin_btn)

        github_btn = QPushButton("GitHub Repository")
        github_btn.setObjectName("secondaryButton")
        github_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/WanderingAstronomer/Vociferous")
            )
        )
        links_layout.addWidget(github_btn)

        layout.addLayout(links_layout)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setObjectName("primaryButton")
        close_btn.clicked.connect(dialog.accept)
        close_btn.setMinimumHeight(40)
        layout.addWidget(close_btn)

        # Auto-size the dialog
        dialog.setMinimumWidth(420)
        dialog.adjustSize()
        dialog.exec()

    def _show_metrics_explanation(self) -> None:
        """Show the Metrics Calculations explanation dialog."""
        from ui.widgets.dialogs.metrics_explanation_dialog import (
            MetricsExplanationDialog,
        )

        dialog = MetricsExplanationDialog(self)
        dialog.exec()

    # Public API

    def on_settings_requested(self, handler) -> None:
        if self._menu_builder.settings_action:
            self._menu_builder.settings_action.triggered.connect(handler)

    def sync_recording_status_from_engine(self, status: str) -> None:
        """Sync workspace state with background transcription engine status.

        ORCHESTRATION PRIVILEGE (Invariant 8):
        This is the ONLY method in MainWindow allowed to push engine state to UI.
        """
        match status:
            case "recording":
                self._on_view_changed(VIEW_TRANSCRIBE)
            case "transcribing":
                pass
            case "idle" | "error" | _:
                pass

    def update_audio_level(self, level: float) -> None:
        """Route audio levels to the transcribe view if active."""
        if hasattr(self, "view_transcribe") and self.view_host.get_current_view_id() == VIEW_TRANSCRIBE:
             self.view_transcribe.set_audio_level(level)

    def display_transcription(self, entry: HistoryEntry) -> None:
        # Debounce metrics refresh to avoid blocking on every transcript
        self._metrics_refresh_timer.start()
        # Optionally switch to edit view to show result
        # self._on_view_changed(VIEW_EDIT) # Disabled for now to prevent jarring switches

    def show_and_raise(self) -> None:
        self.show()
        self.showNormal()

        screen = QGuiApplication.primaryScreen()
        if screen:
            screen_geo = screen.availableGeometry()
            if not screen_geo.contains(self.geometry().center()):
                self.move(
                    screen_geo.center().x() - self.width() // 2,
                    screen_geo.center().y() - self.height() // 2,
                )

        self.raise_()
        self.activateWindow()

    def _debounced_metrics_refresh(self) -> None:
        """Refresh metrics with debouncing to prevent blocking on rapid transcripts."""
        if hasattr(self, "_metrics_refresh_timer"):
            self._metrics_refresh_timer.start()

    # History operations

    def _export_history(self) -> None:
        try:
            if not self.history_manager:
                return

            from ui.widgets.dialogs import ExportDialog

            dialog = ExportDialog(self)
            if dialog.exec():
                file_path, fmt = dialog.get_export_path()

                success = self.history_manager.export_to_file(file_path, fmt)

                if success:
                    MessageDialog(
                        self,
                        title="Export Successful",
                        message=f"History exported to:\n{file_path}",
                        button_text="OK",
                    ).exec()
                else:
                    show_error_dialog(
                        title="Export Failed",
                        message="Could not export history. Check logs for details.",
                        parent=self,
                    )
        except Exception as e:
            logger.exception("Error exporting history")
            show_error_dialog(
                title="Export Error",
                message=f"Failed to export history: {e}",
                parent=self,
            )

    def _clear_all_history(self) -> None:
        """Clear all transcription history."""
        try:
            dialog = ConfirmationDialog(
                self,
                title="Clear History",
                message=(
                    "Are you sure you want to delete all transcription history?\n\n"
                    "This action cannot be undone."
                ),
                confirm_text="Delete All",
                cancel_text="Cancel",
                is_destructive=True,
            )

            if dialog.exec() == QDialog.DialogCode.Accepted:
                if self.history_manager:
                    self.history_manager.clear()
                self.metrics_strip.refresh()
                if hasattr(self, "view_recent"):
                     # RecentView should refresh itself via history signals usually
                     pass
        except Exception:
            logger.exception("Error clearing history")

    # Resize slots removed.


    # Sidebar resize handling - Deprecated


    # Position logic removed


    def _switch_to_history(self) -> None:
        """Switch to Recent View (History)."""
        self._on_view_changed(VIEW_RECENT)

    # Note: Sidebar logic removed.
    def _toggle_sidebar(self) -> None:
        pass

    # State persistence

    def _restore_state(self) -> None:
        geometry = self.settings.value("geometry")

        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(WindowSize.BASE, WindowSize.BASE)
            self._center_on_screen()

        metrics_collapsed = self.settings.value("metrics_collapsed", False)
        if metrics_collapsed == "true" or metrics_collapsed is True:
            self.metrics_strip.set_collapsed(True)

    def _save_state(self) -> None:
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("metrics_collapsed", self.metrics_strip.is_collapsed())

    def _center_on_screen(self) -> None:
        screen = self.screen().availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(screen.center())
        self.move(frame.topLeft())

    def closeEvent(self, event) -> None:
        self._save_state()
        self.windowCloseRequested.emit()
        event.accept()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Sidebar resize logic removed.

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.WindowStateChange:
            if hasattr(self, "title_bar"):
                self.title_bar.sync_state()
        super().changeEvent(event)
