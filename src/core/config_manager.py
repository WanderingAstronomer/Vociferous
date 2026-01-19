"""
Configuration Management Module.

Thread-safe singleton ConfigManager using double-checked locking.
Schema-driven configuration with YAML validation and hot reloading.
"""

import logging
import threading
from contextlib import suppress
from pathlib import Path
from typing import Any

import yaml
from PyQt6.QtCore import QObject, pyqtSignal

from src.core.resource_manager import ResourceManager
from src.core.exceptions import ConfigurationError

_SCHEMA_FILENAME = "config_schema.yaml"

logger = logging.getLogger(__name__)


class ConfigManager(QObject):
    """Thread-safe singleton configuration manager with PyQt signals."""

    # Class-level attributes shared by all instances (though only one exists)
    # The type hint 'ConfigManager | None' uses Python 3.10+ union syntax
    _instance: "ConfigManager | None" = None
    _lock = threading.Lock()

    config_changed = pyqtSignal(str, str, object)
    config_reloaded = pyqtSignal()

    def __init__(self) -> None:
        """Initialize the ConfigManager instance."""
        super().__init__()
        self.config: dict[str, Any] = {}
        self.schema: dict[str, Any] = {}

    @classmethod
    def initialize(cls, schema_path: Path | str | None = None) -> None:
        """Initialize the ConfigManager singleton with double-checked locking."""
        if cls._instance is None:
            with cls._lock:
                # Double-check pattern for thread safety
                if cls._instance is None:
                    instance = cls()
                    instance.schema = instance.load_config_schema(schema_path)
                    instance.config = instance.load_default_config()
                    instance.load_user_config()
                    cls._instance = instance

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        """Get the configuration schema."""
        if cls._instance is None:
            raise RuntimeError("ConfigManager not initialized")
        return cls._instance.schema

    @classmethod
    def instance(cls) -> "ConfigManager":
        """Return the initialized ConfigManager instance."""
        if cls._instance is None:
            raise RuntimeError("ConfigManager not initialized")
        return cls._instance

    @classmethod
    def get_config_section(cls, *keys: str) -> dict[str, Any]:
        """Navigate through nested config dictionaries to get a section."""
        if cls._instance is None:
            raise RuntimeError("ConfigManager not initialized")

        section: Any = cls._instance.config
        for key in keys:
            match section:
                case dict() if key in section:
                    section = section[key]
                case _:
                    return {}
        return section

    @classmethod
    def get_config_value(cls, *keys: str) -> Any:
        """
        Legacy Accessor (Deprecated). Use get_value(category, key, default=...) instead.
        Get a specific configuration value using nested keys.
        """
        return cls.get_value(*keys)

    @classmethod
    def get_value(cls, *keys: str, default: Any = None) -> Any:
        """
        Get a configuration value with robust default fallback.

        Args:
            *keys: Path to the setting (e.g., "model_options", "model").
            default: Value to return if key path is missing.
        """
        if cls._instance is None:
            # We allow getting defaults if not initialized specifically for testing,
            # or raise strictly? Let's stick to strict initialization.
            raise RuntimeError("ConfigManager not initialized")

        value: Any = cls._instance.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    @classmethod
    def set_config_value(cls, value: Any, *keys: str) -> None:
        """Legacy Setter. Use set_value instead."""
        cls.set_value(value, *keys)

    @classmethod
    def set_value(cls, value: Any, *keys: str) -> None:
        """
        Set a configuration value with runtime type checking against schema.

        Args:
            value: The new value to set.
            *keys: The path to the setting.

        Raises:
            ConfigurationError: If value type doesn't match schema definition.
        """
        if cls._instance is None:
            raise RuntimeError("ConfigManager not initialized")
        if not keys:
            raise ValueError("At least one key required")

        # 1. Validate Type (if schema exists)
        # Assuming typical structure (Section -> Key)
        if len(keys) >= 2:
            section, key = keys[0], keys[1]
            schema_def = cls._instance.schema.get(section, {}).get(key)
            if schema_def and isinstance(schema_def, dict):
                expected_type_str = schema_def.get("type", "any")
                if not cls._check_type(value, expected_type_str):
                    raise TypeError(
                        f"Config validation failed: {keys} expected {expected_type_str}, got {type(value).__name__}"
                    )

        with cls._lock:
            config = cls._instance.config
            for key in keys[:-1]:
                # If intermediate key missing, create it dict
                if key not in config or not isinstance(config[key], dict):
                    config[key] = {}
                config = config[key]

            config[keys[-1]] = value

        # Emit after releasing the lock to avoid deadlocks
        if keys:
            section = keys[0]
            leaf_key = keys[-1]
            cls._instance.config_changed.emit(section, leaf_key, value)

    @staticmethod
    def _check_type(value: Any, expected_type: str) -> bool:
        """Helper to validate types against schema strings."""
        match expected_type:
            case "str":
                return isinstance(value, str)
            case "int":
                return isinstance(value, int)
            case "bool":
                return isinstance(value, bool)
            case "float":
                return isinstance(value, float)
            case "list":
                return isinstance(value, list)
            case "dict":
                return isinstance(value, dict)
            case "any":
                return True
            case _:
                return True  # default permissive

    @staticmethod
    def load_config_schema(schema_path: Path | str | None = None) -> dict[str, Any]:
        """Load the configuration schema from a YAML file."""
        if schema_path is None:
            # Use ResourceManager to find app root
            schema_path = ResourceManager.get_app_root() / "src" / _SCHEMA_FILENAME
            # Fallback for dev mode where it might be in root if src structure differs
            if not schema_path.exists():
                schema_path = ResourceManager.get_app_root() / _SCHEMA_FILENAME
        else:
            schema_path = Path(schema_path)

        if not schema_path.exists():
            raise ConfigurationError(f"Schema definition missing at {schema_path}")

        return yaml.safe_load(schema_path.read_text())

    def load_default_config(self) -> dict[str, Any]:
        """Extract default values from the schema using recursive pattern matching."""

        def extract_value(item: Any) -> Any:
            match item:
                case {"value": val}:
                    return val
                case dict():
                    return {k: extract_value(v) for k, v in item.items()}
                case _:
                    return item

        return {
            category: extract_value(settings)
            for category, settings in self.schema.items()
        }

    def load_user_config(self, config_path: Path | str | None = None) -> None:
        """
        Load and merge user configuration with defaults.
        Implements 'Fail Fast' validation on the loaded types.
        """
        path = (
            Path(config_path)
            if config_path
            else ResourceManager.get_user_config_dir() / "config.yaml"
        )

        def deep_update_and_validate(
            source: dict, overrides: dict, schema_section: dict
        ) -> None:
            """
            Update source with overrides, validating types where schema is provided.
            """
            for key, value in overrides.items():
                # Schema lookup
                schema_def = schema_section.get(key)

                # Check 1: Is this a nested section?
                if isinstance(source.get(key), dict) and isinstance(value, dict):
                    # Recurse
                    schema_def if isinstance(
                        schema_def, dict
                    ) and "type" not in schema_def else {}
                    # But wait, schema structure is {key: {value:..., type:...}}
                    # So if source[key] is a section, schema_def is the dict of settings in that section

                    # Logic: In our schema, sections don't have 'type'. Settings do.
                    # If schema[category] exists, pass it down.
                    deep_update_and_validate(source[key], value, schema_def or {})
                else:
                    # Leaf Node: Validate Setting
                    if (
                        schema_def
                        and isinstance(schema_def, dict)
                        and "type" in schema_def
                    ):
                        expected = schema_def["type"]
                        if not ConfigManager._check_type(value, expected):
                            logger.error(
                                f"Config Type Mismatch for '{key}': Expected {expected}, got {type(value).__name__}. keeping default."
                            )
                            continue  # SKIP update, keep default

                    # Apply update
                    source[key] = value

        if path.is_file():
            with suppress(yaml.YAMLError):
                user_config = yaml.safe_load(path.read_text())
                if user_config:
                    # We start validation at the root schema level
                    deep_update_and_validate(self.config, user_config, self.schema)

    @classmethod
    def save_config(cls, config_path: Path | str | None = None) -> None:
        """Save the current configuration to a YAML file."""
        path = (
            Path(config_path)
            if config_path
            else ResourceManager.get_user_config_dir() / "config.yaml"
        )
        if cls._instance is None:
            raise RuntimeError("ConfigManager not initialized")
        path.write_text(yaml.dump(cls._instance.config, default_flow_style=False))

    @classmethod
    def reload_config(cls) -> None:
        """Reload the configuration from the file."""
        if cls._instance is None:
            raise RuntimeError("ConfigManager not initialized")
        cls._instance.config = cls._instance.load_default_config()
        cls._instance.load_user_config()
        cls._instance.config_reloaded.emit()

    @classmethod
    def config_file_exists(cls) -> bool:
        """Check if a valid config file exists."""
        return (ResourceManager.get_user_config_dir() / "config.yaml").is_file()

    @classmethod
    def reset_for_tests(cls) -> None:
        """
        Public API to reset the singleton state for testing purposes only.

        This method allows tests to clean up the singleton state without accessing private attributes directly.
        """
        with cls._lock:
            cls._instance = None


def get_model_cache_dir() -> Path:
    """
    Legacy helper. Use ResourceManager.get_user_cache_dir("models").
    """
    return ResourceManager.get_user_cache_dir("models")
