"""
Model catalog and download API routes.
"""

from __future__ import annotations

import logging
import threading

from litestar import Response, get, post

from src.api.deps import get_coordinator

logger = logging.getLogger(__name__)


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
