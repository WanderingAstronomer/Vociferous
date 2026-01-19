import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from src.core.config_manager import ConfigManager


# Reset singleton between tests
@pytest.fixture(autouse=True)
def reset_singleton():
    ConfigManager._instance = None
    yield
    ConfigManager._instance = None


@pytest.fixture
def mock_resource_manager(tmp_path):
    with patch("src.core.config_manager.ResourceManager") as mock:
        # User config dir
        mock.get_user_config_dir.return_value = tmp_path
        # App root (for schema) - we'll treat tmp_path as root for test
        mock.get_app_root.return_value = tmp_path
        yield mock


def create_dummy_schema(path: Path):
    """Create a minimal schema file."""
    import yaml

    schema = {
        "app": {
            "version": {"value": 1, "type": "int"},
            "debug": {"value": False, "type": "bool"},
        },
        "nested": {"item": {"value": "default", "type": "str"}},
    }
    with open(path / "config_schema.yaml", "w") as f:
        yaml.dump(schema, f)


def test_api_improvements(mock_resource_manager, tmp_path):
    """Test get_value with default fallback."""
    (tmp_path / "src").mkdir()  # Ensure src exists
    create_dummy_schema(tmp_path / "src")  # Schema usually in src/ or root

    # We need to mock where it looks for schema.
    # Current implementation looks at schema_path arg or default.
    # Refactor will likely look in ResourceManager.get_app_root() / "src" / "config_schema.yaml"
    # or just ResourceManager.get_app_root() / "config_schema.yaml"

    # Let's assume we place it where the code expects it for now,
    # but the test is asserting the behavior of the NEW methods we will add.

    # Manually initialize to control the path
    schema_path = tmp_path / "config_schema.yaml"
    create_dummy_schema(tmp_path)

    ConfigManager.initialize(schema_path=str(schema_path))

    # 1. Existing key
    val = ConfigManager.get_value("app", "version")
    assert val == 1

    # 2. Missing key with default
    val = ConfigManager.get_value("app", "missing", default=999)
    assert val == 999

    # 3. Missing section with default
    val = ConfigManager.get_value("missing_section", "key", default="fallback")
    assert val == "fallback"

    # 4. None existing, no default -> returns None (Backwards compat check)
    val = ConfigManager.get_value("app", "missing")
    assert val is None


def test_type_enforcement_on_set(mock_resource_manager, tmp_path):
    """Test that set_value validates types against schema."""
    schema_path = tmp_path / "config_schema.yaml"
    create_dummy_schema(tmp_path)
    ConfigManager.initialize(schema_path=str(schema_path))

    # 1. Valid set
    ConfigManager.set_value(True, "app", "debug")
    assert ConfigManager.get_value("app", "debug") is True

    # 2. Invalid set (Type Mismatch)
    # The current implementation DOES NOT validate. We want to add this.
    # So we expect this to raise TypeError or ValueError after our changes.
    with pytest.raises((TypeError, ValueError)):
        ConfigManager.set_value("not_a_bool", "app", "debug")


def test_fail_fast_on_invalid_user_config(mock_resource_manager, tmp_path):
    """Test that loading an invalid user config logs error or normalizes it."""
    # Create schema
    schema_path = tmp_path / "config_schema.yaml"
    create_dummy_schema(tmp_path)

    # Create User Config with mismatch
    user_config = {
        "app": {
            "version": "bad_string"  # Should be int
        }
    }
    import yaml

    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(user_config, f)

    # Mock config filename resolution to point to this file
    # ConfigManager usually looks in user_config_dir / config.yaml
    # We mocked user_config_dir to be tmp_path

    # Initialize
    ConfigManager.initialize(schema_path=str(schema_path))

    # Assertion: The bad value should either be rejected (reset to default)
    # or cause an initialization error.
    # "Fail Fast" usually means alerting the user, but for autofix logic,
    # we might prefer resetting to default.
    # Let's mandate: Invalid types revert to Schema Default.

    assert ConfigManager.get_value("app", "version") == 1  # Schema default
