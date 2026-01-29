import json
from pathlib import Path
import shutil

import pytest

from src.provisioning.core import provision_model, ProvisioningError
from src.core.model_registry import MODELS


def fake_convert(model, source_dir: Path, output_dir: Path, progress_callback=None):
    # Simulate conversion by creating a model.bin and copying config
    (output_dir / "model.bin").write_text("fake-model")
    if (source_dir / "config.json").exists():
        shutil.copy2(source_dir / "config.json", output_dir / "config.json")
    if progress_callback:
        progress_callback("fake conversion")


def test_provision_with_valid_offline_source(tmp_path, monkeypatch):
    model = MODELS["qwen4b"]
    cache_root = tmp_path / "cache"
    cache_root.mkdir()

    # Prepare a fake local source with required files
    source = tmp_path / "source"
    source.mkdir()
    (source / "config.json").write_text(json.dumps({"model": "test"}))
    (source / "model.safetensors").write_text("fake-weights")
    (source / "tokenizer.json").write_text(json.dumps({"tok": "vocab"}))

    # Patch convert_model to avoid heavy external calls
    monkeypatch.setattr("src.provisioning.core.convert_model", fake_convert)

    result = provision_model(model, cache_root, progress_callback=lambda m: None, source_dir=source)

    assert result is True
    final = cache_root / model.dir_name
    assert (final / "model.bin").exists()
    assert (final / "config.json").exists()
    assert (final / "tokenizer.json").exists()


def test_provision_with_invalid_offline_source_missing_config(tmp_path):
    model = MODELS["qwen4b"]
    cache_root = tmp_path / "cache"
    cache_root.mkdir()

    # Prepare source missing config.json
    source = tmp_path / "source_missing"
    source.mkdir()
    (source / "model.safetensors").write_text("fake-weights")

    with pytest.raises(ProvisioningError):
        provision_model(model, cache_root, progress_callback=lambda m: None, source_dir=source)
