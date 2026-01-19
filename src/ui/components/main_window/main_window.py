"""
MainWindow - Primary application window for Vociferous.

Integrates Icon Rail, main workspace, and metrics strip in a responsive layout.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from src.core.resource_manager import ResourceManager
from PyQt6.QtCore import (
    QEvent,
    QSettings,
    Qt,
    QTimer,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import (
    QCloseEvent,
    QResizeEvent,
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

from src.ui.components.main_window.intent_feedback import IntentFeedbackHandler

# from src.ui.components.main_window.main_window_styles import get_combined_stylesheet
from src.ui.widgets.dialogs.blocking_overlay import BlockingOverlay
from src.ui.components.title_bar import TitleBar
from src.ui.constants import (
    WorkspaceState,
)
from src.ui.constants.dimensions import MIN_WIDTH, MIN_HEIGHT, BASE
from src.ui.widgets.dialogs import ConfirmationDialog, MessageDialog, show_error_dialog

# New shell components
from src.ui.components.main_window.icon_rail import IconRail
from src.ui.components.main_window.view_host import ViewHost
from src.ui.components.main_window.action_dock import ActionDock

# Views
from src.ui.views.transcribe_view import TranscribeView
from src.ui.views.history_view import HistoryView
from src.ui.views.projects_view import ProjectsView
from src.ui.views.search_view import SearchView
from src.ui.views.refine_view import RefineView
from src.ui.views.edit_view import EditView
from src.ui.views.settings_view import SettingsView
from src.ui.views.user_view import UserView
from src.ui.constants.view_ids import (
    VIEW_TRANSCRIBE,
    VIEW_HISTORY,
    VIEW_PROJECTS,
    VIEW_SEARCH,
    VIEW_REFINE,
    VIEW_EDIT,
    VIEW_SETTINGS,
    VIEW_USER,
)
from src.ui.interaction.intents import (
    InteractionIntent,
    NavigateIntent,
    ViewTranscriptIntent,
    BeginRecordingIntent,
    StopRecordingIntent,
    CancelRecordingIntent,
)

if TYPE_CHECKING:
    from src.database.history_manager import HistoryEntry, HistoryManager
    from src.core.command_bus import CommandBus

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
        intent_dispatched(InteractionIntent): Core event bus
        window_close_requested(): Window is closing
    """

    intent_dispatched = pyqtSignal(object)

    window_close_requested = pyqtSignal()
    # Legacy signals - deprecated
    cancel_recording_requested = pyqtSignal()
    start_recording_requested = pyqtSignal()
    stop_recording_requested = pyqtSignal()

    motd_refresh_requested = pyqtSignal()
    refinement_requested = pyqtSignal(
        int, str, str, str
    )  # id, text, profile, user_instruct

    def __init__(
        self,
        history_manager: HistoryManager | None = None,
        key_listener: Any | None = None,
        command_bus: CommandBus | None = None,
    ) -> None:
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.settings = QSettings("Vociferous", "MainWindow")
        self.history_manager = history_manager
        self.key_listener = key_listener
        self.command_bus = command_bus

        # Custom title bar (no menu bar needed)
        self.title_bar = TitleBar(self)

        # Debounce timer for metrics refresh (avoid blocking on rapid transcripts)
        self._metrics_refresh_timer = QTimer()
        self._metrics_refresh_timer.setSingleShot(True)
        self._metrics_refresh_timer.setInterval(1000)  # 1s debounce

        self._current_view_id = VIEW_TRANSCRIBE  # Default view
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
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)

        # Title bar as menu widget (no menu bar anymore)
        self.setMenuWidget(self.title_bar)

        # Central widget container
        central = QWidget(self)
        central.setObjectName("centralWidget")
        central.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
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

        # 2. Content Column (Views + ActionDock)
        content_column = QVBoxLayout()
        content_column.setContentsMargins(0, 0, 0, 0)
        content_column.setSpacing(0)

        # 2.1 View Host (The stack of screens)
        self.view_host = ViewHost()
        self.view_host.view_changed.connect(self._on_view_changed)

        # 2.2 Action Dock (Contextual Actions)
        self.action_dock = ActionDock()

        # Build Layout
        content_column.addWidget(self.view_host, 1)  # Expanding
        content_column.addWidget(self.action_dock, 0)  # Fixed height

        container_layout.addLayout(content_column, 1)
        main_layout.addLayout(container_layout)

        central.setLayout(main_layout)
        self.setCentralWidget(central)
        # self.setStyleSheet(get_combined_stylesheet()) -> Moved to ApplicationCoordinator

        # Status bar for intent feedback
        self._status_bar = self.statusBar()
        self._status_bar.setSizeGripEnabled(True)
        self._status_bar.hide()

        self._status_label = QLabel()
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_bar.addWidget(self._status_label, 1)

        # Intent feedback handler
        self._intent_feedback = IntentFeedbackHandler(self._status_bar, self)

        # Blocking Overlay (Initially hidden)
        self._blocking_overlay = BlockingOverlay(self)
        self._blocking_overlay.resize(self.size())

        # Initialize views (Must be after ActionDock and ViewHost)
        self._init_views()

    def set_app_busy(
        self, is_busy: bool, message: str = "", title: str = "System Busy"
    ) -> None:
        """Block or unblock user interaction with the entire window."""
        if is_busy:
            self._blocking_overlay.show_message(message, title=title)
            self.setCursor(Qt.CursorShape.WaitCursor)
        else:
            self._blocking_overlay.hide()
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def launch_onboarding(self) -> bool:
        """
        Launch the first-run onboarding wizard.
        Returns: True if completed, False if cancelled.
        """
        try:
            from src.ui.components.onboarding.onboarding_window import OnboardingWindow
            from src.ui.constants import WorkspaceState

            wizard = OnboardingWindow(key_listener=self.key_listener, parent=self)

            # Track cancellation
            cancelled = False

            def on_cancel() -> None:
                nonlocal cancelled
                cancelled = True
                wizard.close()

            wizard.cancelled.connect(on_cancel)

            result = wizard.exec() == QDialog.DialogCode.Accepted

            # If cancelled via close button, result will be False and cancelled will be True
            if cancelled:
                return False

            if result and hasattr(self, "view_transcribe"):
                # Refresh greeting immediately if in IDLE state
                workspace = self.view_transcribe.workspace
                if workspace.get_state() == WorkspaceState.IDLE and hasattr(
                    workspace, "header"
                ):
                    workspace.header.update_for_idle()

            return result
        except Exception:
            logger.exception("Failed to launch onboarding")
            return False

    def _init_views(self) -> None:
        """Instantiate and register all application views."""
        # Instantiate
        self.view_transcribe = TranscribeView(self.history_manager)
        self.view_transcribe.edit_normalized_text.connect(
            self._on_transcribe_view_text_edited
        )
        self.view_transcribe.edit_requested.connect(self._on_edit_view_requested)
        self.view_transcribe.refine_requested.connect(self._on_refine_view_requested)
        self.view_transcribe.delete_requested.connect(
            self._on_delete_transcript_requested
        )
        self.view_transcribe.motd_refresh_requested.connect(
            self.motd_refresh_requested.emit
        )

        # Connect workspace control signals directly to orchestrator signals
        # Transition: Map to Intents
        self.view_transcribe.workspace.start_requested.connect(
            lambda: self.dispatch_intent(BeginRecordingIntent())
        )
        self.view_transcribe.workspace.stop_requested.connect(
            lambda: self.dispatch_intent(StopRecordingIntent())
        )
        self.view_transcribe.workspace.cancel_requested.connect(
            lambda: self.dispatch_intent(CancelRecordingIntent())
        )

        self.view_history = HistoryView()
        if self.history_manager:
            self.view_history.set_history_manager(self.history_manager)

        self.view_history.edit_requested.connect(self._on_edit_view_requested)
        self.view_history.refine_requested.connect(self._on_refine_view_requested)
        self.view_history.delete_requested.connect(self._on_delete_from_history_view)

        self.view_projects = ProjectsView()
        if self.history_manager:
            self.view_projects.set_history_manager(self.history_manager)

        self.view_projects.edit_requested.connect(self._on_edit_view_requested)
        self.view_projects.refine_requested.connect(self._on_refine_view_requested)

        self.view_search = SearchView()
        if self.history_manager:
            self.view_search.set_history_manager(self.history_manager)

        self.view_search.edit_requested.connect(self._on_edit_view_requested)
        self.view_search.refine_requested.connect(self._on_refine_view_requested)
        self.view_search.delete_requested.connect(self._on_delete_from_history_view)

        self.view_refine = RefineView()
        self.view_refine.refinement_accepted.connect(self._on_refinement_accepted)
        self.view_refine.refinement_discarded.connect(self._on_refinement_discarded)
        self.view_refine.refinement_rerun_requested.connect(
            self._on_refinement_execution_requested
        )

        self.view_edit = EditView()
        self.view_edit.navigate_requested.connect(self._on_navigation_requested)
        self.view_edit.transcript_updated.connect(self._on_edit_transcript_updated)
        self.view_settings = SettingsView(self.key_listener)
        self.view_user = UserView()
        if self.history_manager:
            self.view_edit.set_history_manager(self.history_manager)
            self.view_user.set_history_manager(self.history_manager)

        # Connect SettingsView signals
        self.view_settings.export_history_requested.connect(self._export_history)
        self.view_settings.clear_all_history_requested.connect(self._clear_all_history)
        self.view_settings.restart_requested.connect(self._restart_application)
        self.view_settings.exit_requested.connect(self.close)

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

        # Activate default view immediately.
        # Note: We previously used QTimer.singleShot(0) to avoid layout issues,
        # but this caused test timing issues. We now rely on ActionDock's
        # improved repack logic and QGridLayout's stability.
        self._activate_default_view()

    def _activate_default_view(self) -> None:
        """Activate the default view once the event loop starts and layouts are ready."""
        try:
            self.icon_rail.set_active_view(VIEW_TRANSCRIBE)
            self.view_host.switch_to_view(VIEW_TRANSCRIBE)
        except Exception:
            logger.exception("Failed to activate default view")

    def dispatch_intent(self, intent: InteractionIntent) -> None:
        """Public entry point to inject an intent into the system."""
        self._on_interaction_intent(intent)

    @pyqtSlot(object)
    def _on_interaction_intent(self, intent: InteractionIntent) -> None:
        """Dispatcher for all intents bubbling up from UI components."""
        # logger.debug(f"MainWindow received intent: {intent}")

        # 1. Dispatch via Command Bus if available (Preferred Architecture)
        if self.command_bus:
            self.command_bus.dispatch(intent)
        else:
            # Fallback for legacy / testing without bus
            self.intent_dispatched.emit(intent)

        # 2. Handle View-Level Actions (Navigation) locally
        # Note: Ideally these should be handlers registered to the Bus too.
        # But keeping local handling for UI-specific logic is acceptable for now.
        if isinstance(intent, NavigateIntent):
            self._on_navigation_requested(intent.target_view_id)
        elif isinstance(intent, ViewTranscriptIntent):
            self._handle_view_transcript(intent)

        # 3. Handle Legacy mapping (Backward Compatibility for older listeners)
        # These will be removed once the Coordinator listens to intent_dispatched
        if isinstance(intent, BeginRecordingIntent):
            self.start_recording_requested.emit()
        elif isinstance(intent, StopRecordingIntent):
            self.stop_recording_requested.emit()
        elif isinstance(intent, CancelRecordingIntent):
            self.cancel_recording_requested.emit()

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
        # Update internal tracking
        self._current_view_id = view_id

        # Update Icon Rail visual state
        self.icon_rail.set_active_view(view_id)

        # Update Action Dock capability context
        current_view = self._view_map.get(view_id)

        # Hide action dock completely for User and Settings views
        if view_id in (VIEW_USER, VIEW_SETTINGS):
            self.action_dock.hide()
        elif current_view:
            self.action_dock.show()
            self.action_dock.set_active_view(current_view)

        # Transcribe View Reset Logic (Idle-State Reset Requirement)
        # If we navigated AWAY from Transcribe View, and it's holding a result (VIEWING or READY),
        # clear it so it's fresh when we return.
        if view_id != VIEW_TRANSCRIBE and hasattr(self, "view_transcribe"):
            workspace = self.view_transcribe.workspace
            # Clear if in VIEWING or READY states (not recording)
            if workspace.get_state() in (WorkspaceState.VIEWING, WorkspaceState.READY):
                workspace.clear_transcript()  # Reset to IDLE implicitly via clear? OR explicit reset?
                # TranscribeView.hideEvent handles some of this, but clearing content ensures IDLE.

    # Slot handlers

    @pyqtSlot(int, str)
    def _on_transcribe_view_text_edited(
        self, transcript_id: int, new_text: str
    ) -> None:
        """Handle text edits from the live transcription view."""
        if not self.history_manager:
            return

        try:
            self.history_manager.update_text(transcript_id, new_text)
            # Note: UI updates automatically via DatabaseSignalBridge
        except Exception as e:
            logger.exception("Failed to update transcript text from live view")
            show_error_dialog(
                "Update Failed", f"Could not save changes: {e}", parent=self
            )

    @pyqtSlot(int, str)
    def _on_edit_transcript_updated(self, transcript_id: int, new_text: str) -> None:
        """Handle transcript updates from EditView."""
        # Note: EditView already updated HistoryManager, which emitted DatabaseSignalBridge
        pass

    @pyqtSlot(int)
    def _on_edit_view_requested(self, transcript_id: int) -> None:
        """Switch to EditView for a specific transcript."""
        self.view_edit.set_origin_view(self._current_view_id)
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
    @pyqtSlot(int, str, str)
    def _on_refine_view_requested(
        self,
        transcript_id: int,
        profile: str = "BALANCED",
        user_instructions: str = "",
    ) -> None:
        """Switch to RefineView for a specific transcript."""
        if not self.history_manager:
            return

        entry = self.history_manager.get_entry(transcript_id)
        if not entry:
            logger.warning(f"Refine requested for missing ID {transcript_id}")
            return

        self.view_host.switch_to_view(VIEW_REFINE)

        # Load data (Draft Mode - Do not start immediately)
        self.view_refine.load_transcript_by_id(transcript_id, entry.text)
        # Note: We do NOT emit refinement_requested here. User must press "Refine" in the view.

    @pyqtSlot(int, str, str)
    def _on_refinement_execution_requested(
        self,
        transcript_id: int,
        profile: str,
        user_instructions: str,
    ) -> None:
        """Actually trigger the backend refinement process."""
        if not self.history_manager:
            return

        entry = self.history_manager.get_entry(transcript_id)
        if not entry:
            return

        self.view_refine.set_loading(True)
        self.refinement_requested.emit(
            transcript_id, entry.text, profile, user_instructions
        )

    @pyqtSlot(int, str)
    def on_refinement_complete(self, transcript_id: int, refined_text: str) -> None:
        """Handle successful refinement from backend."""
        # Ensure we are on the refine view? Or just update it?
        # If the user navigated away, we might not want to snap back, but updating the view is safe.
        if self.history_manager:
            original_entry = self.history_manager.get_entry(transcript_id)
            if original_entry:
                self.view_refine.set_comparison(
                    transcript_id, original_entry.text, refined_text
                )
        else:
            # Fallback if no history manager (unlikely)
            self.view_refine.set_refinement_result(refined_text)  # hypothetical helper?

        # This clears the loading overlay
        self.view_refine.set_loading(False)

    @pyqtSlot(int, str)
    def _on_refinement_accepted(self, transcript_id: int, refined_text: str) -> None:
        """Apply the refinement to the database."""
        if self.history_manager:
            self.history_manager.update_normalized_text(transcript_id, refined_text)

        # Note: UI updates via DatabaseSignalBridge
        self.view_host.switch_to_view(VIEW_HISTORY)

    @pyqtSlot()
    def _on_refinement_discarded(self) -> None:
        self.view_host.switch_to_view(VIEW_HISTORY)

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
    def _on_delete_transcript_requested(self) -> None:
        """Handle delete request from Transcribe View with confirmation."""
        if not self.history_manager or not hasattr(self, "view_transcribe"):
            return

        timestamp = self.view_transcribe.workspace.get_current_timestamp()
        if not timestamp:
            return

        dialog = ConfirmationDialog(
            self,
            title="Delete Transcript",
            message="Are you sure you want to delete this transcript? This action cannot be undone.",
            confirm_text="Delete",
            cancel_text="Cancel",
            is_destructive=True,
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.history_manager.delete_entry(timestamp)
                self.view_transcribe.workspace.clear_transcript()
                # Note: UI updates via DatabaseSignalBridge
                logger.info(f"Deleted transcript: {timestamp}")
            except Exception as e:
                logger.exception("Failed to delete transcript")
                from src.ui.widgets.dialogs import show_error_dialog

                show_error_dialog(
                    "Delete Error",
                    f"Failed to delete transcript: {e}",
                    parent=self,
                )

    @pyqtSlot(list)
    def _on_delete_from_history_view(self, transcript_ids: list[int]) -> None:
        """Handle delete request from HistoryView with confirmation."""
        if not self.history_manager or not transcript_ids:
            return

        count = len(transcript_ids)
        if count == 1:
            entry = self.history_manager.get_entry(transcript_ids[0])
            if not entry:
                return

            from src.ui.utils.history_utils import format_preview

            preview = format_preview(entry.text, max_length=50)
            message = f'Are you sure you want to delete this transcript?\n\n"{preview}"\n\nThis action cannot be undone.'
            title = "Delete Transcript"
        else:
            message = f"Are you sure you want to delete {count} selected transcripts?\n\nThis action cannot be undone."
            title = f"Delete {count} Transcripts"

        dialog = ConfirmationDialog(
            self,
            title=title,
            message=message,
            confirm_text="Delete",
            cancel_text="Cancel",
            is_destructive=True,
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            from src.database.signal_bridge import DatabaseSignalBridge
            from src.database.events import ChangeAction

            try:
                with DatabaseSignalBridge().signal_group(
                    "transcription", ChangeAction.DELETED
                ):
                    for tid in transcript_ids:
                        entry = self.history_manager.get_entry(tid)
                        if entry:
                            self.history_manager.delete_entry(entry.timestamp)

                # Note: UI updates via DatabaseSignalBridge
                logger.info(f"Deleted {len(transcript_ids)} transcripts")
            except Exception as e:
                logger.exception("Failed to delete transcripts")
                from src.ui.widgets.dialogs import show_error_dialog

                show_error_dialog(
                    "Delete Error",
                    f"Failed to delete transcripts: {e}",
                    parent=self,
                )

    def show_refinement(self, transcript_id: int, original: str, refined: str) -> None:
        """Switch to RefineView and show comparison."""
        self.view_host.switch_to_view(VIEW_REFINE)
        if hasattr(self.view_refine, "set_comparison"):
            self.view_refine.set_comparison(transcript_id, original, refined)

    def _show_about_dialog(self) -> None:
        """Show the About Vociferous info (now in User View)."""
        # Navigate to User View instead of showing dialog
        self.view_host.switch_to_view(VIEW_USER)

    def _restart_application(self) -> None:
        """Restart the application by launching the entry point script."""
        import os
        import subprocess
        import sys
        import time

        try:
            project_root = ResourceManager.get_app_root()

            # Target the ./vociferous entry point wrapper
            vociferous_script = str(project_root / "vociferous")
            vociferous_script = os.path.join(project_root, "vociferous")

            if os.path.exists(vociferous_script):
                logger.info(f"Restarting via entry point: {vociferous_script}")
                # Close the current application first, allow shutdown to complete
                self.close()
                # Small delay to ensure old instance releases lock
                time.sleep(0.5)
                # Now spawn the new instance
                subprocess.Popen(
                    [sys.executable, vociferous_script],
                    start_new_session=True,
                )
            else:
                # Fallback: launch src/main.py directly
                main_script = os.path.join(project_root, "src", "main.py")
                logger.warning(f"Entry point not found, falling back to: {main_script}")
                self.close()
                time.sleep(0.5)
                subprocess.Popen(
                    [sys.executable, main_script],
                    start_new_session=True,
                )
        except Exception as e:
            logger.exception("Failed to restart application")
            show_error_dialog(
                title="Restart Error",
                message=f"Failed to restart: {e}",
                parent=self,
            )

    # Public API

    def is_recording(self) -> bool:
        """Check if currently in recording state."""
        if not hasattr(self, "view_transcribe"):
            return False
        return self.view_transcribe.workspace.get_state() == WorkspaceState.RECORDING

    def set_recording_state(self, is_recording: bool) -> None:
        """
        Set recording state manually. (Legacy/Coordinator Compatibility)

        Maps boolean state to engine status strings.
        """
        status = "recording" if is_recording else "idle"
        self.sync_recording_status_from_engine(status)

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
                # Guard: Allow transition to RECORDING from any non-editing state (Edit Safety)
                if current_state in (
                    WorkspaceState.IDLE,
                    WorkspaceState.VIEWING,
                    WorkspaceState.READY,
                ):
                    self.view_host.switch_to_view(VIEW_TRANSCRIBE)
                    self.view_transcribe.update_for_recording_state(True)
            case "transcribing":
                # Explicitly transition to TRANSCRIBING state
                if current_state == WorkspaceState.RECORDING:
                    self.view_transcribe.workspace.set_state(
                        WorkspaceState.TRANSCRIBING
                    )
                self.view_transcribe.pause_visualization()
            case "idle" | "error":
                # Allow transition out of recording or transcribing
                if current_state in (
                    WorkspaceState.RECORDING,
                    WorkspaceState.TRANSCRIBING,
                ):
                    self.view_transcribe.update_for_recording_state(False)
            case _:
                # Ignore intermediate statuses like "model_ready" or "loading_model"
                # which are handled via busy overlay or internal state.
                pass

    def update_audio_level(self, level: float) -> None:
        """Route audio levels to the transcribe view if active."""
        if (
            hasattr(self, "view_transcribe")
            and self.view_host.get_current_view_id() == VIEW_TRANSCRIBE
        ):
            self.view_transcribe.set_audio_level(level)

    def update_audio_spectrum(self, bands: list[float]) -> None:
        """Route FFT spectrum to the transcribe view if active."""
        if (
            hasattr(self, "view_transcribe")
            and self.view_host.get_current_view_id() == VIEW_TRANSCRIBE
        ):
            self.view_transcribe.set_audio_spectrum(bands)

    def set_motd(self, text: str) -> None:
        """Set Message of the Day in workspace header."""
        if (
            hasattr(self, "view_transcribe")
            and hasattr(self.view_transcribe, "workspace")
            and hasattr(self.view_transcribe.workspace, "header")
        ):
            self.view_transcribe.workspace.header.set_motd(text)

    def on_transcription_complete(self, entry: HistoryEntry) -> None:
        """Handle newly created transcription entry."""
        # 1. Debounced metrics refresh (ensure UI reflects new data)
        self._metrics_refresh_timer.start()

        # 2. Show in TranscribeView for immediate editing
        if hasattr(self, "view_transcribe"):
            # This ensures the user sees what they just said immediately
            # without having to find it in the history list.
            self.view_transcribe.display_new_transcript(entry)

    @pyqtSlot(object)
    def update_refinement_state(self, state: object) -> None:
        """Route SLM state updates to Settings View."""
        from src.ui.constants.view_ids import VIEW_SETTINGS

        # Feedback for user
        # Avoid spamming simple states, focus on transitions
        if str(state.value) in [
            "Downloading Source Model",
            "Converting Model",
            "Error",
        ]:
            self._intent_feedback.show_message(f"Refinement: {state.value}", 5000)

        # Update Settings View
        if hasattr(self, "view_host"):
            settings_view = self.view_host.get_view(VIEW_SETTINGS)
            # Use getattr to avoid import check issues or if view not fully typed
            handler = getattr(settings_view, "update_refinement_state", None)
            if handler:
                handler(state)

    @pyqtSlot(str)
    def on_refinement_status_message(self, message: str) -> None:
        """Handle status messages from SLM service."""
        # Show in status bar
        self._intent_feedback.on_refinement_status_message(message)

        # Pass to Settings View
        from src.ui.constants.view_ids import VIEW_SETTINGS

        if hasattr(self, "view_host"):
            settings_view = self.view_host.get_view(VIEW_SETTINGS)
            handler = getattr(settings_view, "update_refinement_status", None)
            if handler:
                handler(message)

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

            from src.ui.widgets.dialogs import ExportDialog

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
            self.resize(BASE, BASE)
            self._center_on_screen()

    def _save_state(self) -> None:
        self.settings.setValue("geometry", self.saveGeometry())

    def _cleanup_children(self) -> None:
        """
        Recursively clean up all child views and components.

        Per cleanup protocol, parent widgets are responsible for
        triggering cleanup() on children that manage resources.

        This is called before window close to ensure:
        - Timers are stopped
        - Animations are halted
        - Threads are joined
        - External connections are closed
        """
        import logging

        # Clean up all registered views
        for view in [
            self.view_transcribe,
            self.view_history,
            self.view_projects,
            self.view_search,
            self.view_refine,
            self.view_edit,
            self.view_settings,
            self.view_user,
        ]:
            if hasattr(view, "cleanup") and callable(view.cleanup):
                try:
                    view.cleanup()
                except Exception as e:
                    logging.error(
                        f"Error cleaning up view {view.__class__.__name__}: {e}"
                    )

        # Clean up shell components
        for component in [self.icon_rail, self.action_dock, self.title_bar]:
            if hasattr(component, "cleanup") and callable(component.cleanup):
                try:
                    component.cleanup()
                except Exception as e:
                    logging.error(
                        f"Error cleaning up component {component.__class__.__name__}: {e}"
                    )

        # Clean up blocking overlay
        if hasattr(self, "_blocking_overlay") and hasattr(
            self._blocking_overlay, "cleanup"
        ):
            try:
                self._blocking_overlay.cleanup()
            except Exception as e:
                logging.error(f"Error cleaning up blocking overlay: {e}")

    def show_settings(self) -> None:
        """Switch to the settings view."""
        self.view_host.switch_to_view(VIEW_SETTINGS)

    def _center_on_screen(self) -> None:
        screen = self.screen().availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(screen.center())
        self.move(frame.topLeft())

    def closeEvent(self, event: QCloseEvent) -> None:
        # Clean up all children before closing
        self._cleanup_children()

        self._save_state()
        self.window_close_requested.emit()
        event.accept()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_blocking_overlay"):
            self._blocking_overlay.resize(self.size())

    def changeEvent(self, event: QEvent) -> None:
        """Handle window state changes, including taskbar interactions."""
        if event.type() == QEvent.Type.WindowStateChange:
            if hasattr(self, "title_bar"):
                self.title_bar.sync_state()
        elif event.type() == QEvent.Type.ActivationChange:
            # Handle taskbar clicks on frameless windows
            if self.isActiveWindow() and self.isMinimized():
                self.showNormal()
                self.activateWindow()
                self.raise_()
        super().changeEvent(event)
