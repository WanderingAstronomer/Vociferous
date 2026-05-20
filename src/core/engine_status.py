"""Engine readiness, lifecycle, and support-status helpers."""

from __future__ import annotations

import importlib.metadata
import platform
import shutil
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Literal

from src.core.cuda_runtime import CudaRuntimeStatus, detect_cuda_runtime
from src.core.model_registry import ASRModel, SLMModel, get_asr_model, get_model_catalog, get_slm_model
from src.core.resource_manager import ResourceManager
from src.core.settings import VociferousSettings

EngineState = Literal[
    "disabled",
    "missing_model",
    "loading",
    "ready",
    "recording",
    "transcribing",
    "refining",
    "degraded_cpu",
    "error",
    "unknown",
]

DownloadState = Literal["started", "downloading", "complete", "error", "stalled"]

_DOWNLOAD_STALL_SECONDS = 180.0
_DOWNLOAD_LOCK = threading.Lock()
_DOWNLOADS: dict[str, "TrackedDownload"] = {}


@dataclass(slots=True)
class EngineComponentStatus:
    name: str
    state: EngineState
    ready: bool
    model_id: str | None = None
    model_name: str | None = None
    selected: bool = False
    downloaded: bool = False
    device: str | None = None
    detail: str = ""
    error: str | None = None
    runtime: dict[str, Any] | None = None


@dataclass(slots=True)
class TrackedDownload:
    model_type: str
    model_id: str
    status: DownloadState
    message: str
    started_at: float
    updated_at: float
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        age = max(0.0, time.monotonic() - self.started_at)
        idle = max(0.0, time.monotonic() - self.updated_at)
        result["age_seconds"] = round(age, 1)
        result["idle_seconds"] = round(idle, 1)
        return result


def track_download(model_type: str, model_id: str, status: DownloadState, message: str, error: str | None = None) -> None:
    """Record model provisioning status for support UI and health checks."""
    now = time.monotonic()
    key = f"{model_type}:{model_id}"
    with _DOWNLOAD_LOCK:
        existing = _DOWNLOADS.get(key)
        _DOWNLOADS[key] = TrackedDownload(
            model_type=model_type,
            model_id=model_id,
            status=status,
            message=message,
            started_at=existing.started_at if existing else now,
            updated_at=now,
            error=error,
        )


def get_tracked_downloads() -> list[dict[str, Any]]:
    """Return current model provisioning state and mark idle active downloads as stalled."""
    now = time.monotonic()
    with _DOWNLOAD_LOCK:
        for tracked in _DOWNLOADS.values():
            if tracked.status in {"started", "downloading"} and now - tracked.updated_at >= _DOWNLOAD_STALL_SECONDS:
                tracked.status = "stalled"
                tracked.message = "Download has not reported progress recently. Check network access and logs."
                tracked.error = tracked.message
                tracked.updated_at = now
        return [tracked.as_dict() for tracked in sorted(_DOWNLOADS.values(), key=lambda d: d.started_at, reverse=True)]


def normalize_engine_error(error: BaseException | str, *, model_name: str | None = None) -> str:
    """Translate common runtime failures into useful user-facing messages."""
    raw = str(error)
    text = raw.lower()
    model_label = model_name or "selected model"

    if "cublas64_12.dll" in text or "cudnn64_9.dll" in text or "cudart64_12.dll" in text:
        return "CUDA runtime DLLs are missing or unloadable. Install the pinned Windows CUDA runtime packages, then restart the engine."
    if "libcublas.so.12" in text or "libcudnn.so.9" in text or "libcudart.so.12" in text:
        return "CUDA runtime libraries are missing or unloadable. Install the CUDA 12 runtime plus cuDNN 9, then restart the engine."
    if "gpu inference requested" in text and "cuda" in text:
        return "GPU inference is selected, but CUDA is not usable. Fix CUDA or switch the engine device to CPU."
    if "out of memory" in text or "oom" in text or ("cuda error" in text and "memory" in text):
        return f"Not enough GPU memory to load {model_label}. Free VRAM, choose a smaller model, or use CPU mode."
    if "awq" in text and "requires gpu" in text:
        return f"{model_label} uses AWQ quantization and requires GPU inference. Choose an int8 refinement model for CPU mode."
    if "model directory not found" in text or "ct2 model directory not found" in text or "run provisioning" in text:
        return f"{model_label} is not downloaded. Download it in Settings before using this engine."
    if "repository not found" in text or "404" in text:
        return f"Model repository for {model_label} was not found. Check the model registry entry."
    if "401" in text or "unauthorized" in text or "gated" in text:
        return f"Model download for {model_label} requires access credentials. Check Hugging Face access."
    if "ctranslate2" in text and ("load" in text or "unsupported" in text or "invalid" in text):
        return f"CTranslate2 could not load {model_label}. The model files or runtime build are incompatible."
    if "webview2" in text:
        return "Microsoft Edge WebView2 Runtime is missing. Install WebView2 Runtime and relaunch Vociferous."
    return raw


