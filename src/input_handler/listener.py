import logging
from collections.abc import Callable

from src.core.plugins import PluginLoader
from src.core.settings import get_settings

from .backends.base import InputBackend
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
        PluginLoader.discover_plugins()
        available_classes = PluginLoader.get_available_backends()
        self.backends = [cls() for cls in available_classes]

    def select_backend_from_config(self) -> None:
        """Select the active backend based on configuration."""
        preferred_backend = get_settings().recording.input_backend

        if preferred_backend == "auto":
            self.select_active_backend()
            return

        # Try to find registered backend by name
        backend_cls = PluginLoader.get_backend_by_name(preferred_backend)
        if backend_cls and backend_cls.is_available():
            # Find the instance in self.backends
            for instance in self.backends:
                if isinstance(instance, backend_cls):
                    self.active_backend = instance
                    self.active_backend.on_input_event = self.on_input_event
                    logger.info(f"Selected configured backend: {preferred_backend}")
                    return

        logger.warning(
            f"Configured backend '{preferred_backend}' not available. Falling back to auto."
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
        """Start the active backend, enabling fallback if startup fails."""
        # Prioritize currently selected backend, then try others
        candidates = []
        if self.active_backend:
            candidates.append(self.active_backend)
        for backend in self.backends:
            if backend not in candidates:
                candidates.append(backend)

        if not candidates:
            logger.error("No input backends available to start")
            return

        for backend in candidates:
            try:
                # Ensure callback is connected
                backend.on_input_event = self.on_input_event
                backend.start()
                self.active_backend = backend
                logger.info(f"Started input backend: {type(backend).__name__}")
                return
            except Exception as e:
                logger.warning(f"Backend {type(backend).__name__} failed to start: {e}")
                try:
                    backend.stop()
                except Exception:
                    pass

        logger.error("All input backends failed to start")
        self.active_backend = None

    def stop(self) -> None:
        """Stop the active backend."""
        if self.active_backend:
            self.active_backend.stop()

    def load_activation_keys(self) -> None:
        """Load activation keys from configuration."""
        key_combination = get_settings().recording.activation_key
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
            "SUPER": frozenset({KeyCode.META_LEFT, KeyCode.META_RIGHT}),
        }

        keys: set[KeyCode | frozenset[KeyCode]] = set()
        for key in combination_string.upper().split("+"):
            key = key.strip()
            if not key:
                continue
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
        key, event_type = event

        # Capture mode takes priority - allow hotkey rebinding even if key_chord is not set
        if self.capture_mode and self.capture_callback:
            try:
                self.capture_callback(key, event_type)
            except Exception:
                logger.exception("Error in capture callback")
            return

        # If no key chord configured, exit early for normal hotkey detection
        if not self.key_chord:
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

    def trigger_callbacks_for_tests(self, event_name: str) -> None:
        """Expose trigger mechanism for testing."""
        self._trigger_callbacks(event_name)
