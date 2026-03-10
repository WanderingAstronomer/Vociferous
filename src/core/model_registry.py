"""
Model Registry — CTranslate2 model catalog for Vociferous v5.0.

All ASR models are CTranslate2-format Whisper directories (faster-whisper compatible).
All SLM models are CTranslate2-format Generator directories.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ASRModel:
    """A CTranslate2 Whisper model entry (directory-based)."""

    id: str
    name: str
    repo: str
    size_mb: int
    tier: str  # fast, balanced, quality
    # The primary model binary inside the CT2 directory, used for
    # existence checks. For CT2 Whisper this is always "model.bin".
    model_file: str = "model.bin"
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class SLMModel:
    """A CTranslate2 Generator model entry (directory-based)."""

    id: str
    name: str
    repo: str
    size_mb: int
    tier: str  # fast, balanced, quality, pro
    quant: str
    # The primary model binary inside the CT2 directory.
    model_file: str = "model.bin"
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class VADModel:
    """A Voice Activity Detection ONNX model entry."""

    id: str
    name: str
    filename: str
    repo: str
    size_mb: int
    sha256: str | None = None


# --- ASR Models (CTranslate2 Whisper — faster-whisper compatible) ---
#
# These are pre-converted CT2 directories downloaded via snapshot_download().
# The repo IS the model directory — no single-file download needed.

ASR_MODELS: dict[str, ASRModel] = {
    "large-v3-turbo-int8": ASRModel(
        id="large-v3-turbo-int8",
        name="Whisper Large v3 Turbo (INT8)",
        repo="Zoont/faster-whisper-large-v3-turbo-int8-ct2",
        size_mb=780,
        tier="fast",
    ),
    "large-v3-turbo": ASRModel(
        id="large-v3-turbo",
        name="Whisper Large v3 Turbo",
        repo="deepdml/faster-whisper-large-v3-turbo-ct2",
        size_mb=1547,
        tier="balanced",
    ),
    "large-v3": ASRModel(
        id="large-v3",
        name="Whisper Large v3",
        repo="Systran/faster-whisper-large-v3",
        size_mb=2948,
        tier="quality",
    ),
}

# --- SLM Models (CTranslate2 Generator — Qwen3) ---
#
# Pre-converted CT2 directories. Downloaded via snapshot_download().

SLM_MODELS: dict[str, SLMModel] = {
    "qwen4b": SLMModel(
        id="qwen4b",
        name="Qwen3 4B",
        repo="jncraton/Qwen3-4B-ct2-int8",
        size_mb=3858,
        tier="fast",
        quant="int8",
    ),
    "qwen8b": SLMModel(
        id="qwen8b",
        name="Qwen3 8B",
        repo="ctranslate2-4you/Qwen3-8B-ct2-AWQ",
        size_mb=5835,
        tier="quality",
        quant="awq",
    ),
    "qwen14b": SLMModel(
        id="qwen14b",
        name="Qwen3 14B",
        repo="ctranslate2-4you/Qwen3-14B-ct2-AWQ",
        size_mb=9534,
        tier="pro",
        quant="awq",
    ),
}


# --- VAD Models (ONNX) ---

SILERO_VAD = VADModel(
    id="silero_vad",
    name="Silero VAD v5",
    filename="silero_vad.onnx",
    repo="deepghs/silero-vad-onnx",
    size_mb=2,
    sha256="2623a2953f6ff3d2c1e61740c6cdb7168133479b267dfef114a4a3cc5bdd788f",
)


def get_asr_model(model_id: str) -> ASRModel | None:
    """Look up an ASR model by ID."""
    return ASR_MODELS.get(model_id)


def get_slm_model(model_id: str) -> SLMModel | None:
    """Look up an SLM model by ID."""
    return SLM_MODELS.get(model_id)


def get_smallest_slm_id() -> str:
    """Return the ID of the smallest SLM model (by size_mb)."""
    return min(SLM_MODELS, key=lambda k: SLM_MODELS[k].size_mb)


def get_model_catalog() -> dict:
    """Return the full model catalog as serializable dicts."""
    return {
        "asr": {k: _model_to_dict(v) for k, v in ASR_MODELS.items()},
        "slm": {k: _model_to_dict(v) for k, v in SLM_MODELS.items()},
    }


def _model_to_dict(m: ASRModel | SLMModel) -> dict:
    from dataclasses import asdict

    return asdict(m)
