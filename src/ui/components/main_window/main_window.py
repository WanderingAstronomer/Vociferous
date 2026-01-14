"""
MainWindow - Primary application window for Vociferous.

Integrates Icon Rail, main workspace, and metrics strip in a responsive layout.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import (
    QEvent,
    QSettings,
    Qt,
    QTimer,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import (
    QGuiApplication,
)
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.components.main_window.intent_feedback import IntentFeedbackHandler
from ui.components.main_window.main_window_styles import get_combined_stylesheet
from ui.components.title_bar import TitleBar
from ui.constants import (
    WindowSize,
    WorkspaceState,
)
from ui.widgets.dialogs import ConfirmationDialog, MessageDialog, show_error_dialog
from ui.widgets.metrics_strip.metrics_strip import MetricsStrip

# New shell components
from ui.components.icon_rail import IconRail
from ui.components.view_host import ViewHost
from ui.components.action_dock import ActionDock

# Views
from ui.views.transcribe_view import TranscribeView
from ui.views.history_view import HistoryView
from ui.views.projects_view import ProjectsView
from ui.views.search_view import SearchView
from ui.views.refine_view import RefineView
from ui.views.edit_view import EditView
from ui.views.settings_view import SettingsView
from ui.views.user_view import UserView
from ui.constants.view_ids import (
    VIEW_TRANSCRIBE, VIEW_HISTORY, VIEW_PROJECTS, VIEW_SEARCH, VIEW_REFINE, VIEW_EDIT,
    VIEW_SETTINGS, VIEW_USER
)
from ui.interaction.intents import InteractionIntent, NavigateIntent, ViewTranscriptIntent

if TYPE_CHECKING:
    from history_manager import HistoryEntry, HistoryManager

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """
    Primary application window with Icon Rail, workspace, and metrics strip.

    Layout:
    ┌─────────────────────────────────────────┐
    │              Title Bar                  │
    ├─────────┬───────────────────────────────┤
    │  Icon   │                               │
    │  Rail   │     Main Workspace            │
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

    def __init__(self, history_manager: HistoryManager | None = None, key_listener=None) -> None:
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)

        self.settings = QSettings("Vociferous", "MainWindow")
        self.history_manager = history_manager
        self.key_listener = key_listener

        # Custom title bar (no menu bar needed)
        self.title_bar = TitleBar(self)

        # Debounce timer for metrics refresh (avoid blocking on rapid transcripts)
        self._metrics_refresh_timer = QTimer()
        self._metrics_refresh_timer.setSingleShot(True)
        self._metrics_refresh_timer.setInterval(1000)  # 1s debounce

        self._init_ui()
        self._restore_state()

    def set_history_manager(self, manager: HistoryManager) -> None:
        """Inject history manager (used for testing or delayed initialization)."""
        self.history_manager = manager
        # Propagate to views if necessary - logic could be added here
        # For now, tests mainly rely on the accessible property

    def _init_ui(self) -> None:
        """Initialize the main UI layout."""
        self.setWindowTitle("Vociferous")
        self.setMinimumSize(WindowSize.MIN_WIDTH, WindowSize.MIN_HEIGHT)

        # Title bar as menu widget (no menu bar anymore)
        self.setMenuWidget(self.title_bar)

        # Central widget container
        central = QWidget(self)
        central.setObjectName("centralWidget")
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Main horizontal container (Rail | Content)
        container_layout = QHBoxLayout()
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # 1. Icon Rail (Navigation)
        self.icon_rail = IconRail()
        self.icon_rail.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )
        self.icon_rail.intent_emitted.connect(self._on_interaction_intent)
        container_layout.addWidget(self.icon_rail, 0)

        # 2. Content Column (Views + ActionDock + Metrics)
        content_column = QVBoxLayout()
        content_column.setContentsMargins(0, 0, 0, 0)
        content_column.setSpacing(0)

        # 2.1 View Host (The stack of screens)
        self.view_host = ViewHost()
        self.view_host.viewChanged.connect(self._on_view_changed)
        
        # 2.2 Action Dock (Contextual Actions)
        self.action_dock = ActionDock()

        # 2.3 Metrics Strip
        self.metrics_strip = MetricsStrip()
        if self.history_manager:
            self.metrics_strip.set_history_manager(self.history_manager)

        # Build Layout
        content_column.addWidget(self.view_host, 1) # Expanding
        content_column.addWidget(self.action_dock, 0) # Fixed height
        content_column.addWidget(self.metrics_strip, 0) # Fixed height

        container_layout.addLayout(content_column, 1)
        main_layout.addLayout(container_layout)

        # Connect debounce timer
        self._metrics_refresh_timer.timeout.connect(self.metrics_strip.refresh)

        central.setLayout(main_layout)
        self.setCentralWidget(central)
        self.setStyleSheet(get_combined_stylesheet())

        # Status bar for intent feedback
        self._status_bar = self.statusBar()
        self._status_bar.setSizeGripEnabled(True)
        self._status_bar.hide()
        
        self._status_label = QLabel()
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_bar.addWidget(self._status_label, 1)

        # Intent feedback handler
        self._intent_feedback = IntentFeedbackHandler(self._status_bar, self)
        
        # Initialize views (Must be after ActionDock and ViewHost)
        self._init_views()

    def _init_views(self) -> None:
        """Instantiate and register all application views."""
        # Instantiate
        self.view_transcribe = TranscribeView(self.history_manager)
        self.view_transcribe.editNormalizedText.connect(self._on_transcribe_view_text_edited)
        
        # Connect workspace control signals directly to orchestrator signals
        # This restores the link broken by previous TranscribeView implementation
        self.view_transcribe.workspace.startRequested.connect(self.startRecordingRequested.emit)
        self.view_transcribe.workspace.stopRequested.connect(self.stopRecordingRequested.emit)
        self.view_transcribe.workspace.cancelRequested.connect(self.cancelRecordingRequested.emit)
        
        self.view_history = HistoryView() 
        if self.history_manager:
            self.view_history.set_history_manager(self.history_manager)
            
        self.view_history.editRequested.connect(self._on_edit_view_requested)
        self.view_history.refineRequested.connect(self._on_refine_view_requested)
        # Refine requested via View -> passes to validation -> Orchestrator?
        # Typically Refine needs "Text" + "Profile". 
        # For now, let's just use the Orchestrator signal if possible, or a local handler.
        # But HistoryView emits (id). We need to show the refinement dialog first? 
        # Or does "Refine" action jump to a specific flow?
        # The Orchestrator has `_on_refine_requested`.
        # Let's direct connect for now to a stub handler or MainWindow handler.
            
        self.view_projects = ProjectsView()
        if self.history_manager:
            self.view_projects.set_history_manager(self.history_manager)

        self.view_search = SearchView()
        self.view_refine = RefineView()
        self.view_edit = EditView()
        self.view_settings = SettingsView(self.key_listener)
        self.view_user = UserView()
        if self.history_manager:
            self.view_edit.set_history_manager(self.history_manager)
            self.view_user.set_history_manager(self.history_manager)
        
        # Connect SettingsView signals
        self.view_settings.exportHistoryRequested.connect(self._export_history)
        self.view_settings.clearAllHistoryRequested.connect(self._clear_all_history)
        self.view_settings.restartRequested.connect(self._restart_application)
        self.view_settings.exitRequested.connect(self.close)
        
        # Register
        self.view_host.register_view(self.view_transcribe, VIEW_TRANSCRIBE)
        self.view_host.register_view(self.view_history, VIEW_HISTORY)
        self.view_host.register_view(self.view_projects, VIEW_PROJECTS)
        self.view_host.register_view(self.view_search, VIEW_SEARCH)
        self.view_host.register_view(self.view_refine, VIEW_REFINE)
        self.view_host.register_view(self.view_edit, VIEW_EDIT)
        self.view_host.register_view(self.view_settings, VIEW_SETTINGS)
        self.view_host.register_view(self.view_user, VIEW_USER)
        
        # Map for ActionGrid lookup
        self._view_map = {
            VIEW_TRANSCRIBE: self.view_transcribe,
            VIEW_HISTORY: self.view_history,
            VIEW_PROJECTS: self.view_projects,
            VIEW_SEARCH: self.view_search,
            VIEW_REFINE: self.view_refine,
            VIEW_EDIT: self.view_edit,
            VIEW_SETTINGS: self.view_settings,
            VIEW_USER: self.view_user,
        }

        # Set default view
        # Triggering switch_to_view will emit signal and run _on_view_changed
        self.icon_rail.set_active_view(VIEW_TRANSCRIBE)
        self.view_host.switch_to_view(VIEW_TRANSCRIBE)

    @pyqtSlot(InteractionIntent)
    def _on_interaction_intent(self, intent: InteractionIntent) -> None:
        """Dispatcher for all intents bubbling up from UI components."""
        if isinstance(intent, NavigateIntent):
            self._on_navigation_requested(intent.target_view_id)
        elif isinstance(intent, ViewTranscriptIntent):
            self._handle_view_transcript(intent)

    def _handle_view_transcript(self, intent: ViewTranscriptIntent) -> None:
        """Handle request to view a specific transcript."""
        # Switch to Transcribe view (View/Edit mode)
        self.view_host.switch_to_view(VIEW_TRANSCRIBE)
        
        # Load the data into the view
        if hasattr(self, "view_transcribe"):
            # Ensure we're targeting the right view instance
            self.view_transcribe.load_transcript(intent.text, intent.timestamp)

    @pyqtSlot(str)
    def _on_navigation_requested(self, view_id: str) -> None:
        """Handle navigation request from IconRail or other sources."""
        self.view_host.switch_to_view(view_id)

    @pyqtSlot(str)
    def _on_view_changed(self, view_id: str) -> None:
        """Handle authoritative view change event."""
        # Update Icon Rail visual state
        self.icon_rail.set_active_view(view_id)
        
        # Update Action Dock capability context
        current_view = self._view_map.get(view_id)
        if current_view:
            self.action_dock.set_active_view(current_view)

    # Slot handlers

    @pyqtSlot(int, str)
    def _on_transcribe_view_text_edited(self, transcript_id: int, new_text: str) -> None:
        """Handle text edits from the live transcription view."""
        if not self.history_manager:
            return
        
        try:
            self.history_manager.update_text(transcript_id, new_text)
            self.view_history.refresh()
            if hasattr(self, "view_projects"):
                self.view_projects.refresh()
        except Exception as e:
            logger.exception("Failed to update transcript text from live view")
            show_error_dialog("Update Failed", f"Could not save changes: {e}", parent=self)

    @pyqtSlot(int)
    def _on_edit_view_requested(self, transcript_id: int) -> None:
        """Switch to EditView for a specific transcript."""
        self.view_host.switch_to_view(VIEW_EDIT)
        if hasattr(self.view_edit, "load_transcript_by_id"):
             self.view_edit.load_transcript_by_id(transcript_id)


    def load_entry_for_edit(self, text: str, timestamp: str) -> None:
        """Load an entry into the edit view by timestamp."""
        if not self.history_manager:
            return
            
        # Find ID by timestamp
        transcript_id = self.history_manager.get_id_by_timestamp(timestamp)
        if transcript_id is not None:
            self._on_edit_view_requested(transcript_id)
        else:
            logger.warning(f"Could not find transcript for timestamp {timestamp}")

    @pyqtSlot(int)
    def _on_refine_view_requested(self, transcript_id: int) -> None:
        """Switch to RefineView for a specific transcript."""
        self.view_host.switch_to_view(VIEW_REFINE)
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
        self.view_host.switch_to_view(VIEW_REFINE)
        if hasattr(self.view_refine, "set_comparison"):
            self.view_refine.set_comparison(transcript_id, original, refined)

    def _show_about_dialog(self) -> None:
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
        """Show the About Vociferous info (now in User View)."""
        # Navigate to User View instead of showing dialog
        self.view_host.switch_to_view(VIEW_USER)

    def _restart_application(self) -> None:
        """Show the Metrics Calculations explanation dialog (now in User View)."""
        # Navigate to User View instead of showing dialog
        self.view_host.switch_to_view(VIEW_USER)

    # Public API
    
    def sync_recording_status_from_engine(self, status: str) -> None:
        """Sync workspace state with background transcription engine status.

        ORCHESTRATION PRIVILEGE (Invariant 8):
        This is the ONLY method in MainWindow allowed to push engine state to UI.
        """
        if not hasattr(self, "view_transcribe"):
             return
             
        current_state = self.view_transcribe.workspace.get_state()
        
        match status:
            case "recording":
                # Guard: Only IDLE -> RECORDING (Edit Safety)
                if current_state == WorkspaceState.IDLE or self.view_transcribe.workspace.get_state() == WorkspaceState.IDLE:
                    self.view_host.switch_to_view(VIEW_TRANSCRIBE)
                    self.view_transcribe.update_for_recording_state(True)
            case "transcribing":
                pass
            case "idle" | "error" | _:
                # Guard: Only RECORDING -> IDLE (Edit Safety)
                if current_state == WorkspaceState.RECORDING or self.view_transcribe.workspace.get_state() == WorkspaceState.RECORDING:
                    self.view_transcribe.update_for_recording_state(False)


    def update_audio_level(self, level: float) -> None:
        """Route audio levels to the transcribe view if active."""
        if hasattr(self, "view_transcribe") and self.view_host.get_current_view_id() == VIEW_TRANSCRIBE:
             self.view_transcribe.set_audio_level(level)

    def display_transcription(self, entry: HistoryEntry) -> None:
        # Debounce metrics refresh to avoid blocking on every transcript
        self._metrics_refresh_timer.start()
        
        # Show in TranscribeView for immediate editing
        if hasattr(self, "view_transcribe"):
             self.view_transcribe.load_transcript(entry.text, entry.timestamp)

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
                if hasattr(self, "view_history"):
                     # HistoryView should refresh itself via history signals usually
                     pass
        except Exception:
            logger.exception("Error clearing history")

    # Resize slots removed.

    # Position logic removed


    def _switch_to_history(self) -> None:
        """Switch to History View."""
        self.view_host.switch_to_view(VIEW_HISTORY)

    # State persistence

    def _restore_state(self) -> None:
        geometry = self.settings.value("geometry")

        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(WindowSize.BASE, WindowSize.BASE)
            self._center_on_screen()

        metrics_visible = self.settings.value("metrics_visible", True)
        if str(metrics_visible).lower() == "false":
            self.metrics_strip.hide()

    def _save_state(self) -> None:
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("metrics_visible", self.metrics_strip.isVisible())

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

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.WindowStateChange:
            if hasattr(self, "title_bar"):
                self.title_bar.sync_state()
        super().changeEvent(event)
