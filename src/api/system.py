"""
System API routes — config, models, health, mini widget, key capture.
"""

from __future__ import annotations

import functools
import importlib.metadata
import logging
import threading
import tomllib
from pathlib import Path

from litestar import Response, get, post, put

from src.api.deps import get_coordinator

logger = logging.getLogger(__name__)


def _resolve_app_version() -> str:
    """Resolve app version from package metadata, with pyproject fallback."""
    try:
        return importlib.metadata.version("vociferous")
    except importlib.metadata.PackageNotFoundError:
        pass
    except Exception:
        logger.exception("Failed to read version from package metadata")

    try:
        root = Path(__file__).resolve().parents[2]
        pyproject_path = root / "pyproject.toml"
        if pyproject_path.is_file():
            with pyproject_path.open("rb") as f:
                data = tomllib.load(f)
            project = data.get("project", {})
            version = project.get("version")
            if isinstance(version, str) and version.strip():
                return version.strip()
    except Exception:
        logger.exception("Failed to read version from pyproject.toml")

    return "unknown"


APP_VERSION = _resolve_app_version()


# --- Config ---


@get("/api/config", sync_to_thread=True)
def get_config() -> dict:
    coordinator = get_coordinator()
    return coordinator.settings.model_dump()


@put("/api/config", sync_to_thread=True)
def update_config(data: dict) -> dict:
    from litestar.exceptions import InternalServerException

    from src.core.intents.definitions import UpdateConfigIntent

    coordinator = get_coordinator()
    intent = UpdateConfigIntent(settings=data)
    success = coordinator.command_bus.dispatch(intent)

    if not success:
        logger.error("Failed to update config via intent")
        raise InternalServerException(detail="Config update failed")

    return coordinator.settings.model_dump()


@post("/api/engine/restart", sync_to_thread=True)
def restart_engine() -> dict:
    """Restart ASR + SLM models (background thread)."""
    from src.core.intents.definitions import RestartEngineIntent

    coordinator = get_coordinator()
    coordinator.command_bus.dispatch(RestartEngineIntent())
    return {"status": "restarting"}


@get("/api/insight", sync_to_thread=True)
def get_insight() -> dict:
    """Return the cached UserView insight, or empty text if none exists yet."""
    coordinator = get_coordinator()
    text = ""
    if coordinator.insight_manager is not None:
        text = coordinator.insight_manager.cached_text
    return {"text": text}


@post("/api/insight/refresh", sync_to_thread=True)
def refresh_insight() -> dict:
    """Force-trigger insight regeneration, bypassing TTL/count guards."""
    from src.core.intents.definitions import RefreshInsightIntent

    coordinator = get_coordinator()
    started = coordinator.command_bus.dispatch(RefreshInsightIntent())
    return {"status": "generating" if started else "unavailable"}


@get("/api/motd", sync_to_thread=True)
def get_motd() -> dict:
    """Return the cached TranscribeView header MOTD, or empty text if none exists yet."""
    coordinator = get_coordinator()
    text = ""
    if coordinator.motd_manager is not None:
        text = coordinator.motd_manager.cached_text
    return {"text": text}


@post("/api/export")
async def export_file(data: dict) -> Response:
    """
    Write exported content to a user-chosen path via the native save dialog.

    Expects: { "content": str, "filename": str }
    Returns: { "path": str } on success, or error.
    """
    import asyncio

    content: str = data.get("content", "")
    filename: str = Path(data.get("filename", "export.txt")).name

    coordinator = get_coordinator()

    # create_file_dialog must run on the main (GTK/UI) thread — use run_in_executor
    # so we don't block the async API event loop.
    loop = asyncio.get_running_loop()
    save_path: str | None = await loop.run_in_executor(None, coordinator.show_save_dialog, filename)

    if save_path is None:
        return Response(content={"error": "cancelled"}, status_code=400)

    try:
        Path(save_path).write_text(content, encoding="utf-8")
    except OSError as e:
        logger.error("Export write failed: %s", e)
        return Response(content={"error": str(e)}, status_code=500)

    return Response(content={"path": save_path})


