"""
Input handler unit tests.

Tests the pure logic in the input handler subsystem without requiring
actual hardware (no keyboard/mouse/evdev needed):
- KeyChord activation detection
- KeyCode and InputEvent enums
- KeyListener key combination parsing
- KeyListener callback mechanism
- Capture mode behavior
"""

from __future__ import annotations

import pytest

from src.input_handler.chord import KeyChord
from src.input_handler.types import InputEvent, KeyCode

# ── KeyChord Basics ───────────────────────────────────────────────────────


class TestKeyChordSingleKey:
    """Chord detection with a single key."""

    def test_single_key_activate_on_press(self):
        chord = KeyChord(keys={KeyCode.SPACE})
        assert not chord.is_active()

        result = chord.update(KeyCode.SPACE, InputEvent.KEY_PRESS)
        assert result is True
        assert chord.is_active()

    def test_single_key_deactivate_on_release(self):
        chord = KeyChord(keys={KeyCode.SPACE})
        chord.update(KeyCode.SPACE, InputEvent.KEY_PRESS)
        assert chord.is_active()

        result = chord.update(KeyCode.SPACE, InputEvent.KEY_RELEASE)
        assert result is False
        assert not chord.is_active()

    def test_unrelated_key_ignored(self):
        chord = KeyChord(keys={KeyCode.SPACE})
        chord.update(KeyCode.A, InputEvent.KEY_PRESS)
        assert not chord.is_active()

    def test_release_unrelated_key_no_effect(self):
        chord = KeyChord(keys={KeyCode.SPACE})
        chord.update(KeyCode.SPACE, InputEvent.KEY_PRESS)
        chord.update(KeyCode.A, InputEvent.KEY_RELEASE)
        assert chord.is_active()


# ── KeyChord Multi-Key ────────────────────────────────────────────────────


class TestKeyChordMultiKey:
    """Chord detection with multiple simultaneous keys."""

    def test_two_key_chord_requires_both(self):
        chord = KeyChord(keys={KeyCode.CTRL_LEFT, KeyCode.SPACE})

        chord.update(KeyCode.CTRL_LEFT, InputEvent.KEY_PRESS)
        assert not chord.is_active()

        chord.update(KeyCode.SPACE, InputEvent.KEY_PRESS)
        assert chord.is_active()

    def test_two_key_chord_order_independent(self):
        chord = KeyChord(keys={KeyCode.CTRL_LEFT, KeyCode.SPACE})

        chord.update(KeyCode.SPACE, InputEvent.KEY_PRESS)
        assert not chord.is_active()

        chord.update(KeyCode.CTRL_LEFT, InputEvent.KEY_PRESS)
        assert chord.is_active()

    def test_releasing_one_key_deactivates_chord(self):
        chord = KeyChord(keys={KeyCode.CTRL_LEFT, KeyCode.SPACE})
        chord.update(KeyCode.CTRL_LEFT, InputEvent.KEY_PRESS)
        chord.update(KeyCode.SPACE, InputEvent.KEY_PRESS)
        assert chord.is_active()

        chord.update(KeyCode.CTRL_LEFT, InputEvent.KEY_RELEASE)
        assert not chord.is_active()

    def test_three_key_chord(self):
        chord = KeyChord(keys={KeyCode.CTRL_LEFT, KeyCode.SHIFT_LEFT, KeyCode.R})

        chord.update(KeyCode.CTRL_LEFT, InputEvent.KEY_PRESS)
        chord.update(KeyCode.SHIFT_LEFT, InputEvent.KEY_PRESS)
        assert not chord.is_active()

        chord.update(KeyCode.R, InputEvent.KEY_PRESS)
        assert chord.is_active()


# ── KeyChord Frozenset (Either-Key) ───────────────────────────────────────


