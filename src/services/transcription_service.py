"""
Transcription module using pywhispercpp (whisper.cpp).

Provides speech-to-text via OpenAI Whisper GGML models loaded through
the whisper.cpp C++ library with Python bindings.
"""

import logging
import re
import time
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from src.core.constants import AudioConfig
from src.core.exceptions import EngineError
from src.core.model_registry import ASR_MODELS, get_asr_model
from src.core.resource_manager import ResourceManager
from src.core.settings import get_settings

logger = logging.getLogger(__name__)


def _resolve_model_path() -> Path:
    """Resolve the filesystem path to the currently configured GGML model file."""
    s = get_settings()
    model_id = s.model.model
    asr_model = get_asr_model(model_id)

    if asr_model is None:
        # Fallback to default
        model_id = "large-v3-turbo-q5_0"
        asr_model = ASR_MODELS[model_id]

    cache_dir = ResourceManager.get_user_cache_dir("models")
    model_path = cache_dir / asr_model.filename

    if not model_path.exists():
        raise EngineError(f"ASR model file not found: {model_path}. Run provisioning to download '{model_id}'.")

    return model_path


def create_local_model():
    """
    Create and return a pywhispercpp Model instance.

    Loads the GGML model file from the cache directory.
    """
    from pywhispercpp.model import Model

    model_path = _resolve_model_path()
    s = get_settings()
    n_threads = s.model.n_threads
    logger.info("Loading whisper.cpp model from %s (n_threads=%d)...", model_path, n_threads)

    start = time.perf_counter()

    try:
        model = Model(
            str(model_path),
            n_threads=n_threads,
            print_realtime=False,
            print_progress=False,
        )
    except Exception as e:
        raise EngineError(f"Failed to load whisper.cpp model: {e}") from e

    elapsed = time.perf_counter() - start
    logger.info("Whisper model loaded in %.2fs", elapsed)

    return model


def transcribe(audio_data: NDArray[np.int16] | None, local_model=None) -> tuple[str, int]:
    """
    Transcribe audio data to text using pywhispercpp.

    Converts int16 to float32, runs transcription, then post-processes.

    Args:
        audio_data: Raw audio samples (int16, 16kHz mono).
        local_model: A pywhispercpp.Model instance (created if None).

    Returns:
        Tuple of (transcription_text, speech_duration_ms).
    """
    if audio_data is None or len(audio_data) == 0:
        return "", 0

    if local_model is None:
        local_model = create_local_model()

    s = get_settings()
    language = s.model.language or "en"

    # Convert int16 → float32 (whisper.cpp expects float32 in [-1, 1])
    try:
        audio_float: NDArray[np.float32] = audio_data.astype(np.float32) / AudioConfig.INT16_SCALE

        start = time.perf_counter()

        # pywhispercpp transcribe returns a list of Segment objects
        segments = local_model.transcribe(
            audio_float,
            language=language,
        )

        transcription = "".join(seg.text for seg in segments).strip()

        # Estimate speech duration from audio length (pywhispercpp doesn't
        # expose per-segment timestamps in all versions)
        speech_duration_ms = int(len(audio_data) / AudioConfig.DEFAULT_SAMPLE_RATE * 1000)

        elapsed = time.perf_counter() - start
        logger.info("Transcription completed in %.2fs (%d segments)", elapsed, len(segments))

        return post_process_transcription(transcription), speech_duration_ms

    except Exception as e:
        raise EngineError(f"Transcription failed: {e}") from e


def post_process_transcription(transcription: str | None) -> str:
    """Apply user-configured post-processing.

    Normalises whitespace artefacts from segment joining and applies
    output settings (e.g. trailing space).
    """
    if not transcription:
        return ""

    result = transcription.strip()

    # Ensure a space after sentence-ending punctuation (. ! ? or ellipsis)
    # when immediately followed by a letter.  Protects decimals (3.14)
    # because digits don't match [A-Za-z].
    result = re.sub(r"([.!?]+)([A-Za-z])", r"\1 \2", result)

    s = get_settings()
    if s.output.add_trailing_space:
        result += " "

    return result