@get("/api/models", sync_to_thread=True)
def list_models() -> dict:
    from src.core.model_registry import get_model_catalog
    from src.core.resource_manager import ResourceManager

    catalog = get_model_catalog()
    models_dir = ResourceManager.get_user_cache_dir("models")

    # Attach download status to each model entry.
    # CT2 models are directories named after the repo slug.
    for category in ("asr", "slm"):
        for model_id, info in catalog[category].items():
            local_dir_name = info["repo"].split("/")[-1]
            model_bin = models_dir / local_dir_name / info["model_file"]
            info["downloaded"] = model_bin.is_file()

    return catalog


@post("/api/models/download")
async def download_model(data: dict) -> Response:
    """Start downloading a model. Sends progress via WebSocket.

    H-pattern exception: this spawns a progress-emitting thread with inline
    callbacks — wrapping it in an intent would just relocate the thread logic
    without adding any decoupling benefit.
    """
    from src.core.model_registry import ASRModel, SLMModel, get_asr_model, get_slm_model
    from src.core.resource_manager import ResourceManager

    coordinator = get_coordinator()
    model_type = data.get("model_type", "asr")
    model_id = data.get("model_id")
    if not model_id:
        return Response(content={"error": "Missing model_id"}, status_code=400)

    if model_type == "asr":
        model: ASRModel | SLMModel | None = get_asr_model(model_id)
    else:
        model = get_slm_model(model_id)

    if model is None:
        return Response(content={"error": f"Unknown model: {model_id}"}, status_code=404)

    cache_dir = ResourceManager.get_user_cache_dir("models")

    def do_download():
        from src.provisioning.core import ProvisioningError, download_model_directory

        def on_progress(msg: str):
            coordinator.event_bus.emit(
                "download_progress",
                {"model_id": model_id, "status": "downloading", "message": msg},
            )

        try:
            coordinator.event_bus.emit(
                "download_progress",
                {
                    "model_id": model_id,
                    "status": "started",
                    "message": f"Starting download of {model.name}...",
                },
            )
            download_model_directory(
                repo_id=model.repo,
                target_dir=cache_dir,
                progress_callback=on_progress,
                expected_sha256=getattr(model, "sha256", None),
                model_file=model.model_file,
            )
            coordinator.event_bus.emit(
                "download_progress",
                {
                    "model_id": model_id,
                    "status": "complete",
                    "message": f"{model.name} downloaded successfully.",
                },
            )
        except ProvisioningError as e:
            coordinator.event_bus.emit(
                "download_progress",
                {"model_id": model_id, "status": "error", "message": str(e)},
            )
        except Exception as e:
            logger.exception("Model download failed: %s", model_id)
            coordinator.event_bus.emit(
                "download_progress",
                {
                    "model_id": model_id,
                    "status": "error",
                    "message": f"Download failed: {e}",
                },
            )

    download_thread = threading.Thread(target=do_download, daemon=True, name=f"download-{model_id}")
    download_thread.start()

    return Response(content={"status": "started", "model_id": model_id})


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
        "whisper_backends": "",
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

    # CTranslate2 backend info
    try:
        import ctranslate2

        cuda_count = ctranslate2.get_cuda_device_count()
        gpu["whisper_backends"] = f"ctranslate2 (CUDA devices: {cuda_count})" if cuda_count > 0 else "ctranslate2 (CPU)"
    except Exception:
        gpu["whisper_backends"] = "unavailable"

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
        "transcripts": coordinator.db.transcript_count() if coordinator.db else 0,
        "recording_active": (
            coordinator.recording_session.is_recording if coordinator.recording_session is not None else False
        ),
        "gpu": _detect_gpu_status(),
    }


# --- Window control (frameless title-bar) ---


@post("/api/window/minimize", sync_to_thread=True)
def minimize_window() -> dict:
    """Minimize the main window."""
    coordinator = get_coordinator()
    coordinator.minimize_window()
    return {"status": "ok"}


@post("/api/window/maximize", sync_to_thread=True)
def maximize_window() -> dict:
    """Toggle maximize/restore on the main window."""
    coordinator = get_coordinator()
    coordinator.maximize_window()
    return {"status": "ok", "maximized": coordinator.is_window_maximized()}


@post("/api/window/close", sync_to_thread=True)
def close_window() -> dict:
    """Close the main window and shut down."""
    coordinator = get_coordinator()
    coordinator.close_window()
    return {"status": "ok"}


# --- Key Capture ---