class TestKeyChordFrozenset:
    """Chord with frozenset keys (e.g., either Ctrl key)."""

    def test_frozenset_left_ctrl_activates(self):
        """frozenset({CTRL_LEFT, CTRL_RIGHT}) should activate with either."""
        either_ctrl = frozenset({KeyCode.CTRL_LEFT, KeyCode.CTRL_RIGHT})
        chord = KeyChord(keys={either_ctrl, KeyCode.SPACE})

        chord.update(KeyCode.CTRL_LEFT, InputEvent.KEY_PRESS)
        chord.update(KeyCode.SPACE, InputEvent.KEY_PRESS)
        assert chord.is_active()

    def test_frozenset_right_ctrl_activates(self):
        either_ctrl = frozenset({KeyCode.CTRL_LEFT, KeyCode.CTRL_RIGHT})
        chord = KeyChord(keys={either_ctrl, KeyCode.SPACE})

        chord.update(KeyCode.CTRL_RIGHT, InputEvent.KEY_PRESS)
        chord.update(KeyCode.SPACE, InputEvent.KEY_PRESS)
        assert chord.is_active()

    def test_frozenset_neither_key_stays_inactive(self):
        either_ctrl = frozenset({KeyCode.CTRL_LEFT, KeyCode.CTRL_RIGHT})
        chord = KeyChord(keys={either_ctrl, KeyCode.SPACE})

        chord.update(KeyCode.ALT_LEFT, InputEvent.KEY_PRESS)
        chord.update(KeyCode.SPACE, InputEvent.KEY_PRESS)
        assert not chord.is_active()

    def test_multiple_frozensets(self):
        """Both CTRL and SHIFT as either-key groups."""
        either_ctrl = frozenset({KeyCode.CTRL_LEFT, KeyCode.CTRL_RIGHT})
        either_shift = frozenset({KeyCode.SHIFT_LEFT, KeyCode.SHIFT_RIGHT})
        chord = KeyChord(keys={either_ctrl, either_shift, KeyCode.SPACE})

        chord.update(KeyCode.CTRL_RIGHT, InputEvent.KEY_PRESS)
        chord.update(KeyCode.SHIFT_LEFT, InputEvent.KEY_PRESS)
        assert not chord.is_active()

        chord.update(KeyCode.SPACE, InputEvent.KEY_PRESS)
        assert chord.is_active()


# ── KeyChord Edge Cases ───────────────────────────────────────────────────


class TestKeyChordEdgeCases:
    """Edge cases for chord detection logic."""

    def test_empty_chord_always_active(self):
        """A chord with no required keys is always active (vacuous truth)."""
        chord = KeyChord(keys=set())
        assert chord.is_active()

    def test_repeated_press_idempotent(self):
        """Pressing the same key twice without release is idempotent."""
        chord = KeyChord(keys={KeyCode.SPACE})
        chord.update(KeyCode.SPACE, InputEvent.KEY_PRESS)
        chord.update(KeyCode.SPACE, InputEvent.KEY_PRESS)
        assert chord.is_active()

        chord.update(KeyCode.SPACE, InputEvent.KEY_RELEASE)
        assert not chord.is_active()

    def test_release_without_press_no_crash(self):
        """Releasing a key that was never pressed should not crash."""
        chord = KeyChord(keys={KeyCode.SPACE})
        chord.update(KeyCode.SPACE, InputEvent.KEY_RELEASE)
        assert not chord.is_active()

    def test_pressed_keys_tracks_state(self):
        """Internal pressed_keys set tracks current state accurately."""
        chord = KeyChord(keys={KeyCode.A, KeyCode.B})
        chord.update(KeyCode.A, InputEvent.KEY_PRESS)
        assert KeyCode.A in chord.pressed_keys
        assert KeyCode.B not in chord.pressed_keys

        chord.update(KeyCode.A, InputEvent.KEY_RELEASE)
        assert KeyCode.A not in chord.pressed_keys


# ── KeyCode Enum ──────────────────────────────────────────────────────────


class TestKeyCodeEnum:
    """Verify KeyCode enum completeness and behavior."""

    def test_modifiers_exist(self):
        assert KeyCode.CTRL_LEFT is not None
        assert KeyCode.CTRL_RIGHT is not None
        assert KeyCode.SHIFT_LEFT is not None
        assert KeyCode.ALT_LEFT is not None
        assert KeyCode.META_LEFT is not None

    def test_function_keys_exist(self):
        for i in range(1, 25):
            assert hasattr(KeyCode, f"F{i}")

    def test_letter_keys_exist(self):
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            assert hasattr(KeyCode, letter)

    def test_mouse_buttons_exist(self):
        assert KeyCode.MOUSE_LEFT is not None
        assert KeyCode.MOUSE_RIGHT is not None
        assert KeyCode.MOUSE_MIDDLE is not None

    def test_media_keys_exist(self):
        assert KeyCode.PLAY_PAUSE is not None
        assert KeyCode.VOLUME_UP is not None
        assert KeyCode.MUTE is not None


# ── InputEvent Enum ───────────────────────────────────────────────────────


class TestInputEventEnum:
    """Verify InputEvent enum values."""

    def test_key_events(self):
        assert InputEvent.KEY_PRESS is not None
        assert InputEvent.KEY_RELEASE is not None

    def test_mouse_events(self):
        assert InputEvent.MOUSE_PRESS is not None
        assert InputEvent.MOUSE_RELEASE is not None

    def test_all_values_unique(self):
        values = [e.value for e in InputEvent]
        assert len(values) == len(set(values))


