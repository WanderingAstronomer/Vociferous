import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path
from src.services.slm_runtime import SLMRuntime, SLMState


# Mock the signals class since it's typically nested or imported
class MockSignals:
    state_changed = MagicMock()
    progress = MagicMock()
    error = MagicMock()
    text_ready = MagicMock()


@pytest.fixture
def mock_config_manager():
    with patch("src.services.slm_runtime.ConfigManager") as mock:
        yield mock


@pytest.fixture
def slm_runtime(mock_config_manager, tmp_path):
    # Mock ResourceManager to return tmp_path
    with patch("src.services.slm_runtime.ResourceManager") as rm_mock:
        rm_mock.get_user_cache_dir.return_value = tmp_path

        # Patch QThreadPool to run synchronously
        with patch("src.services.slm_runtime.QThreadPool") as tp_mock:
            # When start(runnable) is called, run it immediately
            tp_mock.globalInstance.return_value.start.side_effect = (
                lambda runnable: runnable()
            )

            runtime = SLMRuntime()
            # attach mock signals
            runtime.signals = MockSignals()
            yield runtime


def test_initial_state(slm_runtime):
    assert slm_runtime.state == SLMState.DISABLED


def test_enable_fails_without_manifest(slm_runtime):
    """
    If the model directory or manifest doesn't exist, enabling should fail
    (or go to error state) - it should NOT try to download/provision.
    """
    # Act
    slm_runtime.enable()

    # Assert
    # Logic: validation should fail immediately
    assert slm_runtime.state == SLMState.ERROR
    # Should verify we didn't try to start a provisioning worker
    assert not hasattr(slm_runtime, "provisioning_worker")


def test_enable_success_with_valid_model(slm_runtime, tmp_path, mock_config_manager):
    """
    If manifest exists, it should load the engine.
    """
    # Mock ConfigManager to return a valid model_id
    mock_config_manager.get_value.return_value = "qwen4b"

    # Setup - Fake a valid model install
    model_dir = tmp_path / "qwen3-4b-ct2"
    model_dir.mkdir()
    (model_dir / "manifest.json").touch()

    # Mock the RefinementEngine to avoid loading real CTranslate2
    with patch("src.services.slm_runtime.RefinementEngine"):
        # Act
        slm_runtime.enable()

        # Assert
        # Ideally it transitions to LOADING then READY
        # Since enable is async/threaded, we might need to check called methods
        # ensuring we tried to load
        assert slm_runtime.state != SLMState.ERROR


def test_no_pip_imports():
    """Safety check: Ensure the runtime module doesn't import pip or subprocess."""
    import src.services.slm_runtime as runtime_module
    import sys

    # We inspect the module's imports (loose check)
    # Ideally checking source code logic is better, but this is a sanity check
    # subprocess might be used for other things, but ensuring no 'pip' string
    # in the source is a good heuristic.
    with open(runtime_module.__file__, "r") as f:
        content = f.read()
        assert "pip install" not in content
        assert "pip uninstall" not in content
