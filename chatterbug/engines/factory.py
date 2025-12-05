from __future__ import annotations

from dataclasses import replace
from typing import Callable

from chatterbug.domain.model import EngineConfig, EngineKind, TranscriptionEngine
from chatterbug.domain.exceptions import ConfigurationError
from .parakeet import ParakeetEngine
from .model_registry import normalize_model_name
from .voxtral import VoxtralEngine
from .whisper_turbo import WhisperTurboEngine

EngineBuilder = Callable[[EngineConfig], TranscriptionEngine]


def build_engine(kind: EngineKind, config: EngineConfig) -> TranscriptionEngine:
    normalized_name = normalize_model_name(kind, config.model_name)
    config = config.model_copy(update={"model_name": normalized_name})
    if kind == "whisper_turbo":
        return WhisperTurboEngine(config)
    if kind == "voxtral":
        return VoxtralEngine(config)
    if kind == "parakeet_rnnt":
        return ParakeetEngine(config)
    raise ConfigurationError(f"Unknown engine kind: {kind}")
