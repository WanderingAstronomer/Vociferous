"""Local CTranslate2 refinement provider."""

from __future__ import annotations

import logging
from pathlib import Path

from src.core.cuda_runtime import CudaRuntimeStatus, detect_cuda_runtime
from src.core.model_registry import SLMModel, get_slm_model, get_smallest_slm_id
from src.core.resource_manager import ResourceManager
from src.core.settings import VociferousSettings
from src.refinement.engine import RefinementEngine
from src.refinement.output_parser import GenerationResult
from src.refinement.providers.runtime import describe_refinement_runtime

logger = logging.getLogger(__name__)


class LocalCT2RefinementProvider:
    """Local CTranslate2 refinement provider."""

    def __init__(self, settings: VociferousSettings) -> None:
        self._settings = settings
        self._engine: RefinementEngine | None = None
        self._runtime_summary: dict[str, object] | None = None
        self._last_usage: dict[str, int] | None = None

    @property
    def provider_id(self) -> str:
        return "local_ct2"

    def load(self) -> None:
        settings = self._settings
        model_id = settings.refinement.model_id
        cuda_status = detect_cuda_runtime()

        if not model_id:
            raise ValueError("No local refinement model configured.")

        slm_model = get_slm_model(model_id)
        if slm_model is None:
            raise ValueError(f"Unknown SLM model_id: {model_id}")

        slm_model, fallback_reason = self._resolve_model_for_runtime(slm_model, settings, cuda_status)
        runtime_summary = describe_refinement_runtime(
            settings,
            cuda_status=cuda_status,
            model_id=slm_model.id,
            requested_model_id=model_id,
            fallback_reason=fallback_reason,
        )

        cache_dir = ResourceManager.get_user_cache_dir("models")
        model_dir = self._model_dir(cache_dir, slm_model)
        if not (model_dir / slm_model.model_file).exists():
            if fallback_reason:
                raise FileNotFoundError(
                    f"CPU fallback model {slm_model.name} is not downloaded. "
                    "Download it in Settings before using refinement on this machine."
                )
            raise FileNotFoundError(
                f"CT2 model directory not found: {model_dir}. Please run provisioning to download the model."
            )

        if slm_model.quant == "awq" and runtime_summary["resolved_device"] != "cuda":
            raise ValueError(
                f"{slm_model.name} uses AWQ quantization which requires GPU. "
                "For CPU inference, switch to an int8 model (e.g. Qwen3 4B) in Settings -> Refinement."
            )

        logger.info(
            "Loading SLM from %s (model_id=%s, resolved_device=%s, gpu_layers=%s, cpu_threads=%s, "
            "compute_type=%s, use_thinking=%s)...",
            model_dir,
            runtime_summary["model_id"],
            runtime_summary["resolved_device"],
            runtime_summary["gpu_layers"],
            runtime_summary["cpu_threads"],
            runtime_summary["compute_type"],
            runtime_summary["use_thinking"],
        )
        self._engine = RefinementEngine(
            model_path=model_dir,
            system_prompt=settings.refinement.system_prompt,
            invariants=settings.refinement.invariants,
            n_gpu_layers=int(runtime_summary["gpu_layers"]),
            n_threads=settings.refinement.n_threads,
            compute_type=settings.model.compute_type,
        )
        self._runtime_summary = runtime_summary

    def unload(self) -> None:
        if self._engine is None:
            return
        logger.info("Unloading SLM engine...")
        try:
            self._engine.generator.unload_model()
        except Exception:
            logger.debug("CT2 Generator.unload_model() failed (non-fatal)")
        self._engine = None
        self._runtime_summary = None
        self._last_usage = None

    def get_runtime_summary(self) -> dict[str, object]:
        summary = dict(self._runtime_summary or describe_refinement_runtime(self._settings))
        if self._last_usage:
            summary["last_usage"] = dict(self._last_usage)
        return summary

    def refine(
        self,
        text: str,
        *,
        instructions: str = "",
        temperature: float,
        top_p: float,
        top_k: int,
        repetition_penalty: float,
        use_thinking: bool,
        allow_skip: bool = True,
    ) -> GenerationResult:
        if self._engine is None:
            raise RuntimeError("Engine not loaded.")
        result = self._engine.refine(
            text,
            user_instructions=instructions,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            repetition_penalty=repetition_penalty,
            use_thinking=use_thinking,
            allow_skip=allow_skip,
        )
        self._last_usage = {
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "total_tokens": result.total_tokens,
        }
        return result

    def generate_custom(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 150,
        temperature: float = 0.7,
        use_thinking: bool = False,
    ) -> GenerationResult:
        if self._engine is None:
            raise RuntimeError("Engine not loaded.")
        return self._engine.generate_custom(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            use_thinking=use_thinking,
        )

    @staticmethod
    def _model_dir(cache_dir: Path, model: SLMModel) -> Path:
        return cache_dir / model.repo.split("/")[-1]

    def _resolve_model_for_runtime(
        self,
        model: SLMModel,
        settings: VociferousSettings,
        cuda_status: CudaRuntimeStatus,
    ) -> tuple[SLMModel, str]:
        wants_gpu = settings.refinement.n_gpu_layers != 0
        if model.quant != "awq":
            return model, ""
        if settings.refinement.n_gpu_layers == 0:
            raise ValueError(
                f"{model.name} uses AWQ quantization which requires GPU. "
                "Choose an int8 refinement model for CPU mode."
            )
        if wants_gpu and cuda_status.cuda_available:
            return model, ""

        fallback = get_slm_model(get_smallest_slm_id())
        if fallback is None or fallback.quant == "awq":
            raise ValueError(f"{model.name} requires GPU, and no CPU-compatible refinement model is registered.")
        reason = f"{model.name} requires GPU, but CUDA is not usable; using {fallback.name} on CPU."
        logger.warning(reason)
        return fallback, reason


__all__ = ["LocalCT2RefinementProvider"]
