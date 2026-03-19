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
import tempfile
from pathlib import Path

from litestar import Response, get, post
from litestar.datastructures import UploadFile
from litestar.enums import RequestEncodingType
from litestar.params import Body

from src.api.deps import get_coordinator
from src.core.constants import APP_VERSION

logger = logging.getLogger(__name__)


# --- Health ---


@functools.lru_cache(maxsize=1)
def _detect_gpu_status() -> dict:
    """Detect GPU availability for ASR and SLM inference.

    Result is cached via lru_cache after the first call. Call
    _detect_gpu_status.cache_clear() to reset (e.g. in tests or after
    engine restart).
    """
    gpu: dict = {
        "cuda_available": False,
        "detail": "",
        "slm_gpu_layers": -1,
        "vram_total_mb": 0,
        "vram_used_mb": 0,
        "vram_free_mb": 0,
    }
    try:
        import subprocess

        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            gpu["cuda_available"] = True
            parts = [p.strip() for p in result.stdout.strip().split("\n")[0].split(",")]
            gpu["detail"] = parts[0] if len(parts) > 0 else "unknown"
            try:
                gpu["vram_total_mb"] = int(parts[1]) if len(parts) > 1 else 0
                gpu["vram_used_mb"] = int(parts[2]) if len(parts) > 2 else 0
                gpu["vram_free_mb"] = int(parts[3]) if len(parts) > 3 else 0
            except (ValueError, IndexError):
                pass  # VRAM parsing failed — leave at 0
        else:
            gpu["detail"] = "nvidia-smi failed or no GPU found"
    except FileNotFoundError:
        gpu["detail"] = "nvidia-smi not found — no NVIDIA driver"
    except Exception as e:
        gpu["detail"] = str(e)

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


@get("/api/health", sync_to_thread=True)
def health() -> dict:
    coordinator = get_coordinator()
    return {
        "status": "ok",
        "version": APP_VERSION,
        "transcripts": coordinator.get_transcript_count(),
        "recording_active": coordinator.is_recording_active(),
        "gpu": _detect_gpu_status(),
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