# ── KeyListener.parse_key_combination ─────────────────────────────────────


class TestParseKeyCombination:
    """Test key combination string parsing without initializing backends."""

    @pytest.fixture()
    def parser(self, tmp_path):
        """Get parse_key_combination without starting a full listener."""
        from unittest.mock import patch

        from src.core.settings import init_settings, reset_for_tests

        reset_for_tests()
        init_settings(config_path=tmp_path / "config" / "settings.json")

        with (
            patch("src.input_handler.listener.PluginLoader") as mock_pl,
            patch.object(
                __import__("src.input_handler.listener", fromlist=["KeyListener"]).KeyListener,
                "initialize_backends",
            ),
        ):
            mock_pl.discover_plugins.return_value = None
            mock_pl.get_available_backends.return_value = []

            from src.input_handler.listener import KeyListener

            listener = KeyListener.__new__(KeyListener)
            listener.backends = []
            listener.active_backend = None
            listener.key_chord = None
            listener.callbacks = {"on_activate": [], "on_deactivate": []}
            listener.capture_mode = False
            listener.capture_callback = None

            yield listener.parse_key_combination
            reset_for_tests()

    def test_single_key(self, parser):
        keys = parser("SPACE")
        assert KeyCode.SPACE in keys
        assert len(keys) == 1

    def test_modifier_expands_to_frozenset(self, parser):
        keys = parser("CTRL")
        # CTRL should expand to a frozenset of left/right
        ctrl_set = None
        for k in keys:
            if isinstance(k, frozenset):
                ctrl_set = k
        assert ctrl_set is not None
        assert KeyCode.CTRL_LEFT in ctrl_set
        assert KeyCode.CTRL_RIGHT in ctrl_set

    def test_ctrl_plus_space(self, parser):
        keys = parser("CTRL+SPACE")
        assert len(keys) == 2
        has_frozenset = any(isinstance(k, frozenset) for k in keys)
        assert has_frozenset  # CTRL → frozenset
        assert KeyCode.SPACE in keys

    def test_shift_plus_alt_plus_f5(self, parser):
        keys = parser("SHIFT+ALT+F5")
        assert len(keys) == 3
        assert KeyCode.F5 in keys

    def test_case_insensitive(self, parser):
        keys_upper = parser("CTRL+SPACE")
        keys_lower = parser("ctrl+space")
        assert keys_upper == keys_lower

    def test_extra_whitespace_trimmed(self, parser):
        keys = parser("  CTRL + SPACE  ")
        assert len(keys) == 2

    def test_unknown_key_ignored_with_warning(self, parser):
        keys = parser("CTRL+NONEXISTENT_KEY")
        # Only CTRL should be parsed, unknown key logged and skipped
        assert len(keys) == 1

    def test_empty_string_returns_empty(self, parser):
        keys = parser("")
        assert len(keys) == 0

    def test_meta_modifier(self, parser):
        keys = parser("META+A")
        assert len(keys) == 2
        assert KeyCode.A in keys
        meta_set = None
        for k in keys:
            if isinstance(k, frozenset):
                meta_set = k
        assert meta_set is not None
        assert KeyCode.META_LEFT in meta_set
        assert KeyCode.META_RIGHT in meta_set


# ── KeyListener Callbacks ────────────────────────────────────────────────


