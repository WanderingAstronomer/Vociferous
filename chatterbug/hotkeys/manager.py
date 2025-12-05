from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict


HotkeyCallback = Callable[[str], None]


@dataclass(frozen=True)
class Hotkey:
    combo: str  # e.g., "ctrl+shift+space"


class HotkeyManager:
    """In-memory hotkey registry; OS-level bindings are not implemented yet."""

    def __init__(self) -> None:
        self._callbacks: Dict[str, HotkeyCallback] = {}

    def register(self, hotkey: Hotkey, callback: HotkeyCallback) -> None:
        self._callbacks[hotkey.combo] = callback

    def unregister(self, hotkey: Hotkey) -> None:
        self._callbacks.pop(hotkey.combo, None)

    def emit(self, combo: str) -> None:
        if combo in self._callbacks:
            self._callbacks[combo](combo)
