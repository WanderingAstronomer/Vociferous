import sys
from pathlib import Path

# Adjust path to import src
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

try:
    from src.core.resource_manager import ResourceManager

    print("=== Resource Manager Verification ===")
    print(f"App Root: {ResourceManager.get_app_root()}")

    # Check for XDG compliance via internal methods or implied paths
    try:
        from src.core.config_manager import ConfigManager

        print(
            f"Config Manager Path: {ConfigManager.config_path if hasattr(ConfigManager, 'config_path') else 'Unknown'}"
        )
    except ImportError:
        print("ConfigManager not importable")

    # Check assets - verify actual icons that exist
    try:
        # Test with actual icon files currently in use
        test_icons = [
            "rail_icon-history_view.svg",
            "rail_icon-transcribe_view.svg",
            "rail_icon-refine_view.svg",
        ]

        all_passed = True
        for icon_name in test_icons:
            icon_path = ResourceManager.get_asset_path(f"icons/{icon_name}")
            exists = icon_path.exists()
            status = "✓" if exists else "✗"
            print(f"{status} icons/{icon_name}: {icon_path} (Exists: {exists})")
            if not exists:
                all_passed = False

        if all_passed:
            print("\n✅ All icon assets resolved successfully")
        else:
            print("\n❌ Some icon assets missing")

    except Exception as e:
        print(f"Asset Resolution Failed: {e}")

except ImportError as e:
    print(f"CRITICAL: Failed to import resource_manager: {e}")
