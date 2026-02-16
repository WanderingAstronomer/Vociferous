"""
Tests for the model provisioning pipeline.

Covers:
  - src.provisioning.core (download_model_file, provision_asr_model, provision_slm_model)
  - src.provisioning.requirements (check_dependencies, verify_environment_integrity)
  - src.core.model_registry (catalog lookups, data integrity)

All HuggingFace downloads are mocked — no network calls.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.model_registry import (
    ASR_MODELS,
    SLM_MODELS,
    ASRModel,
    SLMModel,
    get_asr_model,
    get_model_catalog,
    get_slm_model,
)
from src.provisioning.core import (
    ProvisioningError,
    download_model_file,
    provision_asr_model,
    provision_slm_model,
)
from src.provisioning.requirements import (
    REQUIRED_DEPENDENCIES,
    check_dependencies,
    get_missing_dependency_message,
    verify_environment_integrity,
)

# ======================================================================
# Model Registry
# ======================================================================


class TestModelRegistry:
    """Catalog integrity and lookup behaviour."""

    def test_asr_catalog_not_empty(self):
        assert len(ASR_MODELS) > 0

    def test_slm_catalog_not_empty(self):
        assert len(SLM_MODELS) > 0

    def test_asr_model_ids_match_keys(self):
        for key, model in ASR_MODELS.items():
            assert model.id == key, f"Key '{key}' != model.id '{model.id}'"

    def test_slm_model_ids_match_keys(self):
        for key, model in SLM_MODELS.items():
            assert model.id == key, f"Key '{key}' != model.id '{model.id}'"

    def test_asr_models_have_required_fields(self):
        for model in ASR_MODELS.values():
            assert model.name
            assert model.filename
            assert model.repo
            assert model.size_mb > 0
            assert model.tier in ("fast", "balanced", "quality")

    def test_slm_models_have_required_fields(self):
        for model in SLM_MODELS.values():
            assert model.name
            assert model.filename
            assert model.repo
            assert model.size_mb > 0
            assert model.tier in ("fast", "balanced", "quality", "pro")
            assert model.quant  # non-empty quant string

    def test_asr_filenames_are_ggml(self):
        """ASR models must be GGML binaries."""
        for model in ASR_MODELS.values():
            assert model.filename.startswith("ggml-"), model.filename
            assert model.filename.endswith(".bin"), model.filename

    def test_slm_filenames_are_gguf(self):
        """SLM models must be GGUF files."""
        for model in SLM_MODELS.values():
            assert model.filename.endswith(".gguf"), model.filename

    def test_get_asr_model_found(self):
        key = next(iter(ASR_MODELS))
        result = get_asr_model(key)
        assert result is not None
        assert result.id == key

    def test_get_asr_model_missing(self):
        assert get_asr_model("nonexistent-model") is None

    def test_get_slm_model_found(self):
        key = next(iter(SLM_MODELS))
        result = get_slm_model(key)
        assert result is not None
        assert result.id == key

    def test_get_slm_model_missing(self):
        assert get_slm_model("nonexistent-model") is None

    def test_get_model_catalog_structure(self):
        catalog = get_model_catalog()
        assert "asr" in catalog
        assert "slm" in catalog
        assert len(catalog["asr"]) == len(ASR_MODELS)
        assert len(catalog["slm"]) == len(SLM_MODELS)

    def test_catalog_entries_are_dicts(self):
        catalog = get_model_catalog()
        for entry in catalog["asr"].values():
            assert isinstance(entry, dict)
            assert "id" in entry
            assert "filename" in entry
        for entry in catalog["slm"].values():
            assert isinstance(entry, dict)
            assert "id" in entry
            assert "filename" in entry

    def test_models_are_frozen(self):
        model = next(iter(ASR_MODELS.values()))
        with pytest.raises(AttributeError):
            model.name = "hacked"  # type: ignore[misc]

    def test_no_duplicate_filenames_within_type(self):
        asr_filenames = [m.filename for m in ASR_MODELS.values()]
        assert len(asr_filenames) == len(set(asr_filenames)), "Duplicate ASR filenames"
        slm_filenames = [m.filename for m in SLM_MODELS.values()]
        assert len(slm_filenames) == len(set(slm_filenames)), "Duplicate SLM filenames"

    def test_no_duplicate_repos_per_asr(self):
        """All ASR models currently come from the same repo — sanity check."""
        repos = {m.repo for m in ASR_MODELS.values()}
        assert len(repos) >= 1  # at least one repo

    def test_size_ordering_within_asr(self):
        """Models should be listed from smallest to largest."""
        sizes = [m.size_mb for m in ASR_MODELS.values()]
        assert sizes == sorted(sizes), "ASR models not in ascending size order"


# ======================================================================
# download_model_file
# ======================================================================


class TestDownloadModelFile:
    """Core download function — hf_hub_download is always mocked."""

    HF_PATCH = "huggingface_hub.hf_hub_download"

    @patch(HF_PATCH)
    def test_successful_download(self, mock_hf: MagicMock, tmp_path: Path):
        expected = tmp_path / "model.bin"
        mock_hf.return_value = str(expected)

        result = download_model_file(
            repo_id="org/repo",
            filename="model.bin",
            target_dir=tmp_path,
        )

        assert result == expected
        mock_hf.assert_called_once_with(
            repo_id="org/repo",
            filename="model.bin",
            local_dir=str(tmp_path),
            local_dir_use_symlinks=False,
        )

    @patch(HF_PATCH)
    def test_creates_target_directory(self, mock_hf: MagicMock, tmp_path: Path):
        nested = tmp_path / "deep" / "nested" / "dir"
        mock_hf.return_value = str(nested / "model.bin")

        download_model_file(
            repo_id="org/repo",
            filename="model.bin",
            target_dir=nested,
        )

        assert nested.exists()

    @patch(HF_PATCH)
    def test_progress_callback_called(self, mock_hf: MagicMock, tmp_path: Path):
        mock_hf.return_value = str(tmp_path / "model.bin")
        callback = MagicMock()

        download_model_file(
            repo_id="org/repo",
            filename="model.bin",
            target_dir=tmp_path,
            progress_callback=callback,
        )

        # Should be called at least for "Downloading..." and "Downloaded...successfully"
        assert callback.call_count >= 2
        first_msg = callback.call_args_list[0][0][0]
        assert "Downloading" in first_msg
        last_msg = callback.call_args_list[-1][0][0]
        assert "successfully" in last_msg

    @patch(HF_PATCH)
    def test_no_callback_no_crash(self, mock_hf: MagicMock, tmp_path: Path):
        mock_hf.return_value = str(tmp_path / "model.bin")

        # Should not raise when progress_callback is None
        result = download_model_file(
            repo_id="org/repo",
            filename="model.bin",
            target_dir=tmp_path,
            progress_callback=None,
        )
        assert result == tmp_path / "model.bin"

    @patch(HF_PATCH)
    def test_hf_error_wraps_in_provisioning_error(self, mock_hf: MagicMock, tmp_path: Path):
        mock_hf.side_effect = ConnectionError("network down")

        with pytest.raises(ProvisioningError, match="Failed to download"):
            download_model_file(
                repo_id="org/repo",
                filename="model.bin",
                target_dir=tmp_path,
            )

    @patch(HF_PATCH)
    def test_provisioning_error_preserves_cause(self, mock_hf: MagicMock, tmp_path: Path):
        original = OSError("disk full")
        mock_hf.side_effect = original

        with pytest.raises(ProvisioningError) as exc_info:
            download_model_file(
                repo_id="org/repo",
                filename="model.bin",
                target_dir=tmp_path,
            )
        assert exc_info.value.__cause__ is original

    @patch(HF_PATCH)
    def test_callback_not_called_on_failure(self, mock_hf: MagicMock, tmp_path: Path):
        mock_hf.side_effect = RuntimeError("boom")
        callback = MagicMock()

        with pytest.raises(ProvisioningError):
            download_model_file(
                repo_id="org/repo",
                filename="model.bin",
                target_dir=tmp_path,
                progress_callback=callback,
            )

        # "Downloading..." message fires before attempt, "Downloaded...successfully" does NOT
        assert callback.call_count == 1
        assert "Downloading" in callback.call_args_list[0][0][0]


# ======================================================================
# provision_asr_model / provision_slm_model
# ======================================================================


class TestProvisionWrappers:
    """Thin wrappers that delegate to download_model_file."""

    HF_PATCH = "huggingface_hub.hf_hub_download"

    @patch(HF_PATCH)
    def test_provision_asr_delegates(self, mock_hf: MagicMock, tmp_path: Path):
        model = next(iter(ASR_MODELS.values()))
        mock_hf.return_value = str(tmp_path / model.filename)

        result = provision_asr_model(model, tmp_path)

        mock_hf.assert_called_once_with(
            repo_id=model.repo,
            filename=model.filename,
            local_dir=str(tmp_path),
            local_dir_use_symlinks=False,
        )
        assert result == tmp_path / model.filename

    @patch(HF_PATCH)
    def test_provision_slm_delegates(self, mock_hf: MagicMock, tmp_path: Path):
        model = next(iter(SLM_MODELS.values()))
        mock_hf.return_value = str(tmp_path / model.filename)

        result = provision_slm_model(model, tmp_path)

        mock_hf.assert_called_once_with(
            repo_id=model.repo,
            filename=model.filename,
            local_dir=str(tmp_path),
            local_dir_use_symlinks=False,
        )
        assert result == tmp_path / model.filename

    @patch(HF_PATCH)
    def test_provision_asr_with_callback(self, mock_hf: MagicMock, tmp_path: Path):
        model = next(iter(ASR_MODELS.values()))
        mock_hf.return_value = str(tmp_path / model.filename)
        cb = MagicMock()

        provision_asr_model(model, tmp_path, progress_callback=cb)

        assert cb.call_count >= 2

    @patch(HF_PATCH)
    def test_provision_slm_with_callback(self, mock_hf: MagicMock, tmp_path: Path):
        model = next(iter(SLM_MODELS.values()))
        mock_hf.return_value = str(tmp_path / model.filename)
        cb = MagicMock()

        provision_slm_model(model, tmp_path, progress_callback=cb)

        assert cb.call_count >= 2

    @patch(HF_PATCH)
    def test_provision_asr_propagates_error(self, mock_hf: MagicMock, tmp_path: Path):
        mock_hf.side_effect = Exception("fail")
        model = next(iter(ASR_MODELS.values()))

        with pytest.raises(ProvisioningError):
            provision_asr_model(model, tmp_path)

    @patch(HF_PATCH)
    def test_provision_slm_propagates_error(self, mock_hf: MagicMock, tmp_path: Path):
        mock_hf.side_effect = Exception("fail")
        model = next(iter(SLM_MODELS.values()))

        with pytest.raises(ProvisioningError):
            provision_slm_model(model, tmp_path)


# ======================================================================
# Requirements checking
# ======================================================================


class TestRequirements:
    """Dependency detection and environment verification."""

    def test_check_dependencies_default_list(self):
        """Should check the REQUIRED_DEPENDENCIES list by default."""
        installed, missing = check_dependencies()
        assert len(installed) + len(missing) == len(REQUIRED_DEPENDENCIES)

    def test_check_dependencies_custom_list(self):
        installed, missing = check_dependencies(["sys", "os", "nonexistent_pkg_xyz"])
        assert "sys" in installed
        assert "os" in installed
        assert "nonexistent_pkg_xyz" in missing

    def test_check_all_installed(self):
        """All stdlib packages should report as installed."""
        installed, missing = check_dependencies(["sys", "os", "json"])
        assert len(installed) == 3
        assert len(missing) == 0

    def test_check_all_missing(self):
        installed, missing = check_dependencies(["fake_pkg_aaa", "fake_pkg_bbb"])
        assert len(installed) == 0
        assert len(missing) == 2

    def test_check_empty_list(self):
        installed, missing = check_dependencies([])
        assert installed == []
        assert missing == []

    def test_missing_message_empty_when_none_missing(self):
        msg = get_missing_dependency_message([])
        assert msg == ""

    def test_missing_message_contains_package_names(self):
        msg = get_missing_dependency_message(["fake_a", "fake_b"])
        assert "fake_a" in msg
        assert "fake_b" in msg

    def test_missing_message_contains_install_hint(self):
        msg = get_missing_dependency_message(["fake_a"])
        assert "pip install" in msg

    def test_verify_environment_passes_when_all_present(self):
        """If all deps are importable, no error is raised."""
        with patch(
            "src.provisioning.requirements.check_dependencies",
            return_value=(REQUIRED_DEPENDENCIES, []),
        ):
            verify_environment_integrity()  # should not raise

    def test_verify_environment_raises_when_missing(self):
        with patch(
            "src.provisioning.requirements.check_dependencies",
            return_value=([], ["missing_pkg"]),
        ):
            with pytest.raises(RuntimeError, match="Missing runtime dependencies"):
                verify_environment_integrity()

    def test_required_dependencies_list_not_empty(self):
        assert len(REQUIRED_DEPENDENCIES) > 0

    def test_required_dependencies_contains_core_packages(self):
        """Sanity check: key runtime deps are in the list."""
        for pkg in ("pywhispercpp", "huggingface_hub", "numpy"):
            assert pkg in REQUIRED_DEPENDENCIES, f"Expected '{pkg}' in requirements"
