"""Refinement runtime descriptor + small shared key helpers."""

from __future__ import annotations

import os

from src.core.cuda_runtime import CudaRuntimeStatus, detect_cuda_runtime
from src.core.secret_store import get_provider_api_key, normalize_provider_api_key
from src.core.settings import VociferousSettings


def api_key_from_env(provider_id: str, env_name: str | None) -> str | None:
    if not env_name:
        return None
    value = os.environ.get(env_name)
    return normalize_provider_api_key(provider_id, value)


def describe_refinement_runtime(
    settings: VociferousSettings,
    *,
    cuda_status: CudaRuntimeStatus | None = None,
    model_id: str | None = None,
    requested_model_id: str | None = None,
    fallback_reason: str = "",
) -> dict[str, object]:
    """Return resolved refinement runtime choices for support diagnostics."""
    provider = settings.refinement.provider
    if provider != "local_ct2":
        provider_settings = getattr(settings.refinement, provider)
        resolved_model = model_id or provider_settings.model_id
        return {
            "enabled": settings.refinement.enabled,
            "provider": provider,
            "model_id": resolved_model,
            "requested_model_id": requested_model_id or provider_settings.model_id,
            "resolved_device": "external",
            "base_url": provider_settings.base_url,
            "timeout_seconds": provider_settings.timeout_seconds,
            "max_output_tokens": provider_settings.max_output_tokens,
            "api_key_env": provider_settings.api_key_env,
            "has_api_key": bool(
                provider_settings.api_key
                or get_provider_api_key(provider)
                or api_key_from_env(provider, provider_settings.api_key_env)
            ),
            "use_thinking": False,
            "fallback_reason": fallback_reason,
        }

    status = cuda_status or detect_cuda_runtime()
    requested = requested_model_id or settings.refinement.model_id
    resolved_model = model_id or requested
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
        "provider": "local_ct2",
        "model_id": resolved_model,
        "requested_model_id": requested,
        "resolved_device": resolved_device,
        "gpu_layers": 0 if resolved_device == "cpu-fallback" else settings.refinement.n_gpu_layers,
        "requested_gpu_layers": settings.refinement.n_gpu_layers,
        "cpu_threads": settings.refinement.n_threads,
        "compute_type": settings.model.compute_type,
        "use_thinking": settings.refinement.use_thinking,
        "cuda_detail": status.detail,
        "fallback_reason": fallback_reason,
    }


__all__ = ["api_key_from_env", "describe_refinement_runtime"]
