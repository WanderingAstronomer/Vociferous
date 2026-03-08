"""
Plugin Loader System.

Responsible for discovering and loading external Input Backends (and future plugin types).
Supports:
1. Built-in Backends (evdev, pynput)
2. Entry Point Plugins (via `vociferous.plugins.input` group)
"""

import importlib.metadata
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.input_handler.backends.base import InputBackend

logger = logging.getLogger(__name__)


class PluginLoader:
    """
    Central registry and loader for application plugins.
    """

    _input_backends: dict[str, type["InputBackend"]] = {}

    @classmethod
    def register_backend(cls, name: str, backend_cls: type["InputBackend"]) -> None:
        """Register a backend class after duck-type validation."""
        if not hasattr(backend_cls, "is_available") or not hasattr(backend_cls, "start"):
            logger.warning(
                "Backend '%s' (%s) missing required methods (is_available, start). Skipping.",
                name, backend_cls.__name__,
            )
            return

        cls._input_backends[name] = backend_cls
        logger.debug("Registered input backend: %s", name)

    @classmethod
    def discover_plugins(cls) -> None:
        """
        Discover plugins via entry points (Setuptools/Poetry).
        Group: `vociferous.plugins.input`
        """
        # 1. Register Built-ins explicitly to ensure they are always present
        from src.input_handler.backends.evdev import EvdevBackend
        from src.input_handler.backends.pynput import PynputBackend

        cls.register_backend("evdev", EvdevBackend)
        cls.register_backend("pynput", PynputBackend)

        # 2. Discover External
        try:
            # Python 3.10+ select interface
            entry_points = importlib.metadata.entry_points(
                group="vociferous.plugins.input"
            )
            for ep in entry_points:
                try:
                    plugin_cls = ep.load()
                    # Verify protocol compliance roughly
                    if hasattr(plugin_cls, "is_available") and hasattr(
                        plugin_cls, "start"
                    ):
                        cls.register_backend(ep.name, plugin_cls)
                    else:
                        logger.warning(
                            "Plugin %s does not satisfy InputBackend protocol.", ep.name
                        )
                except Exception as e:
                    logger.error("Failed to load plugin %s: %s", ep.name, e)
        except Exception as e:
            logger.error("Plugin discovery failed: %s", e)

    @classmethod
    def get_available_backends(cls) -> list[type["InputBackend"]]:
        """Return backend classes whose is_available() returns True."""
        return [backend for backend in cls._input_backends.values() if backend.is_available()]

    @classmethod
    def get_backend_by_name(cls, name: str) -> type["InputBackend"] | None:
        return cls._input_backends.get(name)
