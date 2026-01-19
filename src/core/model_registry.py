from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict


class ModelType(Enum):
    ASR = auto()
    SLM = auto()


@dataclass(frozen=True, slots=True)
class SupportedModel:
    id: str
    name: str
    repo_id: str
    revision: str
    dir_name: str
    quantization: str
    required_vram_mb: int = 0
    source: str = "HuggingFace"
    model_type: ModelType = ModelType.SLM
    prompt_format: str = "chatml"


MODELS: Dict[str, SupportedModel] = {
    "qwen4b": SupportedModel(
        id="qwen4b",
        name="Qwen 3 (4B) - Fast",
        repo_id="Qwen/Qwen3-4B",
        revision="main",
        dir_name="qwen3-4b-ct2",
        quantization="int8",
        required_vram_mb=5500,
        model_type=ModelType.SLM,
    ),
    "qwen8b": SupportedModel(
        id="qwen8b",
        name="Qwen 3 (8B)",
        repo_id="Qwen/Qwen3-8B",
        revision="main",
        dir_name="qwen3-8b-ct2",
        quantization="int8",
        required_vram_mb=9000,
        model_type=ModelType.SLM,
    ),
    "qwen14b": SupportedModel(
        id="qwen14b",
        name="Qwen 3 (14B) - Pro",
        repo_id="Qwen/Qwen3-14B",
        revision="main",
        dir_name="qwen3-14b-ct2",
        quantization="int8",
        required_vram_mb=13500,
        model_type=ModelType.SLM,
    ),
    "daredevil8b": SupportedModel(
        id="daredevil8b",
        name="NeuralDaredevil (8B) - Llama 3",
        repo_id="mlabonne/NeuralDaredevil-8B-abliterated",
        revision="main",
        dir_name="daredevil-8b-ct2",
        quantization="int8",
        required_vram_mb=9000,
        model_type=ModelType.SLM,
        prompt_format="llama3",
    ),
    "josiefied8b": SupportedModel(
        id="josiefied8b",
        name="Josiefied Qwen3 (8B) - Abliterated",
        repo_id="Goekdeniz-Guelmez/Josiefied-Qwen3-8B-abliterated-v1",
        revision="main",
        dir_name="josiefied-qwen3-8b-ct2",
        quantization="int8",
        required_vram_mb=9000,
        model_type=ModelType.SLM,
    ),
}

ASR_MODELS: Dict[str, SupportedModel] = {
    "distil-small-en": SupportedModel(
        id="distil-small-en",
        name="Whisper Distil Small.en (Fastest)",
        repo_id="Systran/faster-distil-whisper-small.en",
        revision="main",
        dir_name="distil-small-en-ct2",
        quantization="float16",
        required_vram_mb=1000,
        model_type=ModelType.ASR,
    ),
    "distil-large-v3": SupportedModel(
        id="distil-large-v3",
        name="Whisper Distil v3 (Balanced)",
        repo_id="SYSTRAN/faster-distil-whisper-large-v3",
        revision="main",
        dir_name="distil-large-v3-ct2",
        quantization="float16",
        required_vram_mb=2100,
        model_type=ModelType.ASR,
    ),
    "large-v3": SupportedModel(
        id="large-v3",
        name="Whisper v3 (High Quality)",
        repo_id="Systran/faster-whisper-large-v3",
        revision="main",
        dir_name="large-v3-ct2",
        quantization="float16",
        required_vram_mb=3200,
        model_type=ModelType.ASR,
    ),
}

DEFAULT_MODEL_ID = "qwen4b"
DEFAULT_ASR_MODEL_ID = "distil-large-v3"
