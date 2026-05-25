"""Provider factory + external-provider helpers."""

from __future__ import annotations

from src.core.settings import VociferousSettings
from src.refinement.providers.contracts import RefinementProvider
from src.refinement.providers.local_ct2 import LocalCT2RefinementProvider
from src.refinement.providers.openai_compatible import OpenAICompatibleRefinementProvider


def make_refinement_provider(settings: VociferousSettings) -> RefinementProvider:
    """Create the configured refinement provider."""
    provider = settings.refinement.provider
    if provider == "local_ct2":
        return LocalCT2RefinementProvider(settings)
    if provider in {"lm_studio", "groq"}:
        return OpenAICompatibleRefinementProvider(settings, provider)
    raise ValueError(f"Unknown refinement provider: {provider}")


def list_external_provider_models(settings: VociferousSettings, provider_id: str) -> list[dict[str, object]]:
    """List models for an external OpenAI-compatible provider."""
    if provider_id not in {"lm_studio", "groq"}:
        raise ValueError(f"Provider does not support external model listing: {provider_id}")
    provider = OpenAICompatibleRefinementProvider(settings, provider_id)
    try:
        return provider.list_models()
    finally:
        provider.unload()


def test_external_provider(settings: VociferousSettings, provider_id: str) -> dict[str, object]:
    """Validate an external provider's base URL, auth, and model list endpoint."""
    provider = OpenAICompatibleRefinementProvider(settings, provider_id)
    try:
        models = provider.list_models()
        summary = provider.get_runtime_summary()
        return {"ok": True, "provider": provider_id, "models": models, "runtime": summary}
    finally:
        provider.unload()


__all__ = ["list_external_provider_models", "make_refinement_provider", "test_external_provider"]
