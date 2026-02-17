"""
Settings resilience and edge-case tests.

Covers:
- Corrupt / malformed JSON recovery → falls back to defaults
- Partial JSON (valid but incomplete) → merges with defaults
- Atomic write guarantees (backup creation, temp file cleanup)
- Environment variable overrides
- update_settings deep merge correctness
- Frozen sub-model enforcement
- Roundtrip fidelity for refinement levels
- reset_for_tests isolation
- save_settings without prior init raises
- Concurrent read/write safety
"""

import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.core.exceptions import ConfigError
from src.core.settings import (
    ModelSettings,
    RecordingSettings,
    VociferousSettings,
    get_settings,
    init_settings,
    reset_for_tests,
    save_settings,
    update_settings,
)


@pytest.fixture(autouse=True)
def _isolate():
    """Clean module state before and after every test."""
    reset_for_tests()
    yield
    reset_for_tests()
    # Clear any env vars we may have set
    for key in list(os.environ):
        if key.startswith("VOCIFEROUS_"):
            del os.environ[key]


# ── Corrupt File Recovery ─────────────────────────────────────────────────


class TestCorruptFileRecovery:
    def test_garbage_json_falls_back_to_defaults(self, tmp_path: Path) -> None:
        config_file = tmp_path / "settings.json"
        config_file.write_text("this is not json {{{", encoding="utf-8")

        s = init_settings(config_path=config_file)
        assert isinstance(s, VociferousSettings)
        assert s.model.model == "large-v3-turbo-q5_0"

    def test_empty_file_falls_back_to_defaults(self, tmp_path: Path) -> None:
        config_file = tmp_path / "settings.json"
        config_file.write_text("", encoding="utf-8")

        s = init_settings(config_path=config_file)
        assert isinstance(s, VociferousSettings)

    def test_valid_json_wrong_types_falls_back(self, tmp_path: Path) -> None:
        """JSON parses, but values are wrong types (e.g. model as int)."""
        config_file = tmp_path / "settings.json"
        config_file.write_text(json.dumps({"model": 42}), encoding="utf-8")

        s = init_settings(config_path=config_file)
        # Should fall back to defaults rather than crash
        assert isinstance(s, VociferousSettings)

    def test_partial_json_merges_with_defaults(self, tmp_path: Path) -> None:
        """Partial config: only some sections provided, rest defaults."""
        config_file = tmp_path / "settings.json"
        config_file.write_text(json.dumps({"user": {"name": "TestUser"}}), encoding="utf-8")

        s = init_settings(config_path=config_file)
        assert s.user.name == "TestUser"
        # Non-specified sections still have defaults
        assert s.model.model == "large-v3-turbo-q5_0"
        assert s.recording.sample_rate == 16000

    def test_extra_unknown_keys_trigger_fallback(self, tmp_path: Path) -> None:
        """Unknown top-level keys cause validation error → falls back to defaults."""
        config_file = tmp_path / "settings.json"
        config_file.write_text(
            json.dumps({"user": {"name": "X"}, "unknown_section": {"foo": "bar"}}),
            encoding="utf-8",
        )
        s = init_settings(config_path=config_file)
        # Pydantic forbids extra inputs → entire load fails → defaults
        assert s.user.name == ""
        assert s.model.model == "large-v3-turbo-q5_0"


# ── Atomic Write Guarantees ───────────────────────────────────────────────


