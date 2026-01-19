import os
import sys
from pathlib import Path
import pytest
from src.core.resource_manager import ResourceManager


# Mock environment for testing
@pytest.fixture
def mock_env_vars(monkeypatch):
    monkeypatch.setenv("VOCIFEROUS_CONFIG_DIR", "/tmp/voci_test/config")
    monkeypatch.setenv("VOCIFEROUS_DATA_DIR", "/tmp/voci_test/data")
    monkeypatch.setenv("VOCIFEROUS_CACHE_DIR", "/tmp/voci_test/cache")
    monkeypatch.setenv("VOCIFEROUS_LOG_DIR", "/tmp/voci_test/logs")


def test_resource_manager_contract_exists():
    """Assert the ResourceManager has the required contract methods."""
    assert hasattr(ResourceManager, "get_app_root")
    assert hasattr(ResourceManager, "get_asset_path")
    # New XDG methods required by Amendment
    assert hasattr(ResourceManager, "get_user_config_dir")
    assert hasattr(ResourceManager, "get_user_data_dir")
    assert hasattr(ResourceManager, "get_user_cache_dir")
    assert hasattr(ResourceManager, "get_user_log_dir")


def test_xdg_overrides(mock_env_vars):
    """Assert environment variables override XDG defaults."""
    assert ResourceManager.get_user_config_dir() == Path("/tmp/voci_test/config")
    assert ResourceManager.get_user_data_dir() == Path("/tmp/voci_test/data")


def test_asset_resolution_sanity():
    """Assert we can resolve the root asset directory."""
    # We expect 'assets' to exist in the repo
    asset_path = ResourceManager.get_asset_path("")
    assert asset_path.name == "assets"
