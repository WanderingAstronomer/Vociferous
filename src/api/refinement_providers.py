"""Refinement provider model listing and connection checks."""

from __future__ import annotations

import asyncio
import logging
import os

from litestar import Response, delete, get, post, put

from src.api.deps import get_coordinator
from src.core.secret_store import (
    SecretStoreUnavailable,
    delete_provider_api_key,
    get_provider_api_key,
    get_secret_backend,
    provider_api_key_is_valid,
    store_provider_api_key,
)
from src.core.settings import VociferousSettings
from src.refinement.providers import ProviderRequestError, list_external_provider_models, test_external_provider

logger = logging.getLogger(__name__)

_EXTERNAL_PROVIDERS = frozenset({"lm_studio", "groq"})


def _provider_settings(provider_id: str, overrides: dict | None = None) -> VociferousSettings:
    if provider_id not in _EXTERNAL_PROVIDERS:
        raise ValueError(f"Unknown external refinement provider: {provider_id}")
    coordinator = get_coordinator()
    merged = coordinator.settings.model_dump()
    if overrides:
        provider_overrides = {key: value for key, value in overrides.items() if value is not None}
        merged["refinement"].setdefault(provider_id, {}).update(provider_overrides)
    return VociferousSettings(**merged)


@get("/api/refinement/providers/{provider_id:str}/models")
async def list_refinement_provider_models(provider_id: str) -> Response:
    """List models from an external refinement provider."""
    try:
        settings = _provider_settings(provider_id)
        models = await asyncio.to_thread(list_external_provider_models, settings, provider_id)
    except ValueError as exc:
        return Response(content={"error": str(exc)}, status_code=400)
    except ProviderRequestError as exc:
        return Response(content={"error": str(exc)}, status_code=exc.status_code)
    except Exception as exc:
        logger.warning("Failed to list refinement provider models for %s: %s", provider_id, exc)
        return Response(content={"error": str(exc)}, status_code=502)
    return Response(content={"provider": provider_id, "models": models})


@post("/api/refinement/providers/{provider_id:str}/test", status_code=200)
async def test_refinement_provider(provider_id: str, data: dict | None = None) -> Response:
    """Test external provider connectivity using saved settings plus optional draft overrides."""
    try:
        settings = _provider_settings(provider_id, data or {})
        result = await asyncio.to_thread(test_external_provider, settings, provider_id)
    except ValueError as exc:
        return Response(content={"ok": False, "error": str(exc)}, status_code=400)
    except ProviderRequestError as exc:
        return Response(content={"ok": False, "error": str(exc)}, status_code=exc.status_code)
    except Exception as exc:
        logger.warning("Refinement provider test failed for %s: %s", provider_id, exc)
        return Response(content={"ok": False, "error": str(exc)}, status_code=502)
    return Response(content=result)


@get("/api/refinement/providers/{provider_id:str}/api-key")
async def get_refinement_provider_api_key_status(provider_id: str) -> Response:
    """Return API key availability without exposing the secret value."""
    try:
        settings = _provider_settings(provider_id)
        provider_settings = getattr(settings.refinement, provider_id)
        env_name = provider_settings.api_key_env
        env_key = os.environ.get(env_name) if env_name else None
        stored_key = await asyncio.to_thread(get_provider_api_key, provider_id)
        has_env_key = bool(env_key)
        has_stored_key = bool(stored_key)
        has_env_key_valid = provider_api_key_is_valid(provider_id, env_key) if has_env_key else False
        has_stored_key_valid = provider_api_key_is_valid(provider_id, stored_key) if has_stored_key else False
        source = "stored" if has_stored_key else "environment" if has_env_key else "none"
        source_valid = has_stored_key_valid if source == "stored" else has_env_key_valid if source == "environment" else False
    except ValueError as exc:
        return Response(content={"error": str(exc)}, status_code=400)
    return Response(
        content={
            "provider": provider_id,
            "backend": get_secret_backend(),
            "has_env_key": has_env_key,
            "has_env_key_valid": has_env_key_valid,
            "has_stored_key": has_stored_key,
            "has_stored_key_valid": has_stored_key_valid,
            "source": source,
            "source_valid": source_valid,
            "api_key_env": env_name,
        }
    )


@put("/api/refinement/providers/{provider_id:str}/api-key")
async def save_refinement_provider_api_key(provider_id: str, data: dict) -> Response:
    """Save a provider API key to the local secret backend."""
    try:
        if provider_id not in _EXTERNAL_PROVIDERS:
            raise ValueError(f"Unknown external refinement provider: {provider_id}")
        api_key = data.get("api_key")
        if not isinstance(api_key, str) or not api_key.strip():
            return Response(content={"error": "'api_key' must be a non-empty string"}, status_code=400)
        await asyncio.to_thread(store_provider_api_key, provider_id, api_key)
    except SecretStoreUnavailable as exc:
        return Response(content={"error": str(exc), "backend": get_secret_backend()}, status_code=501)
    except ValueError as exc:
        return Response(content={"error": str(exc)}, status_code=400)
    except Exception as exc:
        logger.warning("Failed to save refinement provider API key for %s: %s", provider_id, exc)
        return Response(content={"error": "Failed to save provider API key"}, status_code=500)
    return Response(content={"provider": provider_id, "stored": True, "backend": get_secret_backend()})


@delete("/api/refinement/providers/{provider_id:str}/api-key", status_code=200)
async def delete_refinement_provider_api_key(provider_id: str) -> Response:
    """Delete a provider API key from the local secret backend."""
    try:
        if provider_id not in _EXTERNAL_PROVIDERS:
            raise ValueError(f"Unknown external refinement provider: {provider_id}")
        deleted = await asyncio.to_thread(delete_provider_api_key, provider_id)
    except ValueError as exc:
        return Response(content={"error": str(exc)}, status_code=400)
    except Exception as exc:
        logger.warning("Failed to delete refinement provider API key for %s: %s", provider_id, exc)
        return Response(content={"error": "Failed to delete provider API key"}, status_code=500)
    return Response(content={"provider": provider_id, "deleted": deleted, "backend": get_secret_backend()})