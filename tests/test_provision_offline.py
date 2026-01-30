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

    # Manifest must exist and include checksums
    manifest_path = final / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text())
    assert "files" in manifest and "model.bin" in manifest["files"]

    # Verify checksum matches actual file
    import hashlib

    def _sha256_hex(p: Path) -> str:
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    assert manifest["files"]["model.bin"] == _sha256_hex(final / "model.bin")

+def test_provision_cleanup_on_conversion_failure(tmp_path, monkeypatch):
+    """If conversion fails, no final model dir should be left and temps cleaned up."""
+    model = MODELS["qwen4b"]
+    cache_root = tmp_path / "cache"
+    cache_root.mkdir()
+
+    source = tmp_path / "source"
+    source.mkdir()
+    (source / "config.json").write_text(json.dumps({"model": "test"}))
+    (source / "model.safetensors").write_text("fake-weights")
+
+    # Simulate partial write then failure inside convert_model
+    def bad_convert(model_arg, source_dir: Path, output_dir: Path, progress_callback=None):
+        (output_dir / "model.bin").write_text("partial")
+        raise RuntimeError("simulated crash during conversion")
+
+    monkeypatch.setattr("src.provisioning.core.convert_model", bad_convert)
+
+    with pytest.raises(Exception):
+        provision_model(model, cache_root, progress_callback=lambda m: None, source_dir=source)
+
+    final = cache_root / model.dir_name
+    # Final dir must not exist
+    assert not final.exists()
+
+    # No lingering temp dirs starting with model.dir_name.tmp-
+    temps = [p for p in cache_root.iterdir() if p.is_dir() and p.name.startswith(f"{model.dir_name}.tmp-")]
+    assert temps == []


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
