"""
Configuration, insight, and intent dispatch API routes.
"""

from __future__ import annotations

import logging

from litestar import Response, get, post, put

from src.api.deps import get_coordinator

logger = logging.getLogger(__name__)


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


# --- Insight ---


@get("/api/insight", sync_to_thread=True)
def get_insight() -> dict:
    """Return the cached UserView insight, or empty text if none exists yet."""
    coordinator = get_coordinator()
    return {"text": coordinator.get_insight_text()}


@get("/api/motd", sync_to_thread=True)
def get_motd() -> dict:
    """Return the cached insight text (alias for /api/insight; kept for frontend compat)."""
    coordinator = get_coordinator()
    return {"text": coordinator.get_insight_text()}


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
        "commit_edits": defs.CommitEditsIntent,
        "revert_to_raw": defs.RevertToRawIntent,
        "refine_transcript": defs.RefineTranscriptIntent,
        "retitle_transcript": defs.RetitleTranscriptIntent,
        "append_to_transcript": defs.AppendToTranscriptIntent,
        "set_analytics_inclusion": defs.SetAnalyticsInclusionIntent,
        "update_config": defs.UpdateConfigIntent,
        "restart_engine": defs.RestartEngineIntent,
        "import_audio_file": defs.ImportAudioFileIntent,
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
