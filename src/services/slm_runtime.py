"""
SLM Runtime - Lightweight Inference Service.

Manages the lifecycle of a GGUF-based refinement model:
1. Loading an already provisioned GGUF model from disk.
2. Running inference via RefinementEngine (llama-cpp-python).
3. Managing lifecycle (Enable/Disable/Unload).
"""

import gc
import logging
import threading
from typing import Callable, Optional

from src.core.model_registry import get_slm_model
from src.core.resource_manager import ResourceManager
from src.core.settings import get_settings, update_settings
from src.services.slm_types import SLMState

try:
    from src.refinement.engine import RefinementEngine
except ImportError:
    RefinementEngine = None  # type: ignore

logger = logging.getLogger(__name__)


class SLMRuntime:
    """
    Runtime service for Small Language Model refinement.
    Assumes GGUF models are already provisioned in the cache.
    """

    def __init__(
        self,
        on_state_changed: Optional[Callable[[SLMState], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_text_ready: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._state = SLMState.DISABLED
        self._engine: Optional[RefinementEngine] = None
        self._lock = threading.Lock()

        # Callbacks (replace PyQt signals)
        self._on_state_changed = on_state_changed
        self._on_error = on_error
        self._on_text_ready = on_text_ready

    @property
    def state(self) -> SLMState:
        return self._state

    @state.setter
    def state(self, new_state: SLMState) -> None:
        if self._state != new_state:
            self._state = new_state
            if self._on_state_changed:
                self._on_state_changed(new_state)

    def enable(self) -> None:
        """Enable the SLM runtime. Starts async model loading."""
        if self.state not in (SLMState.DISABLED, SLMState.ERROR):
            return

        self.state = SLMState.LOADING
        t = threading.Thread(target=self._load_model_task, daemon=True)
        t.start()

    def disable(self) -> None:
        """Unload the model and disable runtime."""
        self._unload_model()
        self.state = SLMState.DISABLED

    def _load_model_task(self) -> None:
        """Background task to load the GGUF model."""
        try:
            s = get_settings()
            model_id = s.refinement.model_id

            if not model_id:
                logger.info("No SLM model configured. SLM service disabled.")
                self.state = SLMState.DISABLED
                return

            slm_model = get_slm_model(model_id)
            if slm_model is None:
                raise ValueError(f"Unknown SLM model_id: {model_id}")

            cache_dir = ResourceManager.get_user_cache_dir("models")
            model_path = cache_dir / slm_model.filename

            if not model_path.exists():
                raise FileNotFoundError(
                    f"GGUF model file not found: {model_path}. "
                    "Please run provisioning to download the model."
                )

            if not RefinementEngine:
                raise ImportError(
                    "RefinementEngine not available (llama-cpp-python missing)."
                )

            logger.info("Loading SLM from %s...", model_path)

            # Build level data from settings
            levels = {}
            for idx, level in s.refinement.levels.items():
                levels[idx] = {
                    "name": level.name,
                    "role": level.role,
                    "permitted": level.permitted,
                    "prohibited": level.prohibited,
                    "directive": level.directive,
                }

            self._engine = RefinementEngine(
                model_path=model_path,
                system_prompt=s.refinement.system_prompt,
                invariants=s.refinement.invariants,
                levels=levels,
                n_gpu_layers=s.refinement.n_gpu_layers,
                n_ctx=s.refinement.n_ctx,
            )

            self.state = SLMState.READY

        except Exception as e:
            logger.error("Failed to load SLM: %s", e)
            if self._on_error:
                self._on_error(str(e))
            self.state = SLMState.ERROR

    def _unload_model(self) -> None:
        """Force unload of the engine to free VRAM."""
        with self._lock:
            if self._engine:
                logger.info("Unloading SLM engine...")
                del self._engine
                self._engine = None
                gc.collect()

    def refine_text(self, text: str, level: int = 1) -> None:
        """Submit text for refinement (runs in background thread)."""
        if self.state != SLMState.READY:
            logger.warning("Refinement requested but SLM not ready.")
            return

        self.state = SLMState.INFERRING
        t = threading.Thread(
            target=self._inference_task, args=(text, level), daemon=True
        )
        t.start()

    def refine_text_sync(self, text: str, level: int = 1) -> str:
        """Synchronous refinement — blocks until complete. Returns refined text."""
        with self._lock:
            if not self._engine:
                raise RuntimeError("Engine not loaded.")
            result = self._engine.refine(text, profile=level)
        return result.content

    def _inference_task(self, text: str, level: int) -> None:
        try:
            with self._lock:
                if not self._engine:
                    raise RuntimeError("Engine disappeared during inference.")
                result = self._engine.refine(text, profile=level)

            if self._on_text_ready:
                self._on_text_ready(result.content)

            self.state = SLMState.READY
        except Exception as e:
            logger.error("Inference failed: %s", e)
            if self._on_error:
                self._on_error(f"Inference failed: {e}")
            self.state = SLMState.READY

    def change_model(self, model_id: str) -> None:
        """Change active model and reload runtime."""
        try:
            update_settings(refinement={"model_id": model_id})
        except Exception:
            logger.exception("Failed to persist new model id to config")

        self.disable()

        s = get_settings()
        if s.refinement.enabled:
            self.enable()
