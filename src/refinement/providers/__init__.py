"""Refinement provider package.

Public surface (kept import-compatible with the previous single-file module):
  * ``RefinementProvider`` — Protocol consumed by ``SLMRuntime``.
  * ``ProviderRequestError`` — HTTP-aware error type.
  * ``make_refinement_provider`` — factory used by the composition root.
  * ``list_external_provider_models``, ``test_external_provider`` — used by
    the API layer for provider diagnostics.
  * ``describe_refinement_runtime`` — runtime descriptor used by status/support.
  * ``LocalCT2RefinementProvider``, ``OpenAICompatibleRefinementProvider`` —
    concrete implementations.

Internal modules (not re-exported, but stable for tests inside this package):
  * ``capabilities`` — per-model capability model centralizing reasoning
    suppression, ``reasoning_effort`` value selection, schema forcing, and
    MTP awareness for OpenAI-compatible providers.
  * ``runtime`` — runtime descriptor + API key helpers.
  * ``factory``, ``contracts``, ``local_ct2``, ``openai_compatible`` —
    implementation modules.
"""

from src.refinement.providers.contracts import (
    GenerationRequest,
    GenerationTaskKind,
    ProviderRequestError,
    ReasoningPolicy,
    RefinementProvider,
    ResponseShape,
)
from src.refinement.providers.factory import (
    list_external_provider_models,
    make_refinement_provider,
    test_external_provider,
)
from src.refinement.providers.local_ct2 import LocalCT2RefinementProvider
from src.refinement.providers.openai_compatible import OpenAICompatibleRefinementProvider
from src.refinement.providers.runtime import describe_refinement_runtime

__all__ = [
    "LocalCT2RefinementProvider",
    "OpenAICompatibleRefinementProvider",
    "GenerationRequest",
    "GenerationTaskKind",
    "ProviderRequestError",
    "ReasoningPolicy",
    "RefinementProvider",
    "ResponseShape",
    "describe_refinement_runtime",
    "list_external_provider_models",
    "make_refinement_provider",
    "test_external_provider",
]
