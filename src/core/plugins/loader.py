"""
Plugin Loader System.

Responsible for discovering and loading external Input Backends (and future plugin types).
Supports:
1. Built-in Backends (evdev, pynput)
2. Entry Point Plugins (via `vociferous.plugins.input` group)
"""

import logging
import importlib.metadata
from typing import Type, List, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.input_handler.backends.base import InputBackend

logger = logging.getLogger(__name__)


class PluginLoader:
    """
    Central registry and loader for application plugins.
    """

    _input_backends: Dict[str, Type["InputBackend"]] = {}

    @classmethod
    def register_backend(cls, name: str, backend_cls: Type["InputBackend"]):
        """Manually register a backend class."""
        # Defer import to avoid circular dependency

        # Runtime Protocol check for issubclass is flaky with non-method members
        # We perform a rough duck-typing check instead
        if not hasattr(backend_cls, "is_available") or not hasattr(
            backend_cls, "start"
        ):
            # Runtime checkable protocol check is loose, manually verify basic contract?
            # For now, we trust type hint or runtime failure
            pass

        cls._input_backends[name] = backend_cls
        logger.debug(f"Registered input backend: {name}")

    @classmethod
    def discover_plugins(cls):
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
                            f"Plugin {ep.name} does not satisfy InputBackend protocol."
                        )
                except Exception as e:
                    logger.error(f"Failed to load plugin {ep.name}: {e}")
        except Exception as e:
            logger.error(f"Plugin discovery failed: {e}")

    @classmethod
    def get_available_backends(cls) -> List[Type["InputBackend"]]:
        """Return list of instantiated available backends."""
        return [cls for cls in cls._input_backends.values() if cls.is_available()]

    @classmethod
    def get_backend_by_name(cls, name: str) -> Optional[Type["InputBackend"]]:
        return cls._input_backends.get(name)