def build_engine_status(coordinator: Any) -> dict[str, Any]:
    """Build the canonical engine readiness payload consumed by API and UI."""
    settings: VociferousSettings = coordinator.settings
    cuda_status = detect_cuda_runtime()
    asr = _build_asr_status(coordinator, settings, cuda_status)
    slm = _build_slm_status(coordinator, settings, cuda_status)
    readiness = _readiness([asr, slm])
    return {
        "status": readiness,
        "asr": asdict(asr),
        "slm": asdict(slm),
        "providers": _provider_status(settings, slm),
        "hardware": _hardware_status(cuda_status),
        "models": _model_status(settings),
        "downloads": get_tracked_downloads(),
        "packages": _package_versions(),
        "cleanup": _cleanup_status(),
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
            "platform": platform.platform(),
        },
    }


def cleanup_engine_artifacts(*, delete_orphan_spools: bool = False) -> dict[str, Any]:
    """Clean stale engine scratch artifacts without touching transcripts or models."""
    removed: list[str] = []
    errors: list[str] = []

    temp_dir = Path(tempfile_gettempdir())
    for path in temp_dir.glob("vociferous_import_*"):
        _remove_path(path, removed, errors)

    spool_dir = ResourceManager.get_user_cache_dir("audio_spool")
    if delete_orphan_spools:
        for path in spool_dir.glob("*.pcm"):
            _remove_path(path, removed, errors)

    return {
        "removed": removed,
        "errors": errors,
        "orphan_spools_remaining": len(list(spool_dir.glob("*.pcm"))) if spool_dir.exists() else 0,
    }


def tempfile_gettempdir() -> str:
    import tempfile

    return tempfile.gettempdir()


def _build_asr_status(
    coordinator: Any,
    settings: VociferousSettings,
    cuda_status: CudaRuntimeStatus,
) -> EngineComponentStatus:
    model = get_asr_model(settings.model.model)
    downloaded = _model_downloaded(model)
    recording_session = getattr(coordinator, "recording_session", None)
    runtime = _safe_runtime_summary(recording_session, "get_asr_runtime_summary")
    last_error = _safe_last_error(recording_session, "last_asr_error", model.name if model else settings.model.model)

    if model is None:
        state: EngineState = "error"
        detail = f"Unknown ASR model: {settings.model.model}"
    elif not downloaded:
        state = "missing_model"
        detail = f"{model.name} is not downloaded."
    elif getattr(recording_session, "is_transcribing", False):
        state = "transcribing"
        detail = "ASR is transcribing audio."
    elif getattr(coordinator, "is_recording_active", lambda: False)():
        state = "recording"
        detail = "Recording audio."
    elif getattr(recording_session, "is_asr_loaded", False):
        state = "ready"
        detail = "ASR model loaded."
    elif last_error:
        state = "error"
        detail = last_error
    else:
        state = "loading" if downloaded else "missing_model"
        detail = "ASR model is not loaded yet."

    device = _resolve_asr_device(settings, cuda_status)
    if state == "ready" and device == "cpu" and settings.model.device == "auto" and cuda_status.driver_detected:
        state = "degraded_cpu"
        detail = "ASR is ready on CPU because CUDA is not usable."

    return EngineComponentStatus(
        name="Speech recognition",
        state=state,
        ready=state in {"ready", "recording", "transcribing", "degraded_cpu"},
        model_id=settings.model.model,
        model_name=model.name if model else None,
        selected=True,
        downloaded=downloaded,
        device=device,
        detail=detail,
        error=last_error if state == "error" else None,
        runtime=runtime,
    )


