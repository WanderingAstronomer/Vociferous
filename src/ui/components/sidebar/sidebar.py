"""
SidebarWidget - Main sidebar component with Focus Groups and Ungrouped Transcripts.

Uses shared TranscriptionModel as single source of truth for all views.
Contains collapsible sections and handles section toggle layout management.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from ui.constants import Spacing
from ui.models import TranscriptionModel
from ui.widgets.collapsible_section import CollapsibleSection
from ui.widgets.focus_group import FocusGroupContainer

from ui.components.sidebar.sidebar_edge import SidebarEdge
from ui.components.sidebar.transcript_tree import TranscriptTreeView

if TYPE_CHECKING:
    from history_manager import HistoryEntry, HistoryManager


class SidebarWidget(QWidget):
    """
    Main sidebar widget containing separated Focus Groups and Ungrouped Transcripts.

    Uses shared TranscriptionModel - single source of truth for all views.

    Signals:
        entrySelected(str, str): Emitted when entry is selected (text, timestamp)
        collapseRequested(): Emitted when sidebar collapse is requested
    """

    entrySelected = pyqtSignal(str, str)  # text, timestamp
    collapseRequested = pyqtSignal()

    def __init__(
        self,
        history_manager: HistoryManager | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setAutoFillBackground(True)  # Ensure background is painted
        self._history_manager = history_manager
        self._content_layout: QVBoxLayout | None = None
        self._bottom_spacer: QWidget | None = None

        # Create shared model (single source of truth)
        self._model: TranscriptionModel | None = None
        if history_manager:
            self._model = TranscriptionModel(history_manager)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create sidebar layout with sections and edge control."""
        # Styles are applied at app level via generate_unified_stylesheet()

        # Main horizontal layout: content + edge
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Content container
        self.content = QWidget()
        self.content.setObjectName("sidebarContent")
        content_outer = QVBoxLayout(self.content)
        content_outer.setContentsMargins(0, 0, 0, 0)
        content_outer.setSpacing(0)

        # Scrollable content area
        content_scroll = QWidget()
        content_layout = QVBoxLayout(content_scroll)
        self._content_layout = content_layout
        content_layout.setContentsMargins(
            Spacing.SIDEBAR_SIDE,
            Spacing.SIDEBAR_TOP,
            Spacing.SIDEBAR_SIDE,
            Spacing.SIDEBAR_BOTTOM,
        )
        content_layout.setSpacing(Spacing.SIDEBAR_SECTION_GAP)

        # --- SECTION 1: FOCUS GROUPS ---
        self.focus_groups_section = CollapsibleSection(
            "Focus Groups",
            content_scroll,
            initially_collapsed=False,
            show_action_button=True,
            action_text="+",
        )
        self.focus_groups_section.actionClicked.connect(self._on_create_group_clicked)

        self.focus_groups = FocusGroupContainer(self._history_manager)

        # Connect signals
        self.focus_groups.entrySelected.connect(self.entrySelected)
        if self._model:
            self._model.entryDeleted.connect(lambda _: self.focus_groups.load_groups())
            self._model.entryAdded.connect(lambda _: self.focus_groups.load_groups())
            self._model.entryUpdated.connect(lambda _: self.focus_groups.load_groups())
        self.focus_groups.groupDeleted.connect(self._on_group_deleted)
        self.focus_groups.groupRenamed.connect(self._on_group_metadata_changed)
        self.focus_groups.groupColorChanged.connect(self._on_group_metadata_changed)
        self.focus_groups.groupCreated.connect(self._on_group_metadata_changed)

        self.focus_groups_section.content_layout.addWidget(self.focus_groups)
        content_layout.addWidget(self.focus_groups_section, 0)

        # --- DIVIDER ---
        self.section_divider = QFrame()
        self.section_divider.setObjectName("sectionDivider")
        self.section_divider.setFrameShape(QFrame.Shape.HLine)
        self.section_divider.setFixedHeight(1)
        content_layout.addWidget(self.section_divider)

        # --- SECTION 2: UNGROUPED ---
        self.transcripts_section = CollapsibleSection(
            "Ungrouped Transcripts", content_scroll, initially_collapsed=False
        )

        self.transcript_list = TranscriptTreeView()
        if self._model:
            self.transcript_list.set_source_model(self._model)
        if self._history_manager:
            self.transcript_list.set_history_manager(self._history_manager)

        self.transcript_list.entrySelected.connect(self.entrySelected)
        self.transcript_list.countChanged.connect(self.transcripts_section.set_count)
        self.transcript_list.entryGroupChanged.connect(self._on_entry_group_changed)

        self.transcripts_section.content_layout.addWidget(self.transcript_list)

        content_layout.addWidget(self.transcripts_section, 1)

        self._bottom_spacer = QWidget()
        self._bottom_spacer.setObjectName("bottomSpacer")
        content_layout.addWidget(self._bottom_spacer, 1)  # Stretch to fill space

        content_outer.addWidget(content_scroll)
        outer_layout.addWidget(self.content, 1)

        # Right edge
        self.edge = SidebarEdge(self)
        outer_layout.addWidget(self.edge, 0)

        # Connect toggle signals
        self.transcripts_section.toggled.connect(self._on_section_toggled)
        self.focus_groups_section.toggled.connect(self._on_section_toggled)

        self._update_stretch_factors()

    def _on_create_group_clicked(self) -> None:
        """Handle create group button click."""
        self.focus_groups.create_new_group()

    def _on_section_toggled(self, expanded: bool) -> None:
        """Handle collapsible section toggles."""
        self._update_stretch_factors()

    def _on_group_metadata_changed(self, *args) -> None:
        """Refresh group color metadata."""
        if self._model:
            self._model.refresh_group_colors()

    def _on_group_deleted(self, *args) -> None:
        """Reload model when group is deleted."""
        if self._model:
            self._model.refresh_from_manager()

    def _on_entry_group_changed(self, *args) -> None:
        """Refresh focus group tree when entries move."""
        self.focus_groups.load_groups()

    def _update_stretch_factors(self) -> None:
        """Adjust layout stretch factors based on expanded sections."""
        if not self._content_layout or not self._bottom_spacer:
            return

        ungrouped_expanded = self.transcripts_section.is_expanded()

        # Reset stretch factors
        self._content_layout.setStretchFactor(self.transcripts_section, 0)
        self._content_layout.setStretchFactor(self._bottom_spacer, 0)

        if ungrouped_expanded:
            # Ungrouped section is expanded - let it stretch
            self._content_layout.setStretchFactor(self.transcripts_section, 1)
        else:
            # Ungrouped is collapsed - bottom spacer always fills remaining space
            self._content_layout.setStretchFactor(self._bottom_spacer, 1)

    def get_model(self) -> TranscriptionModel | None:
        """Get the shared transcription model."""
        return self._model

    def get_collapse_state(self) -> dict[str, bool]:
        """Return collapsed state for persistence."""
        return {
            "focus_groups": self.focus_groups_section.is_collapsed(),
            "transcripts": self.transcripts_section.is_collapsed(),
        }

    def set_collapse_state(self, state: dict) -> None:
        """Restore collapsed state from settings."""
        if not isinstance(state, dict):
            return

        fg_collapsed = state.get("focus_groups")
        if isinstance(fg_collapsed, str):
            fg_collapsed = fg_collapsed.lower() == "true"
        if isinstance(fg_collapsed, bool):
            self.focus_groups_section.set_collapsed(fg_collapsed)

        transcripts_collapsed = state.get("transcripts")
        if isinstance(transcripts_collapsed, str):
            transcripts_collapsed = transcripts_collapsed.lower() == "true"
        if isinstance(transcripts_collapsed, bool):
            self.transcripts_section.set_collapsed(transcripts_collapsed)

        self._update_stretch_factors()

    def set_history_manager(self, manager: HistoryManager) -> None:
        """Set history manager for all components."""
        self._history_manager = manager

        if not self._model:
            self._model = TranscriptionModel(manager)
            if hasattr(self, "transcript_list"):
                self.transcript_list.set_source_model(self._model)

        self.focus_groups.set_history_manager(manager)
        self.transcript_list.set_history_manager(manager)

    def toggle(self) -> None:
        """Request sidebar collapse/expand."""
        self.collapseRequested.emit()

    def set_content_visible(self, visible: bool) -> None:
        """Show or hide the sidebar content area."""
        self.content.setVisible(visible)

    def focus_transcript_list(self) -> None:
        """Set keyboard focus to the transcript list."""
        self.transcript_list.setFocus()

    def add_entry(self, entry: HistoryEntry) -> None:
        """Add a new transcript entry to the model."""
        if self._model:
            self._model.add_entry(entry)

    def entry_count(self) -> int:
        """Return count of ungrouped transcripts."""
        return self.transcript_list.entry_count()

    def load_history(self) -> None:
        """Reload model and focus groups."""
        if self._model:
            self._model.refresh_from_manager()
        self.focus_groups.load_groups()
