"""
System API routes — health, audio import, key capture.

Config/insight routes → config.py
Model catalog/download → models.py
Window control/export  → window.py
"""

from __future__ import annotations

import functools
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from litestar import Response, get, post
from litestar.datastructures import UploadFile
from litestar.enums import RequestEncodingType
from litestar.params import Body

from src.api.deps import get_coordinator
from src.core.constants import APP_VERSION
from src.core.cuda_runtime import detect_cuda_runtime
from src.core.resource_manager import ResourceManager
from src.services.audio_service import AudioService

logger = logging.getLogger(__name__)


def _open_directory(path: Path) -> None:
    """Open a directory in the platform file manager."""
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
        return
    subprocess.Popen(["xdg-open", str(path)])


# --- Health ---


@functools.lru_cache(maxsize=1)
def _detect_gpu_status() -> dict:
    """Detect GPU availability for ASR and SLM inference.

    Result is cached via lru_cache after the first call. Call
    _detect_gpu_status.cache_clear() to reset (e.g. in tests or after
    engine restart).
    """
    status = detect_cuda_runtime()
    gpu: dict = {
        "cuda_available": status.cuda_available,
        "driver_detected": status.driver_detected,
        "cuda_device_count": status.cuda_device_count,
        "detail": status.detail,
        "gpu_name": status.gpu_name,
        "slm_gpu_layers": -1,
        "vram_total_mb": status.vram_total_mb,
        "vram_used_mb": status.vram_used_mb,
        "vram_free_mb": status.vram_free_mb,
    }

    # SLM GPU layer configuration from settings
    try:
        from src.core.settings import get_settings

        s = get_settings()
        gpu["slm_gpu_layers"] = s.refinement.n_gpu_layers
    except Exception:
        pass

    return gpu


def prewarm_health_cache() -> None:
    """Trigger GPU status detection in a background thread to warm the lru_cache.

    Called once from ``create_app()`` so the first ``GET /api/health`` response
    is fast — without this, the first request blocks for up to 5 s while
    ``nvidia-smi`` runs.
    """
    import threading

    threading.Thread(target=_detect_gpu_status, daemon=True, name="gpu-prewarm").start()


def _detect_mic_status() -> dict:
    """Probe the default input device. Not cached — device can change at any time."""
    status = AudioService.detect_microphone()
    return {
        "available": status.available,
        "device_name": status.device_name,
        "host_api": status.host_api,
        "input_channels": status.input_channels,
        "default_sample_rate": status.default_sample_rate,
        "supports_16k": status.supports_16k,
        "detail": status.detail,
    }


@get("/api/health", sync_to_thread=True)
def health() -> dict:
    coordinator = get_coordinator()
    return {
        "status": "ok",
        "version": APP_VERSION,
        "transcripts": coordinator.get_transcript_count(),
        "recording_active": coordinator.is_recording_active(),
        "gpu": _detect_gpu_status(),
        "mic": _detect_mic_status(),
    }


# --- Audio Import ---


_ALLOWED_AUDIO_EXTENSIONS = frozenset((".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm", ".wma", ".aac", ".opus"))


@post("/api/import-audio")
async def import_audio_file(
    data: UploadFile = Body(media_type=RequestEncodingType.MULTI_PART),
) -> Response:
    """
    Accept an uploaded audio file, save to temp, dispatch transcription.

    The heavy lifting (decode + transcribe) runs on a background thread.
    The temp file is cleaned up after processing.
    Results arrive via WebSocket: transcription_complete / transcription_error.
    """
    from src.core.intents.definitions import ImportAudioFileIntent

    coordinator = get_coordinator()

    original_name = data.filename or "upload.wav"
    ext = Path(original_name).suffix.lower()
    if ext not in _ALLOWED_AUDIO_EXTENSIONS:
        return Response(content={"error": f"Unsupported format: {ext}"}, status_code=400)

    content = await data.read()
    if not content:
        return Response(content={"error": "Empty file"}, status_code=400)

    fd, tmp_path = tempfile.mkstemp(suffix=ext, prefix="vociferous_import_")
    try:
        os.write(fd, content)
    finally:
        os.close(fd)

    intent = ImportAudioFileIntent(file_path=tmp_path, cleanup_source=True)
    success = coordinator.command_bus.dispatch(intent)

    return Response(content={"status": "importing", "file": original_name, "dispatched": success})


# --- Key Capture ---


@post("/api/keycapture/start")
async def start_key_capture() -> Response:
    """Start key capture mode for hotkey rebinding. Keys are emitted via WebSocket."""
    import os
    import sys

    from src.input_handler.key_capture import make_capture_handler

    coordinator = get_coordinator()
    if not coordinator.input_listener:
        return Response(content={"error": "Input handler not available"}, status_code=503)

    backend = coordinator.input_listener.active_backend
    if backend is None:
        return Response(
            content={
                "error": (
                    "No input backend is active. Hotkey capture is unavailable. "
                    "On Linux, ensure evdev access (input group) and restart session."
                )
            },
            status_code=503,
        )

    if (
        type(backend).__name__ == "PynputBackend"
        and sys.platform.startswith("linux")
        and (os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY")))
    ):
        return Response(
            content={
                "error": (
                    "Hotkey capture is degraded under Wayland with PynputBackend. "
                    "Use evdev backend with input-group permissions."
                )
            },
            status_code=503,
        )

    def on_chord(combo: str, display: str) -> None:
        coordinator.input_listener.disable_capture_mode()
        coordinator.event_bus.emit("key_captured", {"combo": combo, "display": display})

    handler = make_capture_handler(on_chord=on_chord)
    coordinator.input_listener.enable_capture_mode(handler)
    return Response(content={"status": "capturing"})


@post("/api/keycapture/stop")
async def stop_key_capture() -> Response:
    """Cancel key capture mode."""
    coordinator = get_coordinator()
    if coordinator.input_listener:
        coordinator.input_listener.disable_capture_mode()
    return Response(content={"status": "stopped"})


@post("/api/logs/open-dir", sync_to_thread=True)
def open_log_directory() -> dict:
    """Open the persistent log directory in the system file manager."""
    log_dir = ResourceManager.get_user_log_dir()
    try:
        _open_directory(log_dir)
    except Exception as e:
        logger.exception("Failed to open log directory %s", log_dir)
        return {"status": "error", "path": str(log_dir), "error": str(e)}
    return {"status": "opened", "path": str(log_dir)}
