"""
SystemHandlers — config update and engine restart intents.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from src.core.settings import VociferousSettings
    from src.input_handler.listener import KeyListener

logger = logging.getLogger(__name__)


class SystemHandlers:
    """Handles config update and engine restart intents."""

    def __init__(
        self,
        *,
        event_bus_emit: Callable,
        input_listener_provider: Callable[[], KeyListener | None],
        on_settings_updated: Callable[[VociferousSettings], None],
        restart_engine: Callable[[], None],
    ) -> None:
        self._emit = event_bus_emit
        self._input_listener_provider = input_listener_provider
        self._on_settings_updated = on_settings_updated
        self._restart_engine = restart_engine

    def handle_update_config(self, intent: Any) -> None:
        from src.core.settings import update_settings

        new_settings = update_settings(**intent.settings)
        self._on_settings_updated(new_settings)
        self._emit("config_updated", new_settings.model_dump())

        # Reload activation keys if the input handler is running
        input_listener = self._input_listener_provider()
        if input_listener:
            try:
                input_listener.update_activation_keys()
                input_listener.reset_chord_state()
                logger.info("Input handler activation keys reloaded")
            except Exception:
                logger.exception("Failed to reload activation keys")

    def handle_restart_engine(self, intent: Any) -> None:
        self._restart_engine()
