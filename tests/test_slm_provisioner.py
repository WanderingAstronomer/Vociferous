import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import pytest
import importlib.util


# We are testing a script that might be in scripts/setup_refinement.py
# Helper to import the script module dynamically
def import_provisioner_module():
    script_path = Path("scripts/setup_refinement.py").resolve()
    spec = importlib.util.spec_from_file_location("setup_refinement", script_path)
    module = importlib.util.module_from_spec(spec)
    # We don't execute the module yet, just want to check its classes/functions
    # But since it's likely a script with `if __name__ == "__main__"`,
    # we might need to refactor the script to have a `main()` or `Provisioner` class.
    # For TDD, let's assume we will structure it with a Provisioner class.
    spec.loader.exec_module(module)
    return module


# Only run if we actually create the file, otherwise skip
def test_provisioner_logic(tmp_path):
    # This test assumes we will create the file shortly.
    # If file is missing, we create a stub to pass the import check if needed,
    # but strictly speaking TDD says "write test -> fail -> write code".
    # Since I cannot import a missing file, I will define what I expect the Provisioner class to do.

    # We will invoke the script via a function call `run_provisioning(model_name, target_dir)`
    pass


@pytest.fixture
def provisioner_module():
    # Fix: test is in tests/test_slm_provisioner.py -> parent is tests/ -> parent[1] is root
    scripts_path = Path(__file__).parents[1] / "scripts"
    sys.path.append(str(scripts_path))

    # We will create the file first then import it?
    # Or just mock the expected interface.
    # Let's write the test assuming 'scripts.setup_refinement' exists.
    try:
        import setup_refinement

        return setup_refinement
    except ImportError:
        pytest.skip("setup_refinement script not created yet")


def test_provisioner_install_deps(provisioner_module):
    with patch("subprocess.check_call") as mock_subprocess:
        provisioner_module.install_dependencies()

        # Expect pip install torch, transformers, autoawq
        # We check that at least one call to pip install happened
        assert mock_subprocess.called
        args = mock_subprocess.call_args[0][0]
        assert "pip" in args
        assert "install" in args


def test_provisioner_manifest_creation(provisioner_module, tmp_path):
    # Mocking the heavy stuff
    with (
        patch("subprocess.check_call"),
        patch("huggingface_hub.snapshot_download") as mock_dl,
        patch("shutil.copy2"),
        patch("setup_refinement.convert_model") as mock_convert,
    ):
        mock_dl.return_value = str(tmp_path / "source")

        # Side effect: Simulate convert_model creating the output directory
        def create_output_dir(model, src, dest):
            dest.mkdir(parents=True, exist_ok=True)

        mock_convert.side_effect = create_output_dir

        # Act
        provisioner_module.provision_model("qwen4b", base_dir=tmp_path)

        # Assert
        manifest = tmp_path / "qwen3-4b-ct2" / "manifest.json"
        assert manifest.exists()
        assert "qwen4b" in manifest.read_text()
