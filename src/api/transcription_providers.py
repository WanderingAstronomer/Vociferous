"""Transcription provider model listing and connection checks."""

from __future__ import annotations

import asyncio
import logging

from litestar import Response, get, post

from src.api.deps import get_coordinator
from src.core.settings import VociferousSettings
from src.services.transcription_service import (
    TranscriptionProviderRequestError,
    list_external_transcription_provider_models,
    test_external_transcription_provider,
)

logger = logging.getLogger(__name__)

_EXTERNAL_PROVIDERS = frozenset({"groq"})


def _provider_settings(provider_id: str, overrides: dict | None = None) -> VociferousSettings:
    if provider_id not in _EXTERNAL_PROVIDERS:
        raise ValueError(f"Unknown external transcription provider: {provider_id}")
    coordinator = get_coordinator()
    merged = coordinator.settings.model_dump()
    if overrides:
        provider_overrides = {key: value for key, value in overrides.items() if value is not None}
        merged["model"].setdefault(provider_id, {}).update(provider_overrides)
    return VociferousSettings(**merged)


@get("/api/transcription/providers/{provider_id:str}/models")
async def list_transcription_provider_models(provider_id: str) -> Response:
    """List models from an external transcription provider."""
    try:
        settings = _provider_settings(provider_id)
        models = await asyncio.to_thread(list_external_transcription_provider_models, settings, provider_id)
    except ValueError as exc:
        return Response(content={"error": str(exc)}, status_code=400)
    except TranscriptionProviderRequestError as exc:
        return Response(content={"error": str(exc)}, status_code=exc.status_code)
    except Exception as exc:
        logger.warning("Failed to list transcription provider models for %s: %s", provider_id, exc)
        return Response(content={"error": str(exc)}, status_code=502)
    return Response(content={"provider": provider_id, "models": models})


@post("/api/transcription/providers/{provider_id:str}/test", status_code=200)
async def test_transcription_provider(provider_id: str, data: dict | None = None) -> Response:
    """Test external transcription provider connectivity using saved settings plus optional draft overrides."""
    try:
        settings = _provider_settings(provider_id, data or {})
        result = await asyncio.to_thread(test_external_transcription_provider, settings, provider_id)
    except ValueError as exc:
        return Response(content={"ok": False, "error": str(exc)}, status_code=400)
    except TranscriptionProviderRequestError as exc:
        return Response(content={"ok": False, "error": str(exc)}, status_code=exc.status_code)
    except Exception as exc:
        logger.warning("Transcription provider test failed for %s: %s", provider_id, exc)
        return Response(content={"ok": False, "error": str(exc)}, status_code=502)
    return Response(content=result)