"""
Tests for the v4 Pydantic Settings layer.

Verifies:
- Default initialization
- Module-level API (init_settings, get_settings, save_settings)
- Settings overrides
- Atomic persistence
"""

import json
from pathlib import Path

import pytest

from src.core.exceptions import ConfigError
from src.core.settings import (
    VociferousSettings,
    get_settings,
    init_settings,
    reset_for_tests,
    save_settings,
    update_settings,
)


@pytest.fixture(autouse=True)
def _reset():
    """Ensure clean module state for each test."""
    reset_for_tests()
    yield
    reset_for_tests()


class TestDefaults:
    """Settings should provide sensible defaults without any config file."""

    def test_default_asr_model(self):
        s = VociferousSettings()
        assert s.model.model == "large-v3-turbo-q5_0"

    def test_default_language(self):
        s = VociferousSettings()
        assert s.model.language == "en"

    def test_default_activation_key(self):
        s = VociferousSettings()
        assert s.recording.activation_key == "alt_right"

    def test_default_sample_rate(self):
        s = VociferousSettings()
        assert s.recording.sample_rate == 16000

    def test_default_refinement_enabled(self):
        s = VociferousSettings()
        assert s.refinement.enabled is True

    def test_default_refinement_levels(self):
        s = VociferousSettings()
        assert len(s.refinement.levels) == 5
        assert 0 in s.refinement.levels
        assert 4 in s.refinement.levels

    def test_default_active_project_none(self):
        s = VociferousSettings()
        assert s.user.active_project_id is None


class TestModuleAPI:
    """Module-level settings API (init/get/save)."""

    def test_get_before_init_raises(self):
        with pytest.raises(ConfigError, match="not initialized"):
            get_settings()

    def test_init_returns_settings(self):
        s = init_settings()
        assert isinstance(s, VociferousSettings)

    def test_get_after_init(self):
        init_settings()
        s = get_settings()
        assert isinstance(s, VociferousSettings)

    def test_init_loads_from_file(self, tmp_path: Path):
        config = {"model": {"model": "small-en", "language": "fr"}}
        config_file = tmp_path / "settings.json"
        config_file.write_text(json.dumps(config))

        s = init_settings(config_path=config_file)
        assert s.model.model == "small-en"
        assert s.model.language == "fr"

    def test_save_creates_file(self, tmp_path: Path):
        config_file = tmp_path / "settings.json"
        s = init_settings(config_path=config_file)
        save_settings(s)
        assert config_file.exists()

        loaded = json.loads(config_file.read_text())
        assert loaded["model"]["model"] == "large-v3-turbo-q5_0"

    def test_save_creates_backup(self, tmp_path: Path):
        config_file = tmp_path / "settings.json"
        init_settings(config_path=config_file)
        save_settings()

        # Write again — should create .bak
        save_settings()
        assert (tmp_path / "settings.json.bak").exists()


class TestUpdate:
    """Update settings with partial overrides."""

    def test_update_model(self, tmp_path: Path):
        init_settings(config_path=tmp_path / "settings.json")
        new = update_settings(model={"model": "small-en"})
        assert new.model.model == "small-en"
        # Other fields preserved
        assert new.recording.activation_key == "alt_right"

    def test_update_persists(self, tmp_path: Path):
        config_file = tmp_path / "settings.json"
        init_settings(config_path=config_file)
        update_settings(user={"name": "Drew"})

        # Reload from disk
        reset_for_tests()
        s = init_settings(config_path=config_file)
        assert s.user.name == "Drew"


class TestSerialization:
    """Settings roundtrip through JSON."""

    def test_model_dump_produces_dict(self):
        s = VociferousSettings()
        d = s.model_dump()
        assert isinstance(d, dict)
        assert "model" in d
        assert "recording" in d
        assert "refinement" in d

    def test_roundtrip(self, tmp_path: Path):
        config_file = tmp_path / "settings.json"
        original = VociferousSettings()
        config_file.write_text(original.model_dump_json(indent=2))

        loaded = VociferousSettings(**json.loads(config_file.read_text()))
        assert loaded.model.model == original.model.model
        assert loaded.refinement.levels[2].name == "Neutral"
