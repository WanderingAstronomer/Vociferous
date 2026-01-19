"""
Command Bus Service.

Central hub for Intent dispatch and handling.
Bridge between Core logic, Hardware Inputs, and UI.
"""

import logging
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from src.core.intents import InteractionIntent
from src.core.intents.registry import HandbookRegistry
from src.core.intents.guards import ReplayContext

logger = logging.getLogger(__name__)


class CommandBus(QObject):
    """
    Dispatches intents to registered handlers and emits signals for observables.
    """

    # Signal emitted when an intent is successfully dispatched/processed
    # Using 'object' because Intent Interitance (dataclasses) doesn't play nice with Qt strict types
    intent_dispatched = pyqtSignal(object)

    # Signal emitted when a guard rejects an intent (for feedback/resolvers)
    intent_rejected = pyqtSignal(object, object)  # intent, guard_result

    def __init__(self) -> None:
        super().__init__()
        # Context Tracker - In a real app, this might be updated by Focus events
        self.context: ReplayContext = ReplayContext(
            active_view_id="unknown", focused_capability="none", can_edit=False
        )

        # Instance-level handlers (e.g. methods bound to live widgets)
        self._handlers: dict[type[InteractionIntent], Any] = {}

    def update_context(self, new_context: ReplayContext) -> None:
        """Update the Replay/Safety Context."""
        self.context = new_context

    def register_handler(
        self, intent_type: type[InteractionIntent], handler: Any
    ) -> None:
        """Register a runtime handler for an intent type."""
        self._handlers[intent_type] = handler

    def dispatch(self, intent: InteractionIntent, allow_ui: bool = True) -> None:
        """
        Process an intent.
        1. Check Guard Policy (Safety)
        2. Execute Handler (if registered)
        3. Emit Signal (for UI/Logging)
        """
        intent_type = type(intent)
        meta = HandbookRegistry.get_metadata(intent_type)

        # 1. Guard (Safety) Check
        if meta and meta.guard:
            try:
                result = meta.guard.evaluate(self.context, intent)
                if not result.allowed:
                    logger.warning(f"Intent {intent} blocked by guard.")
                    self.intent_rejected.emit(intent, result)
                    return
            except Exception as e:
                logger.error(f"Guard evaluation failed: {e}")
                return

        # 2. Execution
        handled = False

        # Prioritize runtime handlers (e.g. UI bound methods)
        if intent_type in self._handlers:
            try:
                self._handlers[intent_type](intent)
                handled = True
            except Exception as e:
                logger.error(f"Handler failed for {intent}: {e}")

        # Fallback to Static Handlers (from Decorator)?
        # In a Qt app, standard handlers might not be static functions but bound methods.
        # But for Core logic (e.g. SaveSettings), it might be static.
        elif meta and meta.handler:
            try:
                meta.handler(
                    intent
                )  # This assumes the handler function can take the intent
                handled = True
            except Exception as e:
                logger.error(f"Static Handler failed: {e}")

        # 3. Notification
        if handled:
            self.intent_dispatched.emit(intent)
        else:
            # If strictly intent-driven, maybe we just emit and let UI react?
            # "Intents MUST propagate upward" -> Signal
            # So if no handler executed, we still emit, assuming a parent/listener will handle it?
            self.intent_dispatched.emit(intent)
