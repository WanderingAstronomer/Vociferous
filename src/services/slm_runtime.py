"""
SLM Runtime - Lightweight Inference Service.

Manages the lifecycle of a CTranslate2 Generator-based refinement model:
1. Loading an already provisioned CT2 model from disk.
2. Running inference via RefinementEngine (ctranslate2 + tokenizers).
3. Managing lifecycle (Enable/Disable/Unload).
"""

import logging
import threading
import time
from typing import Callable, Optional

from src.core.cuda_runtime import CudaRuntimeStatus, detect_cuda_runtime
from src.core.model_registry import get_slm_model
from src.core.resource_manager import ResourceManager
from src.core.settings import VociferousSettings, update_settings
from src.services.slm_types import SLMState

try:
    from src.refinement.engine import RefinementEngine
except ImportError:
    RefinementEngine = None  # type: ignore

logger = logging.getLogger(__name__)


def describe_slm_runtime(
    settings: VociferousSettings,
    *,
    cuda_status: CudaRuntimeStatus | None = None,
) -> dict[str, object]:
    """Return the resolved SLM runtime choices for support diagnostics."""
    status = cuda_status or detect_cuda_runtime()
    wants_gpu = settings.refinement.n_gpu_layers != 0

    if not settings.refinement.enabled or not settings.refinement.model_id:
        resolved_device = "disabled"
    elif wants_gpu and status.cuda_available:
        resolved_device = "cuda"
    elif wants_gpu and not status.cuda_available:
        resolved_device = "cpu-fallback"
    else:
        resolved_device = "cpu"

    return {
        "enabled": settings.refinement.enabled,
        "model_id": settings.refinement.model_id,
        "resolved_device": resolved_device,
        "gpu_layers": settings.refinement.n_gpu_layers,
        "cpu_threads": settings.refinement.n_threads,
        "compute_type": settings.model.compute_type,
        "use_thinking": settings.refinement.use_thinking,
        "cuda_detail": status.detail,
    }


