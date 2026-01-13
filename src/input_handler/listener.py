import logging
from collections.abc import Callable

from utils import ConfigManager

from .backends.base import InputBackend
from .backends.evdev import EvdevBackend
from .backends.pynput import PynputBackend
from .chord import KeyChord
from .types import InputEvent, KeyCode

logger = logging.getLogger(__name__)


class KeyListener:
    """Manages input backends and detects hotkey chord activation."""

    def __init__(self) -> None:
        """Initialize the KeyListener with backends and activation keys."""
        self.backends: list[InputBackend] = []
        self.active_backend: InputBackend | None = None
        self.key_chord: KeyChord | None = None
        self.callbacks: dict[str, list[Callable[[], None]]] = {
            "on_activate": [],
            "on_deactivate": [],
        }
        self.capture_mode: bool = False
        self.capture_callback: Callable[[KeyCode, InputEvent], None] | None = None
        self.load_activation_keys()
        self.initialize_backends()
        self.select_backend_from_config()

    def initialize_backends(self) -> None:
        """Initialize available input backends."""
        backend_classes: list[type[InputBackend]] = [EvdevBackend, PynputBackend]  # type: ignore[list-item]
        self.backends = [cls() for cls in backend_classes if cls.is_available()]

    def select_backend_from_config(self) -> None:
        """Select the active backend based on configuration."""
        preferred_backend = ConfigManager.get_config_value(
            "recording_options", "input_backend"
        )

        match preferred_backend:
            case "auto":
                self.select_active_backend()
            case "evdev":
                self._try_set_backend(EvdevBackend)
            case "pynput":
                self._try_set_backend(PynputBackend)
            case _:
                logger.warning(
                    f"Unknown backend '{preferred_backend}'. Falling back to auto."
                )
                self.select_active_backend()

    def _try_set_backend(self, backend_class: type) -> None:
        """Try to set a specific backend, fall back to auto if unavailable."""
        try:
            self.set_active_backend(backend_class)
        except ValueError:
            name = backend_class.__name__
            logger.warning(f"Backend '{name}' unavailable. Using auto.")
            self.select_active_backend()

    def select_active_backend(self) -> None:
        """Select the first available backend as active."""
        if not self.backends:
            raise RuntimeError("No supported input backend found")
        self.active_backend = self.backends[0]
        self.active_backend.on_input_event = self.on_input_event

    def set_active_backend(self, backend_class: type) -> None:
        """Set a specific backend as active."""
        new_backend = next(
            (b for b in self.backends if isinstance(b, backend_class)), None
        )
        if new_backend:
            if self.active_backend:
                self.stop()
            self.active_backend = new_backend
            self.active_backend.on_input_event = self.on_input_event
            self.start()
        else:
            raise ValueError(f"Backend {backend_class.__name__} is not available")

    def update_backend(self) -> None:
        """Update the active backend based on current configuration."""
        self.select_backend_from_config()

    def start(self) -> None:
        """Start the active backend."""
        if self.active_backend:
            self.active_backend.start()
        else:
            raise RuntimeError("No active backend selected")

    def stop(self) -> None:
        """Stop the active backend."""
        if self.active_backend:
            self.active_backend.stop()

    def load_activation_keys(self) -> None:
        """Load activation keys from configuration."""
        key_combination = ConfigManager.get_config_value(
            "recording_options", "activation_key"
        )
        keys = self.parse_key_combination(key_combination)
        self.set_activation_keys(keys)

    def parse_key_combination(
        self, combination_string: str
    ) -> set[KeyCode | frozenset[KeyCode]]:
        """Parse a string representation of key combination into a set of KeyCodes."""
        modifier_map: dict[str, frozenset[KeyCode]] = {
            "CTRL": frozenset({KeyCode.CTRL_LEFT, KeyCode.CTRL_RIGHT}),
            "SHIFT": frozenset({KeyCode.SHIFT_LEFT, KeyCode.SHIFT_RIGHT}),
            "ALT": frozenset({KeyCode.ALT_LEFT, KeyCode.ALT_RIGHT}),
            "META": frozenset({KeyCode.META_LEFT, KeyCode.META_RIGHT}),
        }

        keys: set[KeyCode | frozenset[KeyCode]] = set()
        for key in combination_string.upper().split("+"):
            key = key.strip()
            if key in modifier_map:
                keys.add(modifier_map[key])
            else:
                try:
                    keys.add(KeyCode[key])
                except KeyError:
                    logger.warning(f"Unknown key: {key}")
        return keys

    def set_activation_keys(self, keys: set[KeyCode | frozenset[KeyCode]]) -> None:
        """Set the activation keys for the KeyChord."""
        self.key_chord = KeyChord(keys=keys)

    def on_input_event(self, event: tuple[KeyCode, InputEvent]) -> None:
        """Handle input events and trigger callbacks for key chord changes."""
        if not self.key_chord or not self.active_backend:
            return

        key, event_type = event

        if self.capture_mode and self.capture_callback:
            try:
                self.capture_callback(key, event_type)
            except Exception:
                logger.exception("Error in capture callback")
            return
        was_active = self.key_chord.is_active()
        is_active = self.key_chord.update(key, event_type)

        match (was_active, is_active):
            case (False, True):
                self._trigger_callbacks("on_activate")
            case (True, False):
                self._trigger_callbacks("on_deactivate")

    def enable_capture_mode(
        self, callback: Callable[[KeyCode, InputEvent], None]
    ) -> None:
        """Divert input events to a capture handler (used for hotkey rebinding)."""
        self.capture_mode = True
        self.capture_callback = callback

    def disable_capture_mode(self) -> None:
        """Exit capture mode and resume normal hotkey handling."""
        self.capture_mode = False
        self.capture_callback = None

    def add_callback(self, event: str, callback: Callable[[], None]) -> None:
        """Add a callback function for a specific event."""
        if event in self.callbacks:
            self.callbacks[event].append(callback)

    def _trigger_callbacks(self, event: str) -> None:
        """Trigger all callbacks associated with a specific event."""
        for callback in self.callbacks.get(event, []):
            try:
                callback()
            except Exception:
                logger.exception(f"Error in {event} callback")

    def update_activation_keys(self) -> None:
        """Update activation keys from the current configuration."""
        self.load_activation_keys()
