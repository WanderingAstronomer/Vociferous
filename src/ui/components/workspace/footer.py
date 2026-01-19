"""
Batch status footer component.

Displays feedback when database batch operations are in progress.
"""

from __future__ import annotations

import logging

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from src.database.signal_bridge import DatabaseSignalBridge
from src.ui.constants import Spacing

logger = logging.getLogger(__name__)


class BatchStatusFooter(QWidget):
    """
    Footer widget that displays batch processing status.

    Observes DatabaseSignalBridge for batch events and updates visibility
    and text accordingly.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("batchStatusFooter")

        self._setup_ui()
        self._connect_signals()

        # Hidden by default
        self.hide()

    def _setup_ui(self) -> None:
        """Initialize the footer UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Spacing.S2, Spacing.S1, Spacing.S2, Spacing.S1)
        layout.setSpacing(Spacing.MINOR_GAP)

        self.status_label = QLabel()
        self.status_label.setObjectName("batchStatusLabel")

        layout.addWidget(self.status_label)
        layout.addStretch()

    def _connect_signals(self) -> None:
        """Connect to the database signal bridge."""
        bridge = DatabaseSignalBridge()
        bridge.is_processing_batch.connect(self._on_batch_status_changed)

    def _on_batch_status_changed(self, active: bool, count: int) -> None:
        """
        Handle batch status changes.

        Args:
            active: Whether a batch is currently being processed.
            count: Number of items in the current batch.
        """
        if active and count > 0:
            self.status_label.setText(f"Processing batch... ({count} items)")
            self.show()
        else:
            self.hide()
