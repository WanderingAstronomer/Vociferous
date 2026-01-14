"""
Tests for key listener and hotkey detection.
"""

import pytest
import sys
import logging

from input_handler import EvdevBackend, InputEvent, KeyChord, KeyCode, PynputBackend


class TestKeyCode:
    """Tests for KeyCode enum."""

    def test_backquote_exists(self):
        """BACKQUOTE key should exist."""
        assert hasattr(KeyCode, "BACKQUOTE")
        assert KeyCode.BACKQUOTE is not None

    def test_modifier_keys_exist(self):
        """Common modifier keys should exist."""
        assert hasattr(KeyCode, "CTRL_LEFT")
        assert hasattr(KeyCode, "CTRL_RIGHT")
        assert hasattr(KeyCode, "SHIFT_LEFT")
        assert hasattr(KeyCode, "ALT_LEFT")
        assert hasattr(KeyCode, "ALT_RIGHT")

    def test_special_keys_exist(self):
        """Special keys should exist."""
        assert hasattr(KeyCode, "SPACE")
        assert hasattr(KeyCode, "ENTER")
        assert hasattr(KeyCode, "TAB")


class TestKeyChord:
    """Tests for KeyChord functionality."""

    def test_single_key_chord(self):
        """Single key chord should activate on press."""
        chord = KeyChord({KeyCode.BACKQUOTE})

        assert not chord.is_active()

        # Press the key
        result = chord.update(KeyCode.BACKQUOTE, InputEvent.KEY_PRESS)
        assert result is True
        assert chord.is_active()

        # Release the key
        result = chord.update(KeyCode.BACKQUOTE, InputEvent.KEY_RELEASE)
        assert result is False
        assert not chord.is_active()

    def test_multi_key_chord(self):
        """Multi-key chord should only activate when all pressed."""
        chord = KeyChord({KeyCode.CTRL_LEFT, KeyCode.SPACE})

        # Press just CTRL
        chord.update(KeyCode.CTRL_LEFT, InputEvent.KEY_PRESS)
        assert not chord.is_active()

        # Press SPACE while holding CTRL
        chord.update(KeyCode.SPACE, InputEvent.KEY_PRESS)
        assert chord.is_active()

        # Release one key
        chord.update(KeyCode.CTRL_LEFT, InputEvent.KEY_RELEASE)
        assert not chord.is_active()

    def test_modifier_group_chord(self):
        """Modifier groups (e.g., any CTRL) should work."""
        # frozenset means "any of these"
        ctrl_group = frozenset({KeyCode.CTRL_LEFT, KeyCode.CTRL_RIGHT})
        chord = KeyChord({ctrl_group, KeyCode.SPACE})

        # Press left CTRL + SPACE
        chord.update(KeyCode.CTRL_LEFT, InputEvent.KEY_PRESS)
        chord.update(KeyCode.SPACE, InputEvent.KEY_PRESS)
        assert chord.is_active()

        chord.update(KeyCode.CTRL_LEFT, InputEvent.KEY_RELEASE)
        chord.update(KeyCode.SPACE, InputEvent.KEY_RELEASE)

        # Press right CTRL + SPACE
        chord.update(KeyCode.CTRL_RIGHT, InputEvent.KEY_PRESS)
        chord.update(KeyCode.SPACE, InputEvent.KEY_PRESS)
        assert chord.is_active()


class TestKeyListener:
    """Tests for KeyListener functionality."""

    def test_parse_single_key(self, key_listener):
        """Should parse single key names."""
        keys = key_listener.parse_key_combination("backquote")
        assert KeyCode.BACKQUOTE in keys

    def test_parse_key_combo(self, key_listener):
        """Should parse key combinations with +."""
        keys = key_listener.parse_key_combination("ctrl+shift+space")

        # CTRL and SHIFT are frozensets (any left/right)
        assert any(isinstance(k, frozenset) for k in keys)

    def test_parse_unknown_key_handled(self, key_listener, caplog):
        """Should handle unknown keys gracefully by logging a warning."""
        caplog.clear()
        with caplog.at_level(logging.WARNING):
            keys = key_listener.parse_key_combination("unknown_key_xyz")
            # Should be empty or partial
            assert len(keys) == 0
            
            # Assert Log
            assert "Unknown key" in caplog.text

    def test_backend_selection(self, key_listener):
        """Should select appropriate backend."""
        # This depends on system, but at least one should be active or attempt made
        if not key_listener.backends:
             # Could happen in stripped CI env
             pytest.skip("No input backends available on this system")
             
        assert key_listener.active_backend is not None


class TestEvdevBackend:
    """Tests specifically for Evdev backend (Linux only)."""
    
    def test_evdev_importable(self):
        if sys.platform != "linux":
            pytest.skip("Evdev is Linux only")
            
        try:
            import evdev
        except ImportError:
            pytest.skip("evdev not installed")
        
        assert evdev is not None
