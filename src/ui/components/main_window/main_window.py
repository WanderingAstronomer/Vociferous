"""
MainWindow - Primary application window for Vociferous.

Integrates sidebar, main workspace, and metrics strip in a responsive layout.
"""

from __future__ import annotations

import logging
from pathlib import Path
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
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui.components.main_window.menu_builder import MenuBuilder
from ui.components.sidebar.sidebar_new import SidebarWidget
from ui.components.title_bar import TitleBar
from ui.components.workspace import MainWorkspace
from ui.constants import Colors, Dimensions, Spacing, Typography, WindowSize, WorkspaceState
from ui.interaction import IntentOutcome, IntentSource, ViewTranscriptIntent
from ui.widgets.dialogs import ConfirmationDialog, MessageDialog, show_error_dialog
from ui.widgets.metrics_strip import MetricsStrip

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

        # Sidebar state
        self._sidebar_collapsed = False
        self._sidebar_expanded_width = Dimensions.SIDEBAR_MIN_WIDTH
        self._content_layout: QHBoxLayout | None = None
        self._initial_state_restored = False

        self._init_ui()
        self._create_menu_bar()
        self._restore_state()

    def _init_ui(self) -> None:
        """Initialize the main UI layout."""
        self.setWindowTitle("Vociferous")
        self.setMinimumSize(WindowSize.MIN_WIDTH, WindowSize.MIN_HEIGHT)

        # Styles are applied at app level via generate_unified_stylesheet()

        # Title bar as menu widget
        self.setMenuWidget(self.title_bar)

        # Central widget with outer padding
        central = QWidget(self)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(
            Spacing.APP_OUTER, Spacing.APP_OUTER, Spacing.APP_OUTER, Spacing.APP_OUTER
        )
        main_layout.setSpacing(Spacing.MAJOR_GAP)

        # Horizontal layout for sidebar and workspace
        self._content_layout = QHBoxLayout()
        self._content_layout.setSpacing(Spacing.MAJOR_GAP)

        # Sidebar with tabbed navigation
        self.sidebar = SidebarWidget(self.history_manager)
        self.sidebar.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )
        self.sidebar.entrySelected.connect(self._on_entry_selected)
        
        # Connect resize grip signals
        self.sidebar.resizeRequested.connect(self._on_sidebar_resize)
        self.sidebar.collapseRequested.connect(self._collapse_sidebar)
        self.sidebar.expandRequested.connect(self._expand_sidebar)
        
        # Floating expand button (shown when sidebar collapsed)
        self._expand_button = QToolButton(self)
        self._expand_button.setText("▶")
        self._expand_button.setFixedSize(20, 60)
        self._expand_button.setStyleSheet(f"""
            QToolButton {{
                background-color: {Colors.SURFACE_ALT};
                color: {Colors.PRIMARY};
                border: 1px solid {Colors.BORDER_LIGHT};
                border-radius: {Dimensions.BORDER_RADIUS_SM}px;
                font-size: {Typography.FONT_SIZE_SM}px;
            }}
            QToolButton:hover {{
                background-color: {Colors.HOVER_BG_SECTION};
                border-color: {Colors.PRIMARY};
            }}
        """)
        self._expand_button.setToolTip("Expand sidebar (Ctrl+B)")
        self._expand_button.clicked.connect(lambda: self._expand_sidebar())
        self._expand_button.hide()  # Hidden initially

        # Main workspace
        self.workspace = MainWorkspace()
        self.workspace.set_history_manager(self.history_manager)
        self.workspace.startRequested.connect(self._on_start_requested)
        self.workspace.stopRequested.connect(self._on_stop_requested)
        self.workspace.cancelRequested.connect(self._on_cancel_requested)
        self.workspace.saveRequested.connect(self._on_save_requested)
        self.workspace.deleteRequested.connect(self._on_delete_requested)

        # Add widgets
        self._content_layout.addWidget(self.sidebar, 0)
        self._content_layout.addWidget(self.workspace, 1)

        main_layout.addLayout(self._content_layout, 1)

        # Metrics strip at bottom
        self.metrics_strip = MetricsStrip(self.history_manager)
        main_layout.addWidget(self.metrics_strip)

        central.setLayout(main_layout)
        self.setCentralWidget(central)

        # Hide status bar
        self.statusBar().hide()

    def _create_menu_bar(self) -> None:
        """Create menu bar with all menus."""
        self._menu_builder = MenuBuilder(self._menu_bar, self)
        self._menu_builder.build(
            on_exit=lambda: (self.close(), None)[1],
            on_export=self._export_history,
            on_clear=self._clear_all_history,
            on_toggle_metrics=self._toggle_metrics,
            on_focus_history=self.sidebar.focus_transcript_list,
            on_about=self._show_about_dialog,
            on_metrics_explanation=self._show_metrics_explanation,
        )

        # Connect metrics strip collapse signal
        self.metrics_strip.collapsedChanged.connect(self._on_metrics_collapsed_changed)

    # Slot handlers

    @pyqtSlot()
    def _on_start_requested(self) -> None:
        try:
            self.startRecordingRequested.emit()
        except Exception as e:
            logger.exception("Error in _on_start_requested")

    @pyqtSlot()
    def _on_stop_requested(self) -> None:
        try:
            self.stopRecordingRequested.emit()
        except Exception as e:
            logger.exception("Error in _on_stop_requested")

    @pyqtSlot()
    def _on_cancel_requested(self) -> None:
        """Handle cancel signal from workspace.
        
        Note: Workspace's _apply_cancel_recording already set state to IDLE.
        This handler only forwards to orchestrator.
        """
        try:
            self.cancelRecordingRequested.emit()
        except Exception as e:
            logger.exception("Error in _on_cancel_requested")

    @pyqtSlot(str)
    def _on_save_requested(self, text: str) -> None:
        try:
            timestamp = self.workspace.get_current_timestamp()
            if self.history_manager and timestamp:
                self.history_manager.update_entry(timestamp, text)
                self.sidebar.load_history()
                self.metrics_strip.refresh()
        except Exception as e:
            logger.exception("Error saving transcript")
            show_error_dialog(
                title="Save Error",
                message=f"Failed to save transcript: {e}",
                parent=self,
            )

    @pyqtSlot()
    def _on_delete_requested(self) -> None:
        """Handle delete signal from workspace.
        
        Phase 5: Workspace validated preconditions in _apply_delete_transcript.
        This handler shows confirmation, performs I/O, then clears workspace.
        """
        try:
            timestamp = self.workspace.get_current_timestamp()
            if not timestamp:
                return

            dialog = ConfirmationDialog(
                self,
                title="Delete Transcript",
                message="Are you sure you want to delete this transcript?",
                confirm_text="Delete",
                cancel_text="Cancel",
                is_destructive=True,
            )

            if dialog.exec() == QDialog.DialogCode.Accepted:
                if self.history_manager:
                    self.history_manager.delete_entry(timestamp)
                    self.sidebar.load_history()
                    self.metrics_strip.refresh()
                # Terminal state mutation: clear workspace after confirmed delete
                self.workspace.clear_transcript()
        except Exception as e:
            logger.exception("Error deleting transcript")
            show_error_dialog(
                title="Delete Error",
                message=f"Failed to delete transcript: {e}",
                parent=self,
            )

    @pyqtSlot(str, str)
    def _on_entry_selected(self, text: str, timestamp: str) -> None:
        """Handle sidebar entry selection via intent layer.
        
        Phase 5: Routes through ViewTranscriptIntent for authority consolidation.
        """
        try:
            intent = ViewTranscriptIntent(
                timestamp=timestamp,
                text=text,
                source=IntentSource.SIDEBAR,
            )
            result = self.workspace.handle_intent(intent)
            
            if result.outcome == IntentOutcome.REJECTED:
                logger.warning(f"ViewTranscriptIntent rejected: {result.reason}")
                # Could show error dialog here, but rejection during editing
                # is expected behavior (unsaved changes protection)
        except Exception as e:
            logger.exception("Error handling entry selection")
            show_error_dialog(
                title="Load Error",
                message=f"Failed to load transcript: {e}",
                parent=self,
            )

    def _toggle_metrics(self, checked: bool) -> None:
        try:
            if self.metrics_strip.is_collapsed() == checked:
                self.metrics_strip.toggle_collapse()
        except Exception as e:
            logger.exception("Error toggling metrics")

    @pyqtSlot(bool)
    def _on_metrics_collapsed_changed(self, collapsed: bool) -> None:
        try:
            if self._menu_builder.metrics_action:
                self._menu_builder.metrics_action.setChecked(not collapsed)
        except Exception:
            logger.exception("Error in _on_metrics_collapsed_changed")

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
        from ui.widgets.dialogs.metrics_explanation_dialog import MetricsExplanationDialog
        
        dialog = MetricsExplanationDialog(self)
        dialog.exec()

    # Public API

    def on_settings_requested(self, handler) -> None:
        if self._menu_builder.settings_action:
            self._menu_builder.settings_action.triggered.connect(handler)

    def update_transcription_status(self, status: str) -> None:
        """Sync workspace state with background transcription thread.
        
        This is ORCHESTRATION, not user interaction (Invariant 8).
        Called by main.py when ResultThread status changes.
        
        Safety: Only transitions IDLE↔RECORDING, never touches EDITING/VIEWING.
        """
        match status:
            case "recording":
                # Only set if idle - don't interrupt editing/viewing
                if self.workspace.get_state() == WorkspaceState.IDLE:
                    self.workspace.set_state(WorkspaceState.RECORDING)
            case "transcribing":
                self.workspace.show_transcribing_status()
            case "idle" | "error" | _:
                # Only reset if we were recording
                if self.workspace.get_state() == WorkspaceState.RECORDING:
                    self.workspace.set_state(WorkspaceState.IDLE)

    def display_transcription(self, entry: HistoryEntry) -> None:
        self.sidebar.add_entry(entry)
        self.workspace.display_new_transcript(entry)
        self.metrics_strip.refresh()

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

    @property
    def history_widget(self):
        return self.sidebar.transcript_list

    def load_entry_for_edit(self, text: str, timestamp: str) -> None:
        """Load an entry for editing via intent layer.
        
        Phase 5: Routes through ViewTranscriptIntent for authority consolidation.
        """
        try:
            intent = ViewTranscriptIntent(
                timestamp=timestamp,
                text=text,
                source=IntentSource.CONTROLS,
            )
            result = self.workspace.handle_intent(intent)
            
            if result.outcome == IntentOutcome.REJECTED:
                logger.warning(f"ViewTranscriptIntent rejected in load_entry_for_edit: {result.reason}")
        except Exception as e:
            logger.exception("Error loading entry for edit")
            show_error_dialog(
                title="Load Error",
                message=f"Failed to load entry: {e}",
                parent=self,
            )

    # History operations

    def _export_history(self) -> None:
        try:
            if not self.history_manager or self.sidebar.entry_count() == 0:
                self.statusBar().showMessage("No history to export", 2000)
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
        """Clear all transcription history.
        
        Phase 5: Uses clear_transcript() for terminal state mutation.
        """
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
                self.sidebar.load_history()
                # Use clear_transcript for authority-compliant state transition
                self.workspace.clear_transcript()
                self.metrics_strip.refresh()
        except Exception as e:
            logger.exception("Error clearing history")
            show_error_dialog(
                title="Clear History Error",
                message=f"Failed to clear history: {e}",
                parent=self,
            )

    # Sidebar resize handling
    
    @pyqtSlot(int)
    def _on_sidebar_resize(self, new_width: int) -> None:
        """Handle resize grip drag."""
        try:
            # Ensure width is within valid bounds
            clamped_width = Dimensions.clamp_sidebar_width(new_width, self.width())
            
            # Set both min and max to lock at this width (no fixed width conflicts)
            self.sidebar.setMinimumWidth(clamped_width)
            self.sidebar.setMaximumWidth(clamped_width)
            self.sidebar.updateGeometry()
            self._sidebar_expanded_width = clamped_width
            self.settings.setValue("sidebar_width", clamped_width)
        except Exception as e:
            logger.exception("Error resizing sidebar")

    @pyqtSlot()
    def _collapse_sidebar(self) -> None:
        """Collapse sidebar completely and show expand button."""
        try:
            if self._sidebar_collapsed:
                return
            
            # Save current width before collapsing
            current_width = self.sidebar.width()
            # Ensure saved width is within valid bounds
            self._sidebar_expanded_width = Dimensions.clamp_sidebar_width(current_width, self.width())
            
            self.sidebar.hide()
            self._expand_button.show()
            self._position_expand_button()
            
            if self._content_layout:
                self._content_layout.setSpacing(0)
            
            self._sidebar_collapsed = True
            self.settings.setValue("sidebar_visible", False)
            self.settings.setValue("sidebar_width", self._sidebar_expanded_width)
        except Exception as e:
            logger.exception("Error collapsing sidebar")

    @pyqtSlot(int)
    def _expand_sidebar(self, target_width: int = 0) -> None:
        """Expand sidebar to target width or last saved width."""
        try:
            if not self._sidebar_collapsed:
                return
            
            # Determine target width
            if target_width <= 0:
                target_width = self._sidebar_expanded_width
            if target_width < Dimensions.SIDEBAR_MIN_WIDTH:
                target_width = self._calculate_sidebar_width()
            
            # Ensure width is within valid bounds for current window size
            target_width = Dimensions.clamp_sidebar_width(target_width, self.width())

            # Set both min and max to lock at this width
            self.sidebar.setMinimumWidth(target_width)
            self.sidebar.setMaximumWidth(target_width)
            self.sidebar.show()
            self._expand_button.hide()

            if self._content_layout:
                self._content_layout.setSpacing(Spacing.MAJOR_GAP)

            self._sidebar_collapsed = False
            self.settings.setValue("sidebar_visible", True)
            self.settings.setValue("sidebar_width", target_width)
        except Exception as e:
            logger.exception("Error expanding sidebar")

    def _position_expand_button(self) -> None:
        """Position the expand button at left edge when sidebar is collapsed."""
        try:
            if not self._expand_button.isVisible():
                return
            # Position at left edge, vertically centered
            title_bar_height = self.title_bar.height() if hasattr(self, "title_bar") else 44
            y = title_bar_height + (self.height() - title_bar_height - self._expand_button.height()) // 2
            self._expand_button.move(0, y)
        except Exception as e:
            logger.exception("Error positioning expand button")

    def _calculate_sidebar_width(self) -> int:
        """Calculate sidebar width (30% of window, clamped to valid range)."""
        target = int(self.width() * Dimensions.SIDEBAR_DEFAULT_RATIO)
        return Dimensions.clamp_sidebar_width(target, self.width())
    
    def _ensure_sidebar_width(self) -> None:
        """Ensure sidebar has proper width after window is fully shown."""
        if self._sidebar_collapsed:
            return
        
        window_width = self.width()
        min_width_absolute = Dimensions.get_sidebar_min_width(window_width)
        
        current_width = self.sidebar.width()
        if current_width < min_width_absolute:
            # Use saved width if valid, otherwise use minimum
            width = max(self._sidebar_expanded_width, min_width_absolute)
            width = Dimensions.clamp_sidebar_width(width, window_width)
            
            # Set both min and max to lock at this width
            self.sidebar.setMinimumWidth(width)
            self.sidebar.setMaximumWidth(width)
            self.sidebar.updateGeometry()
            if self._content_layout:
                self._content_layout.activate()
        # Mark initial state as fully restored
        self._initial_state_restored = True

    # State persistence

    def _restore_state(self) -> None:
        geometry = self.settings.value("geometry")

        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(WindowSize.BASE, WindowSize.BASE)
            self._center_on_screen()

        sidebar_visible = self.settings.value("sidebar_visible", True, type=bool)
        self._sidebar_collapsed = not sidebar_visible

        if not sidebar_visible:
            # Sidebar is collapsed - hide it and show expand button
            self.sidebar.hide()
            self._expand_button.show()
            # Position button after window is shown
            QTimer.singleShot(0, self._position_expand_button)
            if self._content_layout:
                self._content_layout.setSpacing(0)
        else:
            # Calculate sidebar width after window geometry is applied
            # Use saved width if available, otherwise calculate
            saved_width = self.settings.value("sidebar_width", 0, type=int)
            if saved_width >= Dimensions.SIDEBAR_MIN_WIDTH:
                width = saved_width
            else:
                width = self._calculate_sidebar_width()
            # Ensure width is within valid bounds for current window
            width = Dimensions.clamp_sidebar_width(width, self.width())
            self._sidebar_expanded_width = width
            
            # Set both min and max to lock at this width
            self.sidebar.setMinimumWidth(width)
            self.sidebar.setMaximumWidth(width)
            self.sidebar.show()
            # Force layout to process the new width
            self.sidebar.updateGeometry()
            if self._content_layout:
                self._content_layout.activate()
            # Re-apply width after window is fully shown to handle late geometry
            QTimer.singleShot(100, self._ensure_sidebar_width)
            if self._content_layout:
                self._content_layout.setSpacing(Spacing.MAJOR_GAP)

        collapse_state = self.settings.value("sidebar_collapse", {})
        if isinstance(collapse_state, dict):
            self.sidebar.set_collapse_state(collapse_state)

        metrics_collapsed = self.settings.value("metrics_collapsed", False)
        if metrics_collapsed == "true" or metrics_collapsed is True:
            self.metrics_strip.set_collapsed(True)

    def _save_state(self) -> None:
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("sidebar_visible", not self._sidebar_collapsed)
        self.settings.setValue("sidebar_collapse", self.sidebar.get_collapse_state())
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
        if self._sidebar_collapsed:
            self._position_expand_button()
            return

        # Ensure sidebar stays within valid bounds during window resize
        if hasattr(self, "sidebar") and self._initial_state_restored:
            window_width = self.width()
            current_width = self.sidebar.width()
            
            # Clamp current width to new window constraints
            new_width = Dimensions.clamp_sidebar_width(current_width, window_width)
            
            # Only update if width actually needs to change
            if new_width != current_width:
                self.sidebar.setMinimumWidth(new_width)
                self.sidebar.setMaximumWidth(new_width)
                self._sidebar_expanded_width = new_width
                self.settings.setValue("sidebar_width", new_width)

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.WindowStateChange:
            if hasattr(self, "title_bar"):
                self.title_bar.sync_state()
        super().changeEvent(event)