def _build_slm_status(
    coordinator: Any,
    settings: VociferousSettings,
    cuda_status: CudaRuntimeStatus,
) -> EngineComponentStatus:
    if not settings.refinement.enabled:
        return EngineComponentStatus(name="Refinement", state="disabled", ready=True, detail="Refinement is disabled.")

    model = get_slm_model(settings.refinement.model_id)
    downloaded = _model_downloaded(model)
    slm_runtime = getattr(coordinator, "slm_runtime", None)
    runtime = _safe_runtime_summary(slm_runtime, "get_runtime_summary")
    last_error = _safe_last_error(slm_runtime, "last_error", model.name if model else settings.refinement.model_id)

    if model is None:
        state: EngineState = "error"
        detail = f"Unknown refinement model: {settings.refinement.model_id}"
    elif not downloaded:
        state = "missing_model"
        detail = f"{model.name} is not downloaded."
    else:
        raw_state = getattr(getattr(slm_runtime, "state", None), "name", "UNKNOWN")
        if raw_state == "READY":
            state = "ready"
            detail = "Refinement model loaded."
        elif raw_state == "LOADING":
            state = "loading"
            detail = "Refinement model is loading."
        elif raw_state == "INFERRING":
            state = "refining"
            detail = "Refinement is running."
        elif raw_state == "ERROR" or last_error:
            state = "error"
            detail = last_error or "Refinement runtime is in error state."
        elif raw_state == "DISABLED":
            state = "disabled"
            detail = "Refinement runtime is disabled."
        else:
            state = "unknown"
            detail = "Refinement runtime has not reported a state."

    device = _resolve_slm_device(settings, cuda_status)
    if state == "ready" and device == "cpu" and settings.refinement.n_gpu_layers != 0 and cuda_status.driver_detected:
        state = "degraded_cpu"
        detail = "Refinement is ready on CPU because CUDA is not usable."

    return EngineComponentStatus(
        name="Refinement",
        state=state,
        ready=state in {"ready", "refining", "degraded_cpu"},
        model_id=settings.refinement.model_id,
        model_name=model.name if model else None,
        selected=True,
        downloaded=downloaded,
        device=device,
        detail=detail,
        error=last_error if state == "error" else None,
        runtime=runtime,
    )


def _readiness(components: Iterable[EngineComponentStatus]) -> str:
    states = {component.state for component in components}
    if "error" in states:
        return "error"
    if "missing_model" in states:
        return "missing_model"
    if "loading" in states:
        return "loading"
    if "degraded_cpu" in states:
        return "degraded"
    if all(component.ready for component in components):
        return "ready"
    return "unknown"


def _resolve_asr_device(settings: VociferousSettings, cuda_status: CudaRuntimeStatus) -> str:
    preference = (settings.model.device or "auto").lower()
    if preference == "cpu":
        return "cpu"
    if preference == "gpu":
        return "cuda" if cuda_status.cuda_available else "unavailable"
    return "cuda" if cuda_status.cuda_available else "cpu"


def _resolve_slm_device(settings: VociferousSettings, cuda_status: CudaRuntimeStatus) -> str:
    if not settings.refinement.enabled:
        return "disabled"
    if settings.refinement.n_gpu_layers == 0:
        return "cpu"
    return "cuda" if cuda_status.cuda_available else "cpu"


