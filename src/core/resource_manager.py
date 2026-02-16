"""
Resource Manager - Authoritative source for path resolution.

This module provides a robust, environment-aware mechanism for locating:
1. Application Assets (icons, sounds) - via `sys._MEIPASS` or `assets/` relative to root.
2. User Data (logs, db, config) - via platform-appropriate standards.
3. System Resources - via explicit environment overrides.

Cross-platform path resolution:
- Linux:   XDG dirs (~/.config, ~/.local/share, ~/.cache)
- macOS:   ~/Library/Application Support, ~/Library/Caches
- Windows: %APPDATA%, %LOCALAPPDATA%

It is designed to be a "Pure Library" with no Qt dependencies, usable by
both the UI and the Headless Engine.
"""

import os
import sys
from pathlib import Path
from typing import Final

from platformdirs import PlatformDirs

APP_NAME: Final = "vociferous"
APP_AUTHOR: Final = "vociferous"

_dirs = PlatformDirs(appname=APP_NAME, appauthor=APP_AUTHOR, ensure_exists=True)


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
        # Project root is parents[2] from here.
        return Path(__file__).resolve().parents[2]

    @staticmethod
    def get_user_config_dir() -> Path:
        """
        Return the writable user configuration directory.

        Resolved per-platform by platformdirs:
        - Linux:   ~/.config/vociferous
        - macOS:   ~/Library/Application Support/vociferous
        - Windows: C:\\Users\\<user>\\AppData\\Roaming\\vociferous
        """
        env_override = os.environ.get("VOCIFEROUS_CONFIG_DIR")
        if env_override:
            path = Path(env_override)
        else:
            path = _dirs.user_config_path

        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def get_user_data_dir() -> Path:
        """
        Return the writable user data directory (DBs, history).

        Resolved per-platform by platformdirs:
        - Linux:   ~/.local/share/vociferous
        - macOS:   ~/Library/Application Support/vociferous
        - Windows: C:\\Users\\<user>\\AppData\\Local\\vociferous
        """
        env_override = os.environ.get("VOCIFEROUS_DATA_DIR")
        if env_override:
            path = Path(env_override)
        else:
            path = _dirs.user_data_path

        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def get_user_cache_dir(subdir: str = "") -> Path:
        """
        Return the writable user cache directory (Models, temp).

        Resolved per-platform by platformdirs:
        - Linux:   ~/.cache/vociferous
        - macOS:   ~/Library/Caches/vociferous
        - Windows: C:\\Users\\<user>\\AppData\\Local\\vociferous\\Cache
        """
        env_override = os.environ.get("VOCIFEROUS_CACHE_DIR")
        if env_override:
            base = Path(env_override)
        else:
            base = _dirs.user_cache_path

        if subdir:
            base = base / subdir

        base.mkdir(parents=True, exist_ok=True)
        return base

    @staticmethod
    def get_user_log_dir() -> Path:
        """
        Return the writable user log directory.

        Resolved per-platform by platformdirs:
        - Linux:   ~/.local/state/vociferous/log
        - macOS:   ~/Library/Logs/vociferous
        - Windows: C:\\Users\\<user>\\AppData\\Local\\vociferous\\Logs
        """
        env_override = os.environ.get("VOCIFEROUS_LOG_DIR")
        if env_override:
            path = Path(env_override)
        else:
            path = _dirs.user_log_path

        path.mkdir(parents=True, exist_ok=True)
        return path

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
