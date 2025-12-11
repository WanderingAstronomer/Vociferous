from __future__ import annotations

from typing import Dict

from vociferous.domain.model import EngineKind

# Canary-Qwen (GPU-only)
DEFAULT_CANARY_MODEL = "nvidia/canary-qwen-2.5b"
CANARY_MODELS: Dict[str, str] = {
    DEFAULT_CANARY_MODEL: DEFAULT_CANARY_MODEL,
}

# Whisper Turbo (CPU-friendly fallback)
DEFAULT_WHISPER_MODEL = "deepdml/faster-whisper-large-v3-turbo-ct2"
WHISPER_MODELS: Dict[str, str] = {
    DEFAULT_WHISPER_MODEL: DEFAULT_WHISPER_MODEL,
    "large-v3-turbo": DEFAULT_WHISPER_MODEL,
    "large-v3": "Systran/faster-whisper-large-v3",
    "medium": "Systran/faster-whisper-medium",
    "small": "Systran/faster-whisper-small",
}


def _is_invalid_canary_model(name: str, default: str | None) -> bool:
    if not name:
        return True
    if name in CANARY_MODELS or str(name).startswith("nvidia/canary"):
        return False
    if default and name == default:
        return False
    return True


def _is_invalid_whisper_model(name: str, default: str | None) -> bool:
    if not name:
        return True
    if name in WHISPER_MODELS or str(name).lower() in WHISPER_MODELS:
        return False
    if default and name == default:
        return False
    # Allow Systran/deepdml HF model names
    if str(name).startswith(("Systran/faster-whisper", "deepdml/faster-whisper")):
        return False
    return True


_DEFAULTS = {
    "canary_qwen": DEFAULT_CANARY_MODEL,
    "whisper_turbo": DEFAULT_WHISPER_MODEL,
}

_ALIASES: Dict[str, Dict[str, str]] = {
    "canary_qwen": {
        "default": DEFAULT_CANARY_MODEL,
    },
    "whisper_turbo": {
        "default": DEFAULT_WHISPER_MODEL,
        "large-v3-turbo": DEFAULT_WHISPER_MODEL,
        "large-v3": "Systran/faster-whisper-large-v3",
        "medium": "Systran/faster-whisper-medium",
        "small": "Systran/faster-whisper-small",
    },
}


def normalize_model_name(kind: str, model_name: str | None) -> str:
    """Normalize and validate model names for the engine.

    Args:
        kind: Engine kind (e.g., "canary_qwen", "whisper_turbo")
        model_name: User-provided model name or alias

    Returns:
        Canonical model name

    Raises:
        ValueError: If model name is invalid for the engine
    """
    kind_lower = kind.lower()
    
    if kind_lower not in ("canary_qwen", "whisper_turbo"):
        raise ValueError(f"Unknown engine kind: {kind}")
    
    # If no model specified, use default
    if not model_name:
        return _DEFAULTS[kind_lower]
    
    model_lower = model_name.lower()
    
    # Check aliases first
    aliases = _ALIASES.get(kind_lower, {})
    if model_lower in aliases:
        return aliases[model_lower]
    
    # Validate against allowed models
    if kind_lower == "canary_qwen":
        if _is_invalid_canary_model(model_name, _DEFAULTS.get(kind_lower)):
            raise ValueError(
                f"Invalid model '{model_name}' for {kind}. "
                f"Allowed: {list(CANARY_MODELS.keys())}"
            )
        return model_name
    
    if kind_lower == "whisper_turbo":
        if _is_invalid_whisper_model(model_name, _DEFAULTS.get(kind_lower)):
            raise ValueError(
                f"Invalid model '{model_name}' for {kind}. "
                f"Allowed: {list(WHISPER_MODELS.keys())}"
            )
        return model_name
    
    raise ValueError(f"Unknown engine kind: {kind}")