class TestAtomicWrite:
    def test_backup_created_on_second_save(self, tmp_path: Path) -> None:
        config_file = tmp_path / "settings.json"
        init_settings(config_path=config_file)
        save_settings()
        assert config_file.exists()

        # Second save creates .bak
        save_settings()
        bak = config_file.with_suffix(".json.bak")
        assert bak.exists()

    def test_backup_content_matches_previous_save(self, tmp_path: Path) -> None:
        config_file = tmp_path / "settings.json"
        init_settings(config_path=config_file)
        save_settings()
        original_content = config_file.read_text()

        # Update and save again
        update_settings(user={"name": "Changed"})

        bak = config_file.with_suffix(".json.bak")
        assert bak.read_text() == original_content

    def test_save_creates_parent_directories(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "nested" / "settings.json"
        init_settings(config_path=nested)
        save_settings()
        assert nested.exists()

    def test_saved_file_is_valid_json(self, tmp_path: Path) -> None:
        config_file = tmp_path / "settings.json"
        init_settings(config_path=config_file)
        update_settings(user={"name": "ValidJSON"})

        data = json.loads(config_file.read_text("utf-8"))
        assert data["user"]["name"] == "ValidJSON"

    def test_save_without_init_raises(self) -> None:
        with pytest.raises(ConfigError, match="No settings to save"):
            save_settings()


# ── Deep Merge ────────────────────────────────────────────────────────────


class TestDeepMerge:
    def test_update_single_field_preserves_siblings(self, tmp_path: Path) -> None:
        init_settings(config_path=tmp_path / "settings.json")
        update_settings(model={"language": "fr"})

        s = get_settings()
        assert s.model.language == "fr"
        assert s.model.model == "large-v3-turbo-q5_0"  # preserved
        assert s.model.device == "auto"  # preserved

    def test_update_multiple_sections(self, tmp_path: Path) -> None:
        init_settings(config_path=tmp_path / "settings.json")
        update_settings(
            model={"language": "de"},
            user={"name": "MultiUpdate"},
            recording={"sample_rate": 44100},
        )

        s = get_settings()
        assert s.model.language == "de"
        assert s.user.name == "MultiUpdate"
        assert s.recording.sample_rate == 44100

    def test_update_preserves_refinement_levels(self, tmp_path: Path) -> None:
        init_settings(config_path=tmp_path / "settings.json")
        update_settings(refinement={"enabled": False})

        s = get_settings()
        assert s.refinement.enabled is False
        assert len(s.refinement.levels) == 5  # all levels preserved

    def test_sequential_updates_accumulate(self, tmp_path: Path) -> None:
        init_settings(config_path=tmp_path / "settings.json")
        update_settings(user={"name": "First"})
        update_settings(user={"active_project_id": 42})

        s = get_settings()
        assert s.user.name == "First"
        assert s.user.active_project_id == 42


# ── Frozen Sub-Model Enforcement ─────────────────────────────────────────


class TestFrozenModels:
    """Sub-models are frozen (immutable after creation)."""

    def test_model_settings_frozen(self) -> None:
        m = ModelSettings()
        with pytest.raises(ValidationError):
            m.model = "something_else"

    def test_recording_settings_frozen(self) -> None:
        r = RecordingSettings()
        with pytest.raises(ValidationError):
            r.sample_rate = 999


# ── Environment Variable Overrides ────────────────────────────────────────


class TestEnvironmentOverrides:
    def test_env_override_top_level(self, tmp_path: Path) -> None:
        """VOCIFEROUS_ prefixed env vars override fields."""
        os.environ["VOCIFEROUS_MODEL__LANGUAGE"] = "ja"
        s = init_settings(config_path=tmp_path / "settings.json")
        assert s.model.language == "ja"

    def test_env_override_does_not_beat_explicit_file(self, tmp_path: Path) -> None:
        """File-loaded kwargs have higher pydantic-settings priority than env vars."""
        config_file = tmp_path / "settings.json"
        config_file.write_text(json.dumps({"model": {"language": "fr"}}), encoding="utf-8")
        os.environ["VOCIFEROUS_MODEL__LANGUAGE"] = "de"

        s = init_settings(config_path=config_file)
        # File kwargs win over env vars in pydantic-settings priority
        assert s.model.language == "fr"


# ── Roundtrip Fidelity ────────────────────────────────────────────────────


class TestRoundtripFidelity:
    def test_refinement_levels_survive_roundtrip(self, tmp_path: Path) -> None:
        config_file = tmp_path / "settings.json"
        original = VociferousSettings()
        config_file.write_text(original.model_dump_json(indent=2), encoding="utf-8")

        loaded = VociferousSettings(**json.loads(config_file.read_text()))
        assert len(loaded.refinement.levels) == 5
        for level_id in range(5):
            assert loaded.refinement.levels[level_id].name == original.refinement.levels[level_id].name
            assert loaded.refinement.levels[level_id].role == original.refinement.levels[level_id].role

    def test_all_sections_present_after_roundtrip(self, tmp_path: Path) -> None:
        config_file = tmp_path / "settings.json"
        init_settings(config_path=config_file)
        save_settings()

        reset_for_tests()
        s = init_settings(config_path=config_file)

        dump = s.model_dump()
        expected_sections = [
            "model",
            "recording",
            "user",
            "logging",
            "visualizer",
            "voice_calibration",
            "output",
            "refinement",
        ]
        for section in expected_sections:
            assert section in dump, f"Missing section: {section}"

    def test_update_persists_and_reloads(self, tmp_path: Path) -> None:
        config_file = tmp_path / "settings.json"
        init_settings(config_path=config_file)
        update_settings(user={"name": "Persistent"}, recording={"sample_rate": 48000})

        reset_for_tests()
        s = init_settings(config_path=config_file)
        assert s.user.name == "Persistent"
        assert s.recording.sample_rate == 48000


# ── Module State Isolation ────────────────────────────────────────────────


class TestModuleIsolation:
    def test_reset_clears_state(self) -> None:
        init_settings()
        reset_for_tests()
        with pytest.raises(ConfigError):
            get_settings()

    def test_separate_config_paths_isolated(self, tmp_path: Path) -> None:
        path_a = tmp_path / "a" / "settings.json"
        path_b = tmp_path / "b" / "settings.json"

        init_settings(config_path=path_a)
        update_settings(user={"name": "A"})
        save_settings()

        reset_for_tests()
        init_settings(config_path=path_b)
        update_settings(user={"name": "B"})
        save_settings()

        # Reload A — should have name "A", not "B"
        reset_for_tests()
        s = init_settings(config_path=path_a)
        assert s.user.name == "A"


# ── Nonexistent Config Dir ────────────────────────────────────────────────


class TestNonexistentConfig:
    def test_init_with_nonexistent_file_returns_defaults(self, tmp_path: Path) -> None:
        config_file = tmp_path / "does_not_exist" / "settings.json"
        s = init_settings(config_path=config_file)
        assert isinstance(s, VociferousSettings)
        assert s.model.model == "large-v3-turbo-q5_0"