def _model_status(settings: VociferousSettings) -> dict[str, Any]:
    catalog = get_model_catalog()
    for category in ("asr", "slm"):
        for model_id, info in catalog[category].items():
            model = get_asr_model(model_id) if category == "asr" else get_slm_model(model_id)
            info["downloaded"] = _model_downloaded(model)
            info["selected"] = model_id == (settings.model.model if category == "asr" else settings.refinement.model_id)
            info["min_vram_mb"] = _estimate_min_vram_mb(model)
            info["cpu_supported"] = not (isinstance(model, SLMModel) and model.quant == "awq")
            info["recommended_device"] = "gpu" if info["min_vram_mb"] >= 6000 or not info["cpu_supported"] else "cpu_or_gpu"
    return catalog


def _model_downloaded(model: ASRModel | SLMModel | None) -> bool:
    if model is None:
        return False
    local_dir_name = model.repo.split("/")[-1]
    return (ResourceManager.get_user_cache_dir("models") / local_dir_name / model.model_file).is_file()


def _estimate_min_vram_mb(model: ASRModel | SLMModel | None) -> int:
    if model is None:
        return 0
    if isinstance(model, ASRModel):
        return max(2048, int(model.size_mb * 1.6))
    if model.quant == "awq":
        return max(6144, int(model.size_mb * 1.35))
    return max(4096, int(model.size_mb * 1.25))


def _hardware_status(cuda_status: CudaRuntimeStatus) -> dict[str, Any]:
    total = cuda_status.vram_total_mb or 0
    used = cuda_status.vram_used_mb or 0
    free = cuda_status.vram_free_mb or 0
    return {
        "backend": "cuda" if cuda_status.cuda_available else "cpu",
        "cuda_available": cuda_status.cuda_available,
        "driver_detected": cuda_status.driver_detected,
        "cuda_device_count": cuda_status.cuda_device_count,
        "gpu_name": cuda_status.gpu_name,
        "detail": cuda_status.detail,
        "vram_total_mb": total,
        "vram_used_mb": used,
        "vram_free_mb": free,
        "vram_used_pct": round((used / total) * 100, 1) if total > 0 else 0.0,
    }


def _provider_status(settings: VociferousSettings, slm: EngineComponentStatus) -> list[dict[str, Any]]:
    local_ready = settings.refinement.enabled and slm.ready
    return [
        {
            "id": "local_ct2",
            "name": "Local CTranslate2",
            "kind": "local",
            "enabled": settings.refinement.enabled,
            "ready": local_ready,
            "active": True,
            "supports_streaming": False,
            "supports_model_listing": True,
            "detail": slm.detail,
        },
        {
            "id": "lm_studio",
            "name": "LM Studio",
            "kind": "openai_compatible",
            "enabled": False,
            "ready": False,
            "active": False,
            "supports_streaming": True,
            "supports_model_listing": True,
            "detail": "Provider contract reserved for external refinement backend integration.",
        },
    ]


def _package_versions() -> dict[str, str | None]:
    packages = ("ctranslate2", "faster-whisper", "tokenizers", "onnxruntime", "pywebview", "litestar")
    versions: dict[str, str | None] = {}
    for package in packages:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return versions


def _cleanup_status() -> dict[str, Any]:
    spool_dir = ResourceManager.get_user_cache_dir("audio_spool")
    temp_dir = Path(tempfile_gettempdir())
    return {
        "orphan_spool_count": len(list(spool_dir.glob("*.pcm"))) if spool_dir.exists() else 0,
        "import_temp_count": len(list(temp_dir.glob("vociferous_import_*"))),
    }


def _safe_runtime_summary(target: Any, method_name: str) -> dict[str, Any] | None:
    if target is None:
        return None
    method = getattr(target, method_name, None)
    if not callable(method):
        return None
    try:
        summary = method()
    except Exception:
        return None
    return dict(summary) if isinstance(summary, dict) else None


def _safe_last_error(target: Any, attr_name: str, model_name: str | None) -> str | None:
    if target is None:
        return None
    value = getattr(target, attr_name, None)
    if not value:
        return None
    return normalize_engine_error(str(value), model_name=model_name)


def _remove_path(path: Path, removed: list[str], errors: list[str]) -> None:
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
        removed.append(str(path))
    except OSError as exc:
        errors.append(f"{path}: {exc}")