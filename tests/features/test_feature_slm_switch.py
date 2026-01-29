import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest


# Fixture to mock heavy ML dependencies
@pytest.fixture(scope="module", autouse=True)
def mock_heavy_dependencies():
    mock_modules = {
        "ctranslate2": MagicMock(),
        "tokenizers": MagicMock(),
        "huggingface_hub": MagicMock(),
        "awq": MagicMock(),
        "autoawq": MagicMock(),
    }

    # Unload if present
    to_unload = ["services.slm_service", "refinement.engine"]
    for mod in to_unload:
        if mod in sys.modules:
            del sys.modules[mod]

    with patch.dict("sys.modules", mock_modules):
        yield


@pytest.fixture
def slm_module():
    import src.services.slm_service as mod

    return mod


class TestSLMModelSwitching:
    """Test suite for the multi-model architecture."""

    def test_model_registry_integrity(self, slm_module):
        """Verify the model registry contains the expected definitions."""
        models = slm_module.MODELS

        # Invariant: Must support 3-tier model selection
        assert "qwen4b" in models
        assert "qwen8b" in models
        assert "qwen14b" in models

        # Verify 4B specs (Small/Fast)
        small = models["qwen4b"]
        assert small.quantization == "int8"
        assert small.required_vram_mb < 8000
        assert small.source == "HuggingFace"

        # Verify 8B VL specs (Medium/Thinking)
        medium = models["qwen8b"]
        assert medium.quantization == "int8"
        assert 8000 < medium.required_vram_mb < 11000
        assert medium.source == "HuggingFace"
        assert "8B" in medium.name

        # Verify 14B specs (Large/Pro)
        large = models["qwen14b"]
        assert large.quantization == "int8"
        assert 12000 < large.required_vram_mb < 16000
        assert large.source == "HuggingFace"

    def test_change_model_slot(self, slm_module):
        """Test the change_model slot behavior (Immediate vs Background)."""
        # Setup
        service = slm_module.SLMService()

        # Scenario A: Model Artifacts EXIST (Immediate Switch)
        with patch.object(service, "initialize_service") as mock_init:
            with patch("src.services.slm_service.validate_model_artifacts", return_value=True):
                # Action: Switch to 14B
                service.change_model("qwen14b")

                # Assert: Model changed immediately
                assert service.current_model.id == "qwen14b"
                mock_init.assert_called_once()

        # Reset
        service.current_model = slm_module.MODELS["qwen14b"]  # Reset manually if needed

        # Scenario B: Model Artifacts MISSING (Background Provisioning)
        with patch.object(service, "_start_background_provisioning") as mock_bg:
            with patch("src.services.slm_service.validate_model_artifacts", return_value=False):
                # Action: Switch to 4B
                service.change_model("qwen4b")

                # Assert: Model did NOT change immediately
                assert service.current_model.id == "qwen14b"  # Stays on old
                # Assert: Background task triggered
                mock_bg.assert_called_once()

    def test_initialization_picks_correct_model(self, slm_module):
        """Test that __init__ uses the configured model ID."""

        # Mock Config to return qwen14b
        # Must mock where it's used, not where it's defined
        with patch.object(
            slm_module.ConfigManager, "get_config_value", return_value="qwen4b"
        ):
            service = slm_module.SLMService()
            # Assert: Picked up 4B
            assert service.current_model.id == "qwen4b"
