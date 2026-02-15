"""
StateManager — Persistent session state (v4.0).

Uses ResourceManager for paths. No Qt dependency.
"""

import json
import logging
from pathlib import Path
from typing import Any

from src.core.resource_manager import ResourceManager

logger = logging.getLogger(__name__)


class StateManager:
    """
    Manages ephemeral application state/session data that persists across runs
    but is not configuration (e.g., window geometry cache, flags).
    """

    def __init__(self) -> None:
        self._state: dict[str, Any] = {}
        self._path = ResourceManager.get_user_config_dir() / "state.json"
        self._load()

    def _load(self) -> None:
        """Load state from disk."""
        try:
            if self._path.exists():
                with open(self._path, "r", encoding="utf-8") as f:
                    self._state = json.load(f)
        except Exception as e:
            logger.error("Failed to load state: %s", e)
            self._state = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from state."""
        return self._state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in state and save immediately."""
        self._state[key] = value
        self._save()

    def _save(self) -> None:
        """Save state to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2)
        except Exception as e:
            logger.error("Failed to save state: %s", e)
