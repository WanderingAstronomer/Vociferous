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
    import src.services.slm_runtime as mod

    return mod


@pytest.fixture
def slm_service(slm_module):
    service = slm_module.SLMRuntime()
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
        This test verifies runtime emits refined text asynchronously.
        """
        # 2. Setup Driver (Main Thread)
        class Driver(QObject):
            trigger = pyqtSignal(str)

        driver = Driver()
        # Connect the driver to the runtime refine_text slot
        driver.trigger.connect(slm_service.refine_text)

        # 3. Setup Mocks
        mock_engine = MagicMock()

        def slow_refine(text):
            time.sleep(0.01)  # Small sleep
            return f"Refined {text}"

        mock_engine.refine.side_effect = slow_refine

        # We access private _engine/_state for setup purposes
        with (
            patch.object(slm_service, "_engine", mock_engine),
            patch.object(slm_service, "_state", slm_module.SLMState.READY),
        ):
            # 4. Trigger
            with qtbot.waitSignal(slm_service.signals.text_ready, timeout=2000) as blocker:
                driver.trigger.emit("Input")

            # 5. Assert
            assert blocker.args == ["Refined Input"]
            mock_engine.refine.assert_called_with("Input")

    def test_initialization_missing_artifacts_sets_error(self, slm_service):
        """When model artifacts are missing, enable() should result in an ERROR state."""
        # Make cache dir point to a path without model artifacts
        with patch("src.core.resource_manager.ResourceManager.get_user_cache_dir") as mock_cache:
            mock_cache.return_value = Path("/tmp/nonexistent_cache")

            # Call the load task synchronously for deterministic test behavior
            slm_service._load_model_task()

            from src.services.slm_types import SLMState

            assert slm_service.state == SLMState.ERROR
    def test_initialization_fails_gracefully_without_dependencies(self, slm_module):
        """When RefinementEngine is not present, enable() should set ERROR state."""
        original = slm_module.RefinementEngine
        slm_module.RefinementEngine = None

        try:
            service = slm_module.SLMRuntime()

            errors = []
            service.signals.error.connect(lambda e: errors.append(e))

            # Call load task synchronously for deterministic behavior
            service._load_model_task()

            assert service.state == slm_module.SLMState.ERROR
            assert errors
        finally:
            slm_module.RefinementEngine = original