class SLMRuntime:
    """
    Runtime service for Small Language Model refinement.
    Assumes CT2 model directories are already provisioned in the cache.
    """

    _SLOW_INFERENCE_SECONDS = 15.0

    def __init__(
        self,
        settings_provider: Callable[[], VociferousSettings],
        settings_updater: Callable[..., VociferousSettings] = update_settings,
        on_state_changed: Optional[Callable[[SLMState], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_text_ready: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._settings_provider = settings_provider
        self._settings_updater = settings_updater
        self._state = SLMState.DISABLED
        self._engine: Optional[RefinementEngine] = None
        self._lock = threading.Lock()
        self._runtime_summary: dict[str, object] | None = None

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

    def shutdown(self) -> None:
        """Mark disabled WITHOUT touching the native engine object.

        During process shutdown, CUDA driver teardown races with Python's
        garbage collector.  If we set ``self._engine = None`` here, Python
        calls the CTranslate2 destructor synchronously, which tries to free
        CUDA memory on a half-torn-down driver → ``abort()``.  Instead, just
        mark state as DISABLED and let the OS reclaim everything on exit.
        """
        self.state = SLMState.DISABLED

    def _load_model_task(self) -> None:
        """Background task to load the CT2 Generator model."""
        try:
            s = self._settings_provider()
            model_id = s.refinement.model_id
            runtime_summary = describe_slm_runtime(s)

            if not model_id:
                logger.info("No SLM model configured. SLM service disabled.")
                self.state = SLMState.DISABLED
                return

            slm_model = get_slm_model(model_id)
            if slm_model is None:
                raise ValueError(f"Unknown SLM model_id: {model_id}")

            cache_dir = ResourceManager.get_user_cache_dir("models")
            # CT2 models are directories named after the repo slug
            local_dir_name = slm_model.repo.split("/")[-1]
            model_dir = cache_dir / local_dir_name

            if not (model_dir / slm_model.model_file).exists():
                raise FileNotFoundError(
                    f"CT2 model directory not found: {model_dir}. Please run provisioning to download the model."
                )

            if not RefinementEngine:
                raise ImportError("RefinementEngine not available (ctranslate2 missing).")

            # AWQ dequantization requires float16 GPU kernels — CPU can't do it.
            if slm_model.quant == "awq":
                will_use_cpu = s.refinement.n_gpu_layers == 0
                if not will_use_cpu:
                    try:
                        import ctranslate2

                        will_use_cpu = ctranslate2.get_cuda_device_count() == 0
                    except Exception:
                        will_use_cpu = True
                if will_use_cpu:
                    raise ValueError(
                        f"{slm_model.name} uses AWQ quantization which requires GPU. "
                        f"For CPU inference, switch to an int8 model (e.g. Qwen3 4B) "
                        f"in Settings \u2192 Refinement."
                    )

            logger.info(
                "Loading SLM from %s (model_id=%s, resolved_device=%s, gpu_layers=%s, cpu_threads=%s, compute_type=%s, use_thinking=%s)...",
                model_dir,
                runtime_summary["model_id"],
                runtime_summary["resolved_device"],
                runtime_summary["gpu_layers"],
                runtime_summary["cpu_threads"],
                runtime_summary["compute_type"],
                runtime_summary["use_thinking"],
            )
            start = time.perf_counter()

            self._engine = RefinementEngine(
                model_path=model_dir,
                system_prompt=s.refinement.system_prompt,
                invariants=s.refinement.invariants,
                n_gpu_layers=s.refinement.n_gpu_layers,
                n_threads=s.refinement.n_threads,
                compute_type=s.model.compute_type,
            )

            self._runtime_summary = runtime_summary
            logger.info(
                "SLM loaded in %.2fs (model_id=%s, resolved_device=%s)",
                time.perf_counter() - start,
                runtime_summary["model_id"],
                runtime_summary["resolved_device"],
            )

            self.state = SLMState.READY

        except Exception as e:
            logger.error("Failed to load SLM: %s", e)
            if self._on_error:
                self._on_error(str(e))
            self.state = SLMState.ERROR

    def _unload_model(self) -> None:
        """Release the engine reference to free VRAM.

        CTranslate2's native destructor can call abort() when freeing CUDA
        memory — both during process shutdown AND mid-process restarts.
        Use ``Generator.unload_model()`` to explicitly release VRAM first,
        making the subsequent destructor a safe no-op.
        """
        with self._lock:
            if self._engine is not None:
                logger.info("Unloading SLM engine...")
                try:
                    self._engine.generator.unload_model()
                except Exception:
                    logger.debug("CT2 Generator.unload_model() failed (non-fatal)")
                self._engine = None
                self._runtime_summary = None

    def _log_inference_timing(self, operation: str, input_text: str, output_text: str, elapsed: float) -> None:
        """Emit support-useful timing context without logging user text."""
        runtime = self._runtime_summary or describe_slm_runtime(self._settings_provider())
        input_words = len(input_text.split())
        output_words = len(output_text.split()) if output_text else 0

        logger.info(
            "SLM %s completed in %.2fs (input_chars=%d, input_words=%d, output_chars=%d, output_words=%d, model=%s, resolved_device=%s, gpu_layers=%s, cpu_threads=%s, use_thinking=%s)",
            operation,
            elapsed,
            len(input_text),
            input_words,
            len(output_text),
            output_words,
            runtime.get("model_id"),
            runtime.get("resolved_device"),
            runtime.get("gpu_layers"),
            runtime.get("cpu_threads"),
            runtime.get("use_thinking"),
        )
        if elapsed >= self._SLOW_INFERENCE_SECONDS:
            logger.warning(
                "Slow SLM %s detected (elapsed=%.2fs, input_words=%d, output_words=%d, model=%s, resolved_device=%s, gpu_layers=%s, cpu_threads=%s)",
                operation,
                elapsed,
                input_words,
                output_words,
                runtime.get("model_id"),
                runtime.get("resolved_device"),
                runtime.get("gpu_layers"),
                runtime.get("cpu_threads"),
            )

    def _sampling_params_for_level(self, level: int) -> dict[str, float | int | bool]:
        """Return sampling profile for grammar-edit refinement.

        Thinking mode is DISABLED.  Empirical testing showed that Qwen3 models
        (4B/8B/14B Q4_K_M) produce equal-or-better grammar edits without
        thinking, in less time.  The <think> overhead burned tokens on reasoning
        that added no value for mechanical text correction.

        `level` is intentionally ignored — single-purpose grammar pipeline.
        """
        _ = level
        r = self._settings_provider().refinement
        return {
            "temperature": r.temperature,
            "top_p": r.top_p,
            "top_k": r.top_k,
            "repetition_penalty": r.repetition_penalty,
            "use_thinking": r.use_thinking,
        }

    def refine_text(self, text: str, level: int = 1, instructions: str = "") -> None:
        """Submit text for refinement (runs in background thread)."""
        if self.state != SLMState.READY:
            logger.warning("Refinement requested but SLM not ready.")
            return

        self.state = SLMState.INFERRING
        t = threading.Thread(
            target=self._inference_task,
            args=(text, level, instructions),
            daemon=True,
        )
        t.start()

    def refine_text_sync(self, text: str, level: int = 1, instructions: str = "", allow_skip: bool = True) -> str:
        """Synchronous refinement — blocks until complete. Returns refined text."""
        if not self._engine:
            raise RuntimeError("Engine not loaded.")

        previous_state = self.state

        # Mark busy before lock acquisition so low-priority background jobs
        # do not race and starve user-triggered refinement.
        self.state = SLMState.INFERRING

        acquired = self._lock.acquire(timeout=self._REFINE_LOCK_TIMEOUT)
        if not acquired:
            self.state = previous_state
            raise TimeoutError(f"Timed out waiting for SLM lock after {self._REFINE_LOCK_TIMEOUT:.0f}s")

        try:
            if not self._engine:
                raise RuntimeError("Engine not loaded.")
            params = self._sampling_params_for_level(level)
            start = time.perf_counter()
            result = self._engine.refine(
                text,
                user_instructions=instructions,
                temperature=float(params["temperature"]),
                top_p=float(params["top_p"]),
                top_k=int(params["top_k"]),
                repetition_penalty=float(params["repetition_penalty"]),
                use_thinking=bool(params["use_thinking"]),
                allow_skip=allow_skip,
            )
            self._log_inference_timing("refinement", text, result.content, time.perf_counter() - start)
        finally:
            self._lock.release()
            self.state = previous_state
        return result.content

    # Maximum seconds to wait for the inference lock before giving up.
    # Prevents low-priority tasks (title gen) from blocking behind long
    # thinking-mode refinements.
    _CUSTOM_LOCK_TIMEOUT = 5.0
    # Maximum seconds refinement will wait for the shared SLM lock.
    _REFINE_LOCK_TIMEOUT = 60.0

    def generate_custom_sync(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 150,
        temperature: float = 0.7,
        use_thinking: bool = False,
    ) -> str:
        """Synchronous freeform generation — blocks until complete. Returns generated text.

        Uses a short lock timeout so callers (title gen, insight gen) don't
        block for minutes behind a long thinking-mode refinement.
        """
        acquired = self._lock.acquire(timeout=self._CUSTOM_LOCK_TIMEOUT)
        if not acquired:
            logger.warning(
                "generate_custom_sync: could not acquire lock within %.1fs (SLM busy with refinement)",
                self._CUSTOM_LOCK_TIMEOUT,
            )
            return ""
        try:
            if not self._engine:
                raise RuntimeError("Engine not loaded.")
            start = time.perf_counter()
            result = self._engine.generate_custom(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                use_thinking=use_thinking,
            )
            self._log_inference_timing("custom-generation", user_prompt, result.content, time.perf_counter() - start)
        finally:
            self._lock.release()
        return result.content

    def _inference_task(self, text: str, level: int, instructions: str = "") -> None:
        try:
            with self._lock:
                if not self._engine:
                    raise RuntimeError("Engine disappeared during inference.")
                params = self._sampling_params_for_level(level)
                start = time.perf_counter()
                result = self._engine.refine(
                    text,
                    user_instructions=instructions,
                    temperature=float(params["temperature"]),
                    top_p=float(params["top_p"]),
                    top_k=int(params["top_k"]),
                    repetition_penalty=float(params["repetition_penalty"]),
                    use_thinking=bool(params["use_thinking"]),
                )
                self._log_inference_timing("refinement", text, result.content, time.perf_counter() - start)

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
            self._settings_updater(refinement={"model_id": model_id})
        except Exception:
            logger.exception("Failed to persist new model id to config")

        self.disable()

        s = self._settings_provider()
        if s.refinement.enabled:
            self.enable()
