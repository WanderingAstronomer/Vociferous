"""
StateManager - Manages persistent session state.
"""

import json
import logging
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QStandardPaths

logger = logging.getLogger(__name__)


class StateManager:
    """
    Manages ephemeral application state/session data that persists across runs
    but is not configuration (e.g., MOTD, window geometry cache).
    """

    _instance = None
    _state: dict[str, Any] = {}

    def __new__(cls) -> "StateManager":
        if cls._instance is None:
            cls._instance = super(StateManager, cls).__new__(cls)
            cls._instance._load()
        return cls._instance

    def _get_state_path(self) -> Path:
        """Get path to state.json in user config directory."""
        config_dir = Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppConfigLocation
            )
        )
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "state.json"

    def _load(self) -> None:
        """Load state from disk."""
        try:
            path = self._get_state_path()
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    self._state = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
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
            path = self._get_state_path()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
