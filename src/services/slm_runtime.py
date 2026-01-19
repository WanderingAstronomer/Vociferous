"""
SLM Runtime - Lightweight Inference Service.

This module replaces the old monolithic SLMService.
It is responsible strictly for:
1. Loading an *already provisioned* model from disk.
2. Running inference via RefinementEngine.
3. Managing lifecycle (Enable/Disable/Unload).

It DOES NOT:
1. Download models.
2. Install pip dependencies.
3. Convert models.
"""

import enum
import logging
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import (
    QMutex,
    QObject,
    QThreadPool,
    QWaitCondition,
    pyqtSignal,
    pyqtSlot,
)

from src.core.config_manager import ConfigManager
from src.core.resource_manager import ResourceManager

try:
    from src.refinement.engine import RefinementEngine
except ImportError:
    RefinementEngine = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class SupportedModel:
    id: str
    name: str
    dir_name: str
    required_vram_mb: int


class SLMState(enum.Enum):
    DISABLED = "Disabled"
    LOADING = "Loading Model"
    READY = "Ready"
    INFERRING = "Refining..."
    ERROR = "Error"


class SLMSignals(QObject):
    state_changed = pyqtSignal(SLMState)
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    text_ready = pyqtSignal(str)


class SLMRuntime(QObject):
    """
    Runtime service for Small Language Model refinement.
    Assumes models are already provisioned in the cache.
    """

    def __init__(self):
        super().__init__()
        self.signals = SLMSignals()
        self._state = SLMState.DISABLED
        self._engine: Optional[RefinementEngine] = None
        self._mutex = QMutex()
        self._wait_condition = QWaitCondition()
        self._thread_pool = QThreadPool.globalInstance()

    @property
    def state(self) -> SLMState:
        return self._state

    @state.setter
    def state(self, new_state: SLMState):
        if self._state != new_state:
            self._state = new_state
            self.signals.state_changed.emit(new_state)

    @pyqtSlot()
    def enable(self):
        """Enable the SLM runtime. Starts async loading."""
        if self.state not in (SLMState.DISABLED, SLMState.ERROR):
            return

        self.state = SLMState.LOADING
        self._thread_pool.start(self._load_model_task)

    @pyqtSlot()
    def disable(self):
        """Unload the model and disable runtime."""
        self._unload_model()
        self.state = SLMState.DISABLED

    def _load_model_task(self):
        """Background task to load the model."""
        try:
            # 1. Resolve Model Path from manifest
            model_id = ConfigManager.get_value("slm_model", "qwen4b")
            cache_dir = ResourceManager.get_user_cache_dir("models")

            # Map model_id to directory name via manifest lookup
            # This allows the provisioner to control directory structure
            model_dir_map = {
                "qwen4b": "qwen3-4b-ct2",
                "qwen8b": "qwen3-8b-ct2",
                "qwen14b": "qwen3-14b-ct2",
            }

            model_dir_name = model_dir_map.get(model_id)
            if not model_dir_name:
                raise ValueError(f"Unknown model_id: {model_id}")

            model_path = cache_dir / model_dir_name
            manifest_path = model_path / "manifest.json"

            # 2. Validation
            if not model_path.exists():
                raise FileNotFoundError(
                    f"Model directory not found: {model_path}.\n"
                    "Please run the setup utility to provision the model."
                )

            if not manifest_path.exists():
                raise FileNotFoundError(
                    f"Manifest not found: {manifest_path}.\n"
                    "Model directory may be incomplete or corrupted."
                )

            # 3. Load Engine
            if not RefinementEngine:
                raise ImportError(
                    "RefinementEngine module missing (ctranslate2/transformers)."
                )

            logger.info(f"Loading SLM from {model_path}...")
            self._engine = RefinementEngine(str(model_path))

            self.state = SLMState.READY

        except Exception as e:
            logger.error(f"Failed to load SLM: {e}")
            self.signals.error.emit(str(e))
            self.state = SLMState.ERROR

    def _unload_model(self):
        """Force unload of the engine to free VRAM."""
        if self._engine:
            logger.info("Unloading SLM engine...")
            del self._engine
            self._engine = None
            import gc

            gc.collect()

    @pyqtSlot(str)
    def refine_text(self, text: str):
        """Submit text for refinement."""
        if self.state != SLMState.READY:
            logger.warning("Refinement requested but SLM not ready.")
            return

        self.state = SLMState.INFERRING
        # Run inference in background
        self._thread_pool.start(lambda: self._inference_task(text))

    def _inference_task(self, text: str):
        try:
            if not self._engine:
                raise RuntimeError("Engine disappeared during inference.")

            refined = self._engine.refine(text)
            self.signals.text_ready.emit(refined)
            self.state = SLMState.READY
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            self.signals.error.emit(f"Inference failed: {e}")
            self.state = SLMState.READY  # Return to ready state even on error?
