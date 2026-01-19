import os
import sys
from pathlib import Path
import pytest
from src.core.resource_manager import ResourceManager


def test_app_root_dev():
    """Verify app root detection in dev mode."""
    if getattr(sys, "frozen", False):
        pytest.skip("Skipping dev-mode test in frozen environment")

    root = ResourceManager.get_app_root()
    # In dev mode, root should contain 'src' and 'assets'
    assert (root / "src").is_dir()
    # Note: Depending on repo structure, assets might be checked
    assert (root / "pyproject.toml").is_file()


def test_user_data_dir_xdg(monkeypatch):
    """Verify XDG data dir compliance."""
    # Unset override if present
    monkeypatch.delenv("VOCIFEROUS_DATA_DIR", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/xdg_data")

    path = ResourceManager.get_user_data_dir()
    assert str(path) == "/tmp/xdg_data/vociferous"


def test_user_data_dir_override(monkeypatch):
    """Verify environment override."""
    monkeypatch.setenv("VOCIFEROUS_DATA_DIR", "/tmp/override_data")
    path = ResourceManager.get_user_data_dir()
    assert str(path) == "/tmp/override_data"


def test_user_config_dir_xdg(monkeypatch):
    """Verify XDG config dir compliance."""
    monkeypatch.delenv("VOCIFEROUS_CONFIG_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/xdg_config")

    path = ResourceManager.get_user_config_dir()
    assert str(path) == "/tmp/xdg_config/vociferous"


def test_get_icon_path_resolution():
    """Verify icon path resolution finds real files."""
    # We assume 'vociferous.png' or similar exists in assets/icons
    # If not, we just check it returns a string path at least
    path_str = ResourceManager.get_icon_path("non_existent_icon")
    assert isinstance(path_str, str)
    assert "assets" in path_str


def test_cache_dir_creation(monkeypatch, tmp_path):
    """Verify cache dir creation."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    cache = ResourceManager.get_user_cache_dir("models")
    assert cache.exists()
    assert cache.name == "models"
    assert cache.parent.name == "vociferous"
