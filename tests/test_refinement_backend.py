import pytest
from unittest.mock import MagicMock, patch, ANY
from pathlib import Path
from PyQt6.QtCore import QObject

# Mock dependencies before importing modules that use them
with patch.dict("sys.modules", {
    "ctranslate2": MagicMock(),
    "tokenizers": MagicMock(),
    "huggingface_hub": MagicMock(),
}):
    from services.slm_service import SLMService, SLMState

class TestRefinementBackend:
    
    @pytest.fixture
    def slm_service(self):
        service = SLMService()
        return service

    @patch("services.slm_service.snapshot_download")
    @patch("services.slm_service.GECEngine")
    @patch("services.slm_service.get_model_cache_dir")
    def test_initialization_download(self, mock_get_cache, mock_engine, mock_download, slm_service):
        """Test that initialization triggers download if files are missing."""
        mock_get_cache.return_value = Path("/tmp/cache")
        # Mock download returning paths
        mock_download.side_effect = ["/tmp/cache/model", "/tmp/cache/tokenizer"]
        
        # Mock engine loading
        slm_service.initialize_service()
        
        assert slm_service.state == SLMState.READY
        assert mock_download.call_count == 4 # 2 probes (fail) + 2 downloads
        # actually, implementation: _get_snapshot_path calls snapshot_download with local_files_only=True
        
    @patch("services.slm_service.get_model_cache_dir")
    @patch("services.slm_service.snapshot_download")
    def test_initialization_cached(self, mock_download, mock_get_cache, slm_service):
        """Test initialization when files are already cached."""
        mock_get_cache.return_value = Path("/tmp/cache")
        
        # Mock probes returning valid paths
        mock_download.return_value = "/tmp/cache/snapshot"
        
        with patch("pathlib.Path.exists", return_value=True):
             slm_service.initialize_service()
             
        # Should be READY
        assert slm_service.state == SLMState.READY

    def test_refinement_request_not_ready(self, slm_service):
        """Test refinement request when service is not ready."""
        # Check Error Signal emission
        mock_error_signal = MagicMock()
        slm_service.refinementError.connect(mock_error_signal)
        
        slm_service.handle_refinement_request(1, "test")
        
        mock_error_signal.emit.assert_called()

    @patch("services.slm_service.GECEngine")
    def test_refinement_success(self, mock_engine_cls, slm_service):
        """Test successful refinement."""
        mock_engine = mock_engine_cls.return_value
        mock_engine.refine.return_value = "Refined Text"
        slm_service._engine = mock_engine
        slm_service._set_state(SLMState.READY)
        
        mock_success_signal = MagicMock()
        slm_service.refinementSuccess.connect(mock_success_signal)
        
        slm_service.handle_refinement_request(1, "Raw Text")
        
        mock_engine.refine.assert_called_with("Raw Text")
        mock_success_signal.emit.assert_called_with(1, "Refined Text")
