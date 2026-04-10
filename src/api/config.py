"""
Configuration, insight, and intent dispatch API routes.
"""

from __future__ import annotations

import logging

from litestar import Response, delete, get, post, put

from src.api.deps import get_coordinator

logger = logging.getLogger(__name__)


def _update_default_refinement_prompt(coordinator, transcript_id: int | None) -> bool:
    from src.core.intents.definitions import UpdateConfigIntent

    intent = UpdateConfigIntent(settings={"refinement": {"default_prompt_transcript_id": transcript_id}})
    return coordinator.command_bus.dispatch(intent)


def clear_default_refinement_prompt_if_matches(coordinator, transcript_id: int) -> bool:
    current_id = coordinator.settings.refinement.default_prompt_transcript_id
    if current_id != transcript_id:
        return False
    return _update_default_refinement_prompt(coordinator, None)


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


@put("/api/config/refinement/default-prompt")
async def set_default_refinement_prompt(data: dict) -> Response:
    import asyncio

    transcript_id = data.get("transcript_id")
    if not isinstance(transcript_id, int):
        return Response(content={"error": "'transcript_id' must be an integer"}, status_code=400)

    coordinator = get_coordinator()
    if coordinator.db is None:
        return Response(content={"error": "Database not available"}, status_code=503)

    transcript = await asyncio.to_thread(coordinator.db.get_transcript, transcript_id)
    if transcript is None:
        return Response(content={"error": "Transcript not found"}, status_code=404)
    if not transcript.text.strip():
        return Response(content={"error": "Default refinement prompt transcript cannot be empty"}, status_code=400)
    if not any(tag.name == "Prompt" for tag in transcript.tags):
        return Response(
            content={"error": "Transcript must be tagged 'Prompt' before it can become the default refinement prompt"},
            status_code=400,
        )

    if not _update_default_refinement_prompt(coordinator, transcript_id):
        logger.error("Failed to persist default refinement prompt transcript %d", transcript_id)
        return Response(content={"error": "Failed to update default refinement prompt"}, status_code=500)

    return Response(content={"status": "updated", "default_prompt_transcript_id": transcript_id})


@delete("/api/config/refinement/default-prompt", status_code=200, sync_to_thread=True)
def clear_default_refinement_prompt() -> Response:
    coordinator = get_coordinator()
    if not _update_default_refinement_prompt(coordinator, None):
        logger.error("Failed to clear default refinement prompt transcript")
        return Response(content={"error": "Failed to clear default refinement prompt"}, status_code=500)

    return Response(content={"status": "cleared", "default_prompt_transcript_id": None})


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