@post("/api/keycapture/start")
async def start_key_capture() -> Response:
    """Start key capture mode for hotkey rebinding. Keys are emitted via WebSocket.

    H-pattern exception: sets up closures over local state (captured_keys set,
    modifier maps) that belong in the API layer, not in a handler class.
    """
    import os
    import sys

    from src.input_handler.types import InputEvent, KeyCode

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

    captured_keys: set[str] = set()

    # Map KeyCode back to human-readable names for display
    modifier_codes = {
        KeyCode.CTRL_LEFT,
        KeyCode.CTRL_RIGHT,
        KeyCode.SHIFT_LEFT,
        KeyCode.SHIFT_RIGHT,
        KeyCode.ALT_LEFT,
        KeyCode.ALT_RIGHT,
        KeyCode.META_LEFT,
        KeyCode.META_RIGHT,
    }

    modifier_labels: dict[KeyCode, str] = {
        KeyCode.CTRL_LEFT: "Ctrl",
        KeyCode.CTRL_RIGHT: "Ctrl",
        KeyCode.SHIFT_LEFT: "Shift",
        KeyCode.SHIFT_RIGHT: "Shift",
        KeyCode.ALT_LEFT: "Alt",
        KeyCode.ALT_RIGHT: "Alt",
        KeyCode.META_LEFT: "Meta",
        KeyCode.META_RIGHT: "Meta",
    }

    def on_key(key: KeyCode, event: InputEvent) -> None:
        if event == InputEvent.KEY_PRESS:
            if key in modifier_codes:
                captured_keys.add(modifier_labels[key])
            else:
                # Non-modifier key pressed — finalize the chord
                key_name = key.name.replace("_", " ").title().replace(" ", "_")
                # Build the combo string: modifiers + key, using + separator
                parts = sorted(captured_keys) + [key.name]
                combo = "+".join(parts)

                coordinator.input_listener.disable_capture_mode()
                coordinator.event_bus.emit(
                    "key_captured", {"combo": combo, "display": " + ".join(sorted(captured_keys) + [key_name])}
                )
                captured_keys.clear()

    coordinator.input_listener.enable_capture_mode(on_key)
    return Response(content={"status": "capturing"})


@post("/api/keycapture/stop")
async def stop_key_capture() -> Response:
    """Cancel key capture mode."""
    coordinator = get_coordinator()
    if coordinator.input_listener:
        coordinator.input_listener.disable_capture_mode()
    return Response(content={"status": "stopped"})


# --- Generic intent dispatch ---


@post("/api/intents")
async def dispatch_intent(data: dict) -> Response:
    """
    Generic intent dispatch from frontend.

    Expects: {"type": "begin_recording", ...fields}
    """
    from src.core.intents import definitions as defs

    coordinator = get_coordinator()
    intent_type_name = data.pop("type", None)
    if not intent_type_name:
        return Response(content={"error": "Missing 'type'"}, status_code=400)

    intent_map = {
        "begin_recording": defs.BeginRecordingIntent,
        "stop_recording": defs.StopRecordingIntent,
        "cancel_recording": defs.CancelRecordingIntent,
        "toggle_recording": defs.ToggleRecordingIntent,
        "delete_transcript": defs.DeleteTranscriptIntent,
        "batch_delete_transcripts": defs.BatchDeleteTranscriptsIntent,
        "clear_transcripts": defs.ClearTranscriptsIntent,
        "commit_edits": defs.CommitEditsIntent,
        "refine_transcript": defs.RefineTranscriptIntent,
        "rename_transcript": defs.RenameTranscriptIntent,
        "batch_retitle": defs.BatchRetitleIntent,
        "retitle_transcript": defs.RetitleTranscriptIntent,
        "create_tag": defs.CreateTagIntent,
        "update_tag": defs.UpdateTagIntent,
        "delete_tag": defs.DeleteTagIntent,
        "assign_tags": defs.AssignTagsIntent,
        "update_config": defs.UpdateConfigIntent,
        "restart_engine": defs.RestartEngineIntent,
        "refresh_insight": defs.RefreshInsightIntent,
    }

    intent_cls = intent_map.get(intent_type_name)
    if intent_cls is None:
        return Response(
            content={"error": f"Unknown intent: {intent_type_name}"},
            status_code=400,
        )

    try:
        intent = intent_cls(**data)
    except Exception as e:
        return Response(content={"error": str(e)}, status_code=400)

    success = coordinator.command_bus.dispatch(intent)
    return Response(content={"dispatched": success})
