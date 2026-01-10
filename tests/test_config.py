"""
Tests for configuration loading and management.
"""


class TestConfigManager:
    """Tests for ConfigManager functionality."""

    def test_get_nonexistent_key_returns_none(self, config_manager):
        """Non-existent keys should return None."""
        value = config_manager.get_config_value("nonexistent", "key")
        assert value is None

    def test_get_nested_nonexistent_key(self, config_manager):
        """Deeply nested non-existent keys should return None."""
        value = config_manager.get_config_value("fake", "nested", "deeply", "key")
        assert value is None
