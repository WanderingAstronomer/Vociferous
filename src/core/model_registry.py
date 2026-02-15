"""
Model Registry — GGUF/GGML model catalog for Vociferous v4.0.

Replaces CTranslate2 repo references with direct GGUF/GGML URLs.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ASRModel:
    """A whisper.cpp GGML model entry."""
    id: str
    name: str
    filename: str
    repo: str
    size_mb: int
    tier: str  # fast, balanced, quality


@dataclass(frozen=True, slots=True)
class SLMModel:
    """A llama.cpp GGUF model entry."""
    id: str
    name: str
    filename: str
    repo: str
    size_mb: int
    tier: str  # fast, balanced, quality, pro
    quant: str


# --- ASR Models (whisper.cpp GGML) ---

ASR_MODELS: dict[str, ASRModel] = {
    "small-en": ASRModel(
        id="small-en",
        name="Whisper Small English",
        filename="ggml-small.en.bin",
        repo="ggerganov/whisper.cpp",
        size_mb=466,
        tier="fast",
    ),
    "large-v3-turbo-q5_0": ASRModel(
        id="large-v3-turbo-q5_0",
        name="Whisper Large v3 Turbo (Q5)",
        filename="ggml-large-v3-turbo-q5_0.bin",
        repo="ggerganov/whisper.cpp",
        size_mb=547,
        tier="balanced",
    ),
    "large-v3-turbo": ASRModel(
        id="large-v3-turbo",
        name="Whisper Large v3 Turbo",
        filename="ggml-large-v3-turbo.bin",
        repo="ggerganov/whisper.cpp",
        size_mb=1500,
        tier="quality",
    ),
}

# --- SLM Models (llama.cpp GGUF) ---

SLM_MODELS: dict[str, SLMModel] = {
    "qwen1.7b": SLMModel(
        id="qwen1.7b",
        name="Qwen3 1.7B",
        filename="qwen3-1.7b-q4_k_m.gguf",
        repo="Qwen/Qwen3-1.7B-GGUF",
        size_mb=1100,
        tier="fast",
        quant="Q4_K_M",
    ),
    "qwen4b": SLMModel(
        id="qwen4b",
        name="Qwen3 4B",
        filename="qwen3-4b-q4_k_m.gguf",
        repo="Qwen/Qwen3-4B-GGUF",
        size_mb=2500,
        tier="balanced",
        quant="Q4_K_M",
    ),
    "qwen8b": SLMModel(
        id="qwen8b",
        name="Qwen3 8B",
        filename="qwen3-8b-q4_k_m.gguf",
        repo="Qwen/Qwen3-8B-GGUF",
        size_mb=5030,
        tier="quality",
        quant="Q4_K_M",
    ),
    "qwen14b": SLMModel(
        id="qwen14b",
        name="Qwen3 14B",
        filename="qwen3-14b-q4_k_m.gguf",
        repo="Qwen/Qwen3-14B-GGUF",
        size_mb=8500,
        tier="pro",
        quant="Q4_K_M",
    ),
}


def get_asr_model(model_id: str) -> ASRModel | None:
    """Look up an ASR model by ID."""
    return ASR_MODELS.get(model_id)


def get_slm_model(model_id: str) -> SLMModel | None:
    """Look up an SLM model by ID."""
    return SLM_MODELS.get(model_id)


def get_model_catalog() -> dict:
    """Return the full model catalog as serializable dicts."""
    return {
        "asr": {k: _model_to_dict(v) for k, v in ASR_MODELS.items()},
        "slm": {k: _model_to_dict(v) for k, v in SLM_MODELS.items()},
    }


def _model_to_dict(m: ASRModel | SLMModel) -> dict:
    from dataclasses import asdict
    return asdict(m)
