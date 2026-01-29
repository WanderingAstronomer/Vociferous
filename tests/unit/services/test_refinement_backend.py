import sys
import time
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest
from PyQt6.QtCore import QObject, QThread, pyqtSignal, Qt

# NOTE: We do NOT import SLMService at top level to avoid triggering
# real imports of huggingface_hub/ctranslate2 which might crash or segfault
# in the test environment if they are not properly mocked.


@pytest.fixture(scope="module", autouse=True)
def mock_heavy_dependencies():
    """
    Mock out heavy ML libraries globally for this test module
    BEFORE any service code is imported.
    """
    mock_modules = {
        "ctranslate2": MagicMock(),
        "tokenizers": MagicMock(),
        "huggingface_hub": MagicMock(),
    }

    # Force unload relevant modules if they exist to ensure they are re-imported with mocks
    to_unload = ["services.slm_service", "refinement.engine"]
    for mod in to_unload:
        if mod in sys.modules:
            del sys.modules[mod]

    with patch.dict("sys.modules", mock_modules):
        yield


@pytest.fixture
def slm_module():
    """Import the module safely after mocking."""
    import src.services.slm_service as mod

    return mod


@pytest.fixture
def slm_service(slm_module):
    service = slm_module.SLMService()
    return service


@pytest.fixture
def qapp():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestRefinementBackend:
    def test_refinement_concurrency_invariant(
        self, qapp, qtbot, slm_service, slm_module
    ):
        """
        Invariant: Refinement must be capable of running off the main thread.
        This test verifies SLMService functions correctly as a threaded worker.
        """
        # 1. Setup Worker Thread
        thread = QThread()
        slm_service.moveToThread(thread)
        thread.start()

        try:
            # 2. Setup Driver (Main Thread)
            class Driver(QObject):
                trigger = pyqtSignal(int, str, str, str)

            driver = Driver()
            driver.trigger.connect(
                slm_service.handle_refinement_request,
                type=Qt.ConnectionType.QueuedConnection,
            )

            # 3. Setup Mocks
            mock_engine = MagicMock()

            def slow_refine(text, profile=None, instructions=None):
                time.sleep(0.01)  # Small sleep
                res = MagicMock()
                res.content = f"Refined {text}"
                res.reasoning = None
                return res

            mock_engine.refine.side_effect = slow_refine

            # We access private _engine/_state for setup purposes
            with (
                patch.object(slm_service, "_engine", mock_engine),
                patch.object(slm_service, "_state", slm_module.SLMState.READY),
            ):
                # 4. Trigger
                with qtbot.waitSignal(
                    slm_service.refinementSuccess, timeout=2000
                ) as blocker:
                    driver.trigger.emit(100, "Input", "BALANCED", "")

                # 5. Assert
                assert blocker.args == [100, "Refined Input"]
                mock_engine.refine.assert_called_with("Input", "BALANCED", "")
        finally:
            # Cleanup
            thread.quit()
            thread.wait()

    def test_initialization_download(self, slm_service, slm_module):
        """Test that initialization triggers provisioning if files are missing."""
        # Use patch on the module's namespace for the helper function
        with (
            patch("src.services.slm_service.get_model_cache_dir") as mock_get_cache,
            patch.object(
                slm_service, "_start_background_provisioning"
            ) as mock_provision,
            patch.object(slm_service, "_load_engine"),
            patch("src.services.slm_service.validate_model_artifacts", return_value=False),
        ):
            mock_get_cache.return_value = Path("/tmp/cache")

            slm_service.initialize_service()

            mock_provision.assert_called_once()

    def test_initialization_fails_gracefully_without_dependencies(self, slm_module):
        """Test that initialization sets NOT_AVAILABLE when RefinementEngine is None (deps missing)."""
        # Temporarily set RefinementEngine to None to simulate missing dependencies
        original = slm_module.RefinementEngine
        slm_module.RefinementEngine = None

        try:
            service = slm_module.SLMService()

            # Mock statusMessage to capture emissions
            status_messages = []
            service.statusMessage.connect(lambda msg: status_messages.append(msg))

            service.initialize_service()

            assert service.state == slm_module.SLMState.NOT_AVAILABLE
            assert (
                "Refinement unavailable: dependencies not installed" in status_messages
            )
        finally:
            # Restore
            slm_module.RefinementEngine = original
