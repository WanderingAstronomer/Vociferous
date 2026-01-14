from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest
from PyQt6.QtCore import QObject

# Mock dependencies before importing modules that use them
with patch.dict(
    "sys.modules",
    {
        "ctranslate2": MagicMock(),
        "tokenizers": MagicMock(),
        "huggingface_hub": MagicMock(),
    },
):
    from services.slm_service import SLMService, SLMState


class TestRefinementBackend:
    @pytest.fixture
    def slm_service(self):
        service = SLMService()
        return service

    @patch("services.slm_service.get_model_cache_dir")
    def test_initialization_download(
        self, mock_get_cache, slm_service
    ):
        """Test that initialization triggers provisioning if files are missing."""
        mock_get_cache.return_value = Path("/tmp/cache")
        
        # Patch instance methods to avoid path resolution issues
        with patch.object(slm_service, '_provision_model') as mock_provision, \
             patch.object(slm_service, '_load_engine') as mock_load, \
             patch.object(slm_service, '_validate_artifacts', return_value=False):
             
             slm_service.initialize_service()

             # Should have called provisioning
             mock_provision.assert_called_once()
             # Should have called load
             mock_load.assert_called_once()

    @patch("services.slm_service.get_model_cache_dir")
    @patch("services.slm_service.snapshot_download")
    def test_initialization_cached(self, mock_download, mock_get_cache, slm_service):
        """Test initialization when files are already cached."""
        mock_get_cache.return_value = Path("/tmp/cache")

        with patch.object(slm_service, '_validate_artifacts', return_value=True), \
             patch.object(slm_service, '_load_engine') as mock_load:
            
            slm_service.initialize_service()

            # Should NOT call snapshot_download (part of provision)
            mock_download.assert_not_called()
            # Should call load
            mock_load.assert_called_once()

    def test_refinement_request_not_ready(self, slm_service):
        """Test refinement request when service is not ready."""
        mock_error_signal = MagicMock()
        slm_service.refinementError.connect(mock_error_signal)
        
        slm_service._set_state(SLMState.DISABLED)
        slm_service.handle_refinement_request(1, "test")

        mock_error_signal.assert_called()

    @patch("services.slm_service.RefinementEngine")
    def test_refinement_success(self, mock_engine_cls, slm_service):
        """Test successful refinement."""
        mock_engine = mock_engine_cls.return_value
        mock_engine.refine.return_value = "Refined Text"
        
        # Inject private attribute since that's what the service uses
        slm_service._engine = mock_engine
        slm_service._set_state(SLMState.READY)

        mock_success_signal = MagicMock()
        slm_service.refinementSuccess.connect(mock_success_signal)

        slm_service.handle_refinement_request(1, "Raw Text")

        mock_engine.refine.assert_called()
        mock_success_signal.assert_called_with(1, "Refined Text")
