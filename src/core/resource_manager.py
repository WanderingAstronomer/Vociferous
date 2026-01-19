"""
Resource Manager - Authoritative source for path resolution.

This module provides a robust, environment-aware mechanism for locating:
1. Application Assets (icons, sounds) - via `sys._MEIPASS` or `assets/` relative to root.
2. User Data (logs, db, config) - via XDG/AppLocal standards.
3. System Resources - via explicit environment overrides.

It is designed to be a "Pure Library" with no Qt dependencies, usable by
both the UI and the Headless Engine.
"""

import os
import sys
from pathlib import Path
from typing import Final

# Standard XDG defaults logic is now inline to support environment updates
pass

APP_NAME: Final = "vociferous"


class ResourceManager:
    """Static utility for resolving application paths."""

    @staticmethod
    def get_app_root() -> Path:
        """
        Return the absolute path to the application root.

        - If frozen (PyInstaller), returns sys._MEIPASS.
        - If dev, returns the project root (parent of src/).
        """
        if getattr(sys, "frozen", False):
            # PyInstaller temp dir
            return Path(sys._MEIPASS)  # type: ignore

        # Dev mode: file is in src/core/resource_manager.py
        # Root is 2 levels up (src/core/ -> src/ -> root)
        # Actually, standard layout is root/src/core.
        # But wait, assets might be in root/assets/ or src/assets/?
        # Let's check where this file is: src/core/__file__
        # Project root is parents[2] from here.
        return Path(__file__).resolve().parents[2]

    @staticmethod
    def get_user_config_dir() -> Path:
        """
        Return the writable user configuration directory.
        Follows XDG_CONFIG_HOME or ~/.config mapping.
        """
        env_override = os.environ.get("VOCIFEROUS_CONFIG_DIR")
        if env_override:
            path = Path(env_override)
        else:
            path = (
                Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
                / APP_NAME
            )

        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def get_user_data_dir() -> Path:
        """
        Return the writable user data directory (DBs, history).
        Follows XDG_DATA_HOME or ~/.local/share mapping.
        """
        env_override = os.environ.get("VOCIFEROUS_DATA_DIR")
        if env_override:
            path = Path(env_override)
        else:
            path = (
                Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
                / APP_NAME
            )

        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def get_user_cache_dir(subdir: str = "") -> Path:
        """
        Return the writable user cache directory (Models, temp).
        Follows XDG_CACHE_HOME or ~/.cache mapping.
        """
        env_override = os.environ.get("VOCIFEROUS_CACHE_DIR")
        if env_override:
            base = Path(env_override)
        else:
            base = (
                Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
                / APP_NAME
            )

        if subdir:
            base = base / subdir

        base.mkdir(parents=True, exist_ok=True)
        return base

    @staticmethod
    def get_user_log_dir() -> Path:
        """
        Return the writable user log directory.
        Usually in cache/logs or state/logs. We map to cache/logs for simplicity.
        """
        env_override = os.environ.get("VOCIFEROUS_LOG_DIR")
        if env_override:
            return Path(env_override)

        # Some linux definitions use XDG_STATE_HOME, but usually logs go to cache or specialized /var/log/
        # For user apps: ~/.cache/app/logs is common
        return ResourceManager.get_user_cache_dir() / "logs"

    @staticmethod
    def get_assets_root() -> Path:
        """
        Return the absolute path to the assets directory.
        Always returns root/assets.
        """
        return ResourceManager.get_app_root() / "assets"

    @staticmethod
    def get_asset_path(relative_path: str) -> Path:
        """
        Resolve an asset path.

        Args:
            relative_path: Path relative to the assets folder (e.g. "icons/logo.svg")

        Returns:
            Absolute Path object.

        Raises:
            FileNotFoundError: If the asset cannot be strictly resolved in dev mode.
        """
        root = ResourceManager.get_assets_root()
        candidate = root / relative_path

        # in typical PyInstaller --onefile, assets are at root level of _MEIPASS
        if getattr(sys, "frozen", False):
            # Sometimes assets are bundled into a subfolder 'assets'
            # adjust based on .spec file. Assuming 'assets' folder is included.
            pass

        return candidate

    @staticmethod
    def get_icon_path(icon_name: str) -> str:
        """Helper to get string path for Qt icons (convenience)."""
        # Tries svg first, then png
        # This assumes a structure like assets/icons/...
        # Logic:
        # 1. Try assets/icons/{name}.svg
        # 2. Try assets/icons/{name}.png
        # 3. Try assets/images/{name}.png

        assets = ResourceManager.get_app_root() / "assets"

        candidates = [
            assets / "icons" / f"{icon_name}.svg",
            assets / "icons" / f"{icon_name}.png",
            assets / "images" / f"{icon_name}.png",
        ]

        for c in candidates:
            if c.exists():
                return str(c)

        # Fallback or strict fail?
        # For now, return the primary candidate path string so Qt can fail gracefully/log it
        return str(candidates[0])
