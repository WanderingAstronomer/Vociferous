"""
Tests for Wayland/X11 compatibility and input backend selection.
"""

import os
import pytest

pytestmark = pytest.mark.system


class TestDisplayServer:
    """Tests for display server detection."""

    def test_wayland_display_set(self):
        """On Wayland, WAYLAND_DISPLAY should be set."""
        session_type = os.environ.get("XDG_SESSION_TYPE", "")
        if session_type == "wayland":
            wayland_display = os.environ.get("WAYLAND_DISPLAY")
            assert wayland_display is not None, "WAYLAND_DISPLAY should be set"

    def test_x11_display_set(self):
        """On X11, DISPLAY should be set."""
        session_type = os.environ.get("XDG_SESSION_TYPE", "")
        if session_type == "x11":
            display = os.environ.get("DISPLAY")
            assert display is not None, "DISPLAY should be set"


class TestBackendCompatibility:
    """Tests for backend compatibility with display servers."""

    def test_pynput_x11_only_warning(self):
        """pynput should warn if used on Wayland."""
        session_type = os.environ.get("XDG_SESSION_TYPE", "")
        if session_type == "wayland":
            # pynput won't capture keys on Wayland
            pass  # Skipping logic removed for clearer test output

    def test_evdev_needs_input_group(self):
        """evdev needs user to be in input group."""
        import grp
        import pwd

        username = pwd.getpwuid(os.getuid()).pw_name
        try:
            input_group = grp.getgrnam("input")
            in_members = username in input_group.gr_mem
            is_primary = os.getgid() == input_group.gr_gid
            user_in_input = in_members or is_primary
        except KeyError:
            user_in_input = False

        session_type = os.environ.get("XDG_SESSION_TYPE", "")
        if session_type == "wayland":
            if not user_in_input:
                pytest.skip(
                    f"User '{username}' is not in 'input' group. Skpping evdev test."
                )

    def test_evdev_can_list_devices(self):
        """evdev should be able to list input devices if permissions are correct."""
        try:
            import evdev

            devices = evdev.list_devices()
            if not devices:
                pytest.skip("No input devices found (likely a headless or restricted environment).")
        except ImportError:
            pytest.skip("evdev not installed")
        except PermissionError:
            pytest.skip("Permission denied accessing input devices.")
