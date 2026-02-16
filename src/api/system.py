"""
System API routes — config, models, health, mini widget, key capture.
"""

from __future__ import annotations

import logging
import threading

from litestar import Response, get, post, put

from src.api.deps import get_coordinator

logger = logging.getLogger(__name__)


# --- Config ---


@get("/api/config")
async def get_config() -> dict:
    coordinator = get_coordinator()
    return coordinator.settings.model_dump()


@put("/api/config")
async def update_config(data: dict) -> dict:
    from src.core.settings import update_settings

    coordinator = get_coordinator()
    new_settings = update_settings(**data)
    coordinator.settings = new_settings
    coordinator.event_bus.emit("config_updated", new_settings.model_dump())

    # Reload activation keys if the input handler is running
    if coordinator.input_listener:
        try:
            coordinator.input_listener.update_activation_keys()
            logger.info("Input handler activation keys reloaded")
        except Exception:
            logger.exception("Failed to reload activation keys")

    return new_settings.model_dump()


@post("/api/engine/restart")
async def restart_engine() -> dict:
    """Restart ASR + SLM models (background thread)."""
    coordinator = get_coordinator()
    coordinator.restart_engine()
    return {"status": "restarting"}


# --- Models ---


@get("/api/models")
async def list_models() -> dict:
    from src.core.model_registry import get_model_catalog
    from src.core.resource_manager import ResourceManager

    catalog = get_model_catalog()
    models_dir = ResourceManager.get_user_cache_dir("models")

    # Attach download status to each model entry
    for category in ("asr", "slm"):
        for model_id, info in catalog[category].items():
            filepath = models_dir / info["filename"]
            info["downloaded"] = filepath.is_file()

    return catalog


@post("/api/models/download")
async def download_model(data: dict) -> Response:
    """Start downloading a model. Sends progress via WebSocket."""
    from src.core.model_registry import get_asr_model, get_slm_model
    from src.core.resource_manager import ResourceManager

    coordinator = get_coordinator()
    model_type = data.get("model_type", "asr")
    model_id = data.get("model_id")
    if not model_id:
        return Response(content={"error": "Missing model_id"}, status_code=400)

    if model_type == "asr":
        model = get_asr_model(model_id)
    else:
        model = get_slm_model(model_id)

    if model is None:
        return Response(content={"error": f"Unknown model: {model_id}"}, status_code=404)

    cache_dir = ResourceManager.get_user_cache_dir("models")

    def do_download():
        from src.provisioning.core import ProvisioningError, download_model_file

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
            download_model_file(
                repo_id=model.repo,
                filename=model.filename,
                target_dir=cache_dir,
                progress_callback=on_progress,
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


def _detect_gpu_status() -> dict:
    """Detect GPU availability for ASR and SLM inference."""
    gpu: dict = {"cuda_available": False, "detail": "", "whisper_backends": "", "slm_gpu_layers": -1}
    try:
        import subprocess

        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            gpu["cuda_available"] = True
            gpu["detail"] = result.stdout.strip().split("\n")[0]
        else:
            gpu["detail"] = "nvidia-smi failed or no GPU found"
    except FileNotFoundError:
        gpu["detail"] = "nvidia-smi not found — no NVIDIA driver"
    except Exception as e:
        gpu["detail"] = str(e)

    # Whisper.cpp compiled backend info
    try:
        from pywhispercpp.model import Model as WhisperModel
        gpu["whisper_backends"] = WhisperModel.system_info() or ""
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


@get("/api/health")
async def health() -> dict:
    coordinator = get_coordinator()
    return {
        "status": "ok",
        "version": "4.0.0-dev",
        "transcripts": coordinator.db.transcript_count() if coordinator.db else 0,
        "gpu": _detect_gpu_status(),
    }


# --- Mini widget ---


@post("/api/mini-widget/toggle")
async def toggle_mini_widget() -> dict:
    coordinator = get_coordinator()
    coordinator.toggle_mini_widget()
    return {"status": "ok"}


# --- Window control (frameless title-bar) ---


@post("/api/window/minimize")
async def minimize_window() -> dict:
    """Minimize the main window."""
    coordinator = get_coordinator()
    coordinator.minimize_window()
    return {"status": "ok"}


@post("/api/window/maximize")
async def maximize_window() -> dict:
    """Toggle maximize/restore on the main window."""
    coordinator = get_coordinator()
    coordinator.maximize_window()
    return {"status": "ok"}


@post("/api/window/close")
async def close_window() -> dict:
    """Close the main window and shut down."""
    coordinator = get_coordinator()
    coordinator.close_window()
    return {"status": "ok"}


# --- Key Capture ---


@post("/api/keycapture/start")
async def start_key_capture() -> Response:
    """Start key capture mode for hotkey rebinding. Keys are emitted via WebSocket."""
    from src.input_handler.types import InputEvent, KeyCode

    coordinator = get_coordinator()
    if not coordinator.input_listener:
        return Response(content={"error": "Input handler not available"}, status_code=503)

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
        "commit_edits": defs.CommitEditsIntent,
        "refine_transcript": defs.RefineTranscriptIntent,
        "create_project": defs.CreateProjectIntent,
        "delete_project": defs.DeleteProjectIntent,
        "assign_project": defs.AssignProjectIntent,
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
