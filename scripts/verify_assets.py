#!/usr/bin/env python3
"""
Verify asset resolution logic.
Checks:
1. App root detection.
2. Assets root detection.
3. Existence of critical assets.
4. Consistency of ResourceManager paths.
"""

import sys
from pathlib import Path

# Add src to path so we can import modules
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

try:
    from core.resource_manager import ResourceManager
except ImportError:
    print("Could not import ResourceManager. Check python path.")
    sys.exit(1)


def check_asset(path: Path, description: str):
    if path.exists():
        print(f"[OK] {description}: {path}")
        return True
    else:
        print(f"[ERROR] MISSING {description}: {path}")
        return False


def main():
    print("=== Asset Verification Report ===")
    success = True

    # Check roots
    try:
        app_root = ResourceManager.get_app_root()
        assets_root = ResourceManager.get_assets_root()
        print(f"App Root: {app_root}")
        print(f"Assets Root: {assets_root}")
    except Exception as e:
        print(f"[ERROR] Failed to resolve roots: {e}")
        sys.exit(1)

    if not assets_root.exists():
        print(
            f"[CRITICAL] Assets root does not exist at expected location: {assets_root}"
        )
        sys.exit(1)

    # 1. Unified Stylesheet Source
    try:
        from ui.styles.unified_stylesheet import get_unified_stylesheet

        sheet = get_unified_stylesheet()
        if sheet and len(sheet) > 100:
            print(f"[OK] Unified Stylesheet: Generated ({len(sheet)} bytes)")
        else:
            print("[ERROR] Unified Stylesheet: Generated output is empty or too small")
            success = False
    except ImportError:
        print(
            "[ERROR] Unified Stylesheet: Could not import ui.styles.unified_stylesheet"
        )
        success = False
    except Exception as e:
        print(f"[ERROR] Unified Stylesheet: Failed to generate: {e}")
        success = False

    # 2. Critical Icons
    critical_icons = [
        # IconRail
        "rail_icon-transcribe_view",
        "rail_icon-history_view",
        "rail_icon-projects_view",
        "rail_icon-search_view",
        "rail_icon-refine_view",
        "rail_icon-profile_view",
        "rail_icon-settings_view",
        # Title Bars
        "title_bar-minimize",
        "title_bar-maximize",
        "title_bar-close",
        # Miscelleneous
        "system_tray_icon",
        "github",
        "motd_icon-refresh",
    ]

    print("\n--- Verifying Icons ---")
    for icon_name in critical_icons:
        icon_path_str = ResourceManager.get_icon_path(icon_name)
        icon_path = Path(icon_path_str)
        if not check_asset(icon_path, f"Icon '{icon_name}'"):
            success = False

    # 3. Fonts (Optional directory check)
    print("\n--- Verifying Fonts ---")
    font_path = assets_root / "fonts"
    if font_path.exists():
        fonts = list(font_path.glob("*.*"))
        if fonts:
            print(f"[OK] Fonts: Found {len(fonts)} fonts in {font_path}")
        else:
            print(f"[WARNING] Fonts: Directory exists but is empty: {font_path}")
    else:
        print("[INFO] Fonts: Directory not present (using system fonts)")

    # 4. Sound Resources (Optional)
    print("\n--- Verifying Sounds ---")
    sound_path = assets_root / "sounds"
    if sound_path.exists():
        sounds = list(sound_path.glob("*.*"))
        if sounds:
            print(f"[OK] Sounds: Found {len(sounds)} sounds")
        else:
            print("[INFO] Sounds: Directory exists but is empty")
    else:
        print("[INFO] Sounds: Directory not present")

    print("\n=== Verification Complete ===")
    if not success:
        print("[FAIL] One or more critical assets are missing or soul-less.")
        sys.exit(1)
    else:
        print("[PASS] All critical assets verified.")
        sys.exit(0)


if __name__ == "__main__":
    main()