class TestKeyListenerCallbacks:
    """Test the callback registration and triggering mechanism."""

    @pytest.fixture()
    def listener(self, tmp_path):
        """A KeyListener with mocked backends for testing callbacks."""
        from unittest.mock import patch

        from src.core.settings import init_settings, reset_for_tests

        reset_for_tests()
        init_settings(config_path=tmp_path / "config" / "settings.json")

        with (
            patch("src.input_handler.listener.PluginLoader") as mock_pl,
        ):
            mock_pl.discover_plugins.return_value = None
            mock_pl.get_available_backends.return_value = []

            from src.input_handler.listener import KeyListener

            listener = KeyListener.__new__(KeyListener)
            listener.backends = []
            listener.active_backend = None
            listener.key_chord = KeyChord(keys={KeyCode.SPACE})
            listener.callbacks = {"on_activate": [], "on_deactivate": []}
            listener.capture_mode = False
            listener.capture_callback = None

            yield listener
            reset_for_tests()

    def test_add_callback(self, listener):
        calls = []
        listener.add_callback("on_activate", lambda: calls.append("fired"))
        assert len(listener.callbacks["on_activate"]) == 1

    def test_trigger_callbacks_fires_all(self, listener):
        calls = []
        listener.add_callback("on_activate", lambda: calls.append("a"))
        listener.add_callback("on_activate", lambda: calls.append("b"))

        listener.trigger_callbacks_for_tests("on_activate")
        assert calls == ["a", "b"]

    def test_unknown_event_add_is_noop(self, listener):
        """Adding a callback for an unknown event name does nothing."""
        listener.add_callback("totally_bogus", lambda: None)
        assert "totally_bogus" not in listener.callbacks

    def test_on_input_event_triggers_activate(self, listener):
        """Pressing the activation key triggers on_activate callbacks."""
        calls = []
        listener.add_callback("on_activate", lambda: calls.append("activated"))

        listener.on_input_event((KeyCode.SPACE, InputEvent.KEY_PRESS))
        assert calls == ["activated"]

    def test_on_input_event_triggers_deactivate(self, listener):
        """Releasing the activation key triggers on_deactivate callbacks."""
        calls = []
        listener.add_callback("on_deactivate", lambda: calls.append("deactivated"))

        # First press, then release
        listener.on_input_event((KeyCode.SPACE, InputEvent.KEY_PRESS))
        listener.on_input_event((KeyCode.SPACE, InputEvent.KEY_RELEASE))
        assert calls == ["deactivated"]

    def test_callback_error_does_not_crash(self, listener):
        """An exception in a callback should not propagate."""

        def bad_callback():
            raise ValueError("boom")

        listener.add_callback("on_activate", bad_callback)

        # Should not raise
        listener.on_input_event((KeyCode.SPACE, InputEvent.KEY_PRESS))


# ── KeyListener Capture Mode ─────────────────────────────────────────────


class TestCaptureMode:
    """Test the capture mode for hotkey rebinding."""

    @pytest.fixture()
    def listener(self, tmp_path):
        from unittest.mock import patch

        from src.core.settings import init_settings, reset_for_tests

        reset_for_tests()
        init_settings(config_path=tmp_path / "config" / "settings.json")

        with patch("src.input_handler.listener.PluginLoader") as mock_pl:
            mock_pl.discover_plugins.return_value = None
            mock_pl.get_available_backends.return_value = []

            from src.input_handler.listener import KeyListener

            listener = KeyListener.__new__(KeyListener)
            listener.backends = []
            listener.active_backend = None
            listener.key_chord = KeyChord(keys={KeyCode.F5})
            listener.callbacks = {"on_activate": [], "on_deactivate": []}
            listener.capture_mode = False
            listener.capture_callback = None

            yield listener
            reset_for_tests()

    def test_enable_capture_mode(self, listener):
        captured = []
        listener.enable_capture_mode(lambda key, event: captured.append((key, event)))
        assert listener.capture_mode is True

    def test_capture_mode_diverts_events(self, listener):
        """In capture mode, events go to capture callback, not chord detection."""
        captured = []
        activate_calls = []

        listener.add_callback("on_activate", lambda: activate_calls.append(True))
        listener.enable_capture_mode(lambda key, event: captured.append((key, event)))

        listener.on_input_event((KeyCode.F5, InputEvent.KEY_PRESS))

        # Capture handler got the event
        assert len(captured) == 1
        assert captured[0] == (KeyCode.F5, InputEvent.KEY_PRESS)

        # Normal activation did NOT fire
        assert activate_calls == []

    def test_disable_capture_mode(self, listener):
        listener.enable_capture_mode(lambda k, e: None)
        listener.disable_capture_mode()
        assert listener.capture_mode is False
        assert listener.capture_callback is None

    def test_normal_detection_resumes_after_capture(self, listener):
        """After disabling capture mode, normal chord detection resumes."""
        calls = []
        listener.add_callback("on_activate", lambda: calls.append("activated"))

        listener.enable_capture_mode(lambda k, e: None)
        listener.disable_capture_mode()

        listener.on_input_event((KeyCode.F5, InputEvent.KEY_PRESS))
        assert calls == ["activated"]

    def test_no_chord_with_capture_mode(self, listener):
        """Capture mode works even when key_chord is None."""
        listener.key_chord = None
        captured = []
        listener.enable_capture_mode(lambda key, event: captured.append((key, event)))
        listener.on_input_event((KeyCode.A, InputEvent.KEY_PRESS))
        assert len(captured) == 1

    def test_no_chord_normal_mode_is_noop(self, listener):
        """With key_chord=None and capture_mode=False, events are silently dropped."""
        listener.key_chord = None
        calls = []
        listener.add_callback("on_activate", lambda: calls.append(True))

        listener.on_input_event((KeyCode.A, InputEvent.KEY_PRESS))
        assert calls == []
