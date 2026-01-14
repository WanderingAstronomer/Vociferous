"""
MetricsDock - Unified statistics display.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from ui.constants import Colors, Typography, SPEAKING_SPEED_WPM, TYPING_SPEED_WPM

if TYPE_CHECKING:
    from history_manager import HistoryManager

logger = logging.getLogger(__name__)

class MetricsDock(QFrame):
    """
    Bottom dock displaying statistics.
    Replacement for MetricsStrip.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("metricsDock")
        self._history_manager: Optional[HistoryManager] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setFixedHeight(36)
        # Styling handled in unified_stylesheet.py (#metricsDock)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(32)

        # Metrics
        self._lbl_count_val = self._add_metric(layout, "Transcripts")
        self._lbl_words_val = self._add_metric(layout, "Words")
        self._lbl_saved_val = self._add_metric(layout, "Time Saved")
        
        layout.addStretch()

    def _add_metric(self, layout: QHBoxLayout, label: str) -> QLabel:
        cont = QWidget()
        l = QHBoxLayout(cont)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(0)
        
        lbl_name = QLabel(label + ":")
        lbl_val = QLabel("—")
        lbl_val.setObjectName("MetricValue")
        
        l.addWidget(lbl_name)
        l.addWidget(lbl_val)
        
        layout.addWidget(cont)
        return lbl_val

    def set_history_manager(self, manager: HistoryManager) -> None:
        self._history_manager = manager
        self.refresh()

    def refresh(self) -> None:
        """Recalculate and display metrics."""
        if not self._history_manager:
            return
            
        try:
            # Analyze last 1000 entries for performance
            entries = self._history_manager.get_recent(limit=1000)
            
            count = len(entries)
            words = sum(len(e.text.split()) for e in entries)
            
            # Simple estimates
            rec_sec = sum(e.duration_ms for e in entries if e.duration_ms) / 1000.0
            if rec_sec == 0 and words > 0:
                 rec_sec = (words / SPEAKING_SPEED_WPM) * 60
            
            type_sec = (words / TYPING_SPEED_WPM) * 60
            saved_sec = max(0, type_sec - rec_sec)
            
            self._lbl_count_val.setText(f"{count:,}")
            self._lbl_words_val.setText(f"{words:,}")
            self._lbl_saved_val.setText(self._format_duration(saved_sec))
            
        except Exception as e:
            logger.error(f"Failed to refresh metrics: {e}")

    def _format_duration(self, seconds: float) -> str:
        if seconds < 60:
            return f"{int(seconds)}s"
        mins = int(seconds / 60)
        if mins < 60:
            return f"{mins}m"
        hours = mins / 60
        return f"{hours:.1f}h"
