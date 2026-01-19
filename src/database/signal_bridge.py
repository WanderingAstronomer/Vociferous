"""
Signal bridge for database events.

Provides a centralized QObject to propagate database changes to the UI
via Qt signals, supporting batching to prevent UI performance issues.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from PyQt6.QtCore import QObject, pyqtSignal

from src.database.events import ChangeAction, EntityChange

logger = logging.getLogger(__name__)


class DatabaseSignalBridge:
    """
    Singleton bridge to propagate database changes to the UI via Qt signals.
    Supports batching/grouping of signals to prevent UI thrashing.
    """

    class _Emitter(QObject):
        # Signal emitted when data changes
        data_changed = pyqtSignal(EntityChange)
        # Signal for UI feedback during batch operations (active, count)
        is_processing_batch = pyqtSignal(bool, int)

    _instance: "DatabaseSignalBridge | None" = None
    _initialized: bool = False

    def __new__(cls) -> "DatabaseSignalBridge":
        """Singleton pattern for global signal bridge."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (primarily for tests)."""
        if cls._instance:
            # Explicitly clear the emitter and instance
            cls._instance._initialized = False
            cls._instance = None

    def __init__(self) -> None:
        """Initialize."""
        if self._initialized:
            return

        self._emitter = self._Emitter()
        self._initialized = True

        self._batch_depth = 0
        self._pending_ids: list[int] = []
        self._current_entity_type: str | None = None
        self._current_action: ChangeAction | None = None

    @property
    def data_changed(self):
        """Proxy for emitter signal."""
        return self._emitter.data_changed

    @property
    def is_processing_batch(self):
        """Proxy for emitter signal."""
        return self._emitter.is_processing_batch

    def emit_change(self, change: EntityChange) -> None:
        """
        Emit a change event or collect it if a batch is active.

        Args:
            change: The change event to emit.
        """
        if self._batch_depth > 0:
            self._pending_ids.extend(change.ids)

            # Use the first encountered type/action for the batch header if not set
            if self._current_entity_type is None:
                self._current_entity_type = change.entity_type
                self._current_action = change.action

            # Update the count for UI feedback
            self.is_processing_batch.emit(True, len(self._pending_ids))
        else:
            self.data_changed.emit(change)

    @contextmanager
    def signal_group(
        self, entity_type: str | None = None, action: ChangeAction | None = None
    ) -> Generator[None, None, None]:
        """
        Context manager to group multiple emissions into a single signal.

        Args:
            entity_type: Optional override for the final entity type.
            action: Optional override for the final action.
        """
        self._batch_depth += 1
        if self._batch_depth == 1:
            self._pending_ids = []
            self._current_entity_type = entity_type
            self._current_action = action
            self.is_processing_batch.emit(True, 0)

        try:
            yield
        finally:
            self._batch_depth -= 1
            if self._batch_depth == 0:
                # Resolve final parameters
                final_type = entity_type or self._current_entity_type or "mixed"
                final_action = (
                    action or self._current_action or ChangeAction.BATCH_COMPLETED
                )

                ids = self._pending_ids
                reload = len(ids) > 50

                final_change = EntityChange(
                    entity_type=final_type,
                    action=final_action,
                    ids=ids,
                    reload_required=reload,
                )

                self.data_changed.emit(final_change)
                self.is_processing_batch.emit(False, 0)

                # Reset
                self._pending_ids = []
                self._current_entity_type = None
                self._current_action = None
