"""
Transcription module using faster-whisper.

Provides speech-to-text via OpenAI Whisper (CTranslate2 backend).
"""

import logging
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from src.core_runtime.constants import AudioConfig
from src.core.config_manager import ConfigManager
from src.core.resource_manager import ResourceManager
from src.core.model_registry import ASR_MODELS, DEFAULT_ASR_MODEL_ID
from src.core.exceptions import ModelLoadError, TranscriptionError

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


def create_local_model() -> "WhisperModel":
    """
    Create and configure a faster-whisper model instance.

    Tries CUDA first, falls back to CPU on failure.
    Loads from cache when available to avoid HTTP requests.
    """
    from faster_whisper import WhisperModel

    logger.info("Loading Whisper model...")

    model_options = ConfigManager.get_config_section("model_options")
    model_id: str = model_options.get("model", DEFAULT_ASR_MODEL_ID)

    # Resolve repo_id from registry
    asr_model = ASR_MODELS.get(model_id, ASR_MODELS[DEFAULT_ASR_MODEL_ID])
    model_repo = asr_model.repo_id

    device: str = model_options.get("device", "auto")
    compute_type: str = model_options.get("compute_type", "float16")

    # Use ResourceManager to get authoritative cache location
    download_root = str(ResourceManager.get_user_cache_dir("models"))

    # Handle device selection using match/case
    match (device, compute_type):
        case ("auto", _):
            device = "cuda"  # Try CUDA first, faster-whisper will fall back to CPU
        case ("cpu", "float16"):
            # float16 doesn't work on CPU, downgrade to float32
            compute_type = "float32"
            logger.warning("float16 not supported on CPU, using float32 instead.")
        case (_, "int8"):
            device = "cpu"
            logger.info("Using int8 quantization, forcing CPU.")

    # Try loading from cache first to avoid unnecessary HTTP requests
    model = None
    try:
        # Attempt local-only load (no network)
        model = WhisperModel(
            model_repo,
            device=device,
            compute_type=compute_type,
            local_files_only=True,
            download_root=download_root,
        )
        logger.info(f"Model loaded from cache: {model_repo} on {device}")
    except Exception:
        # Model not in cache, download it
        logger.info(f"Model not cached, downloading {model_repo}...")
        try:
            model = WhisperModel(
                model_repo,
                device=device,
                compute_type=compute_type,
                download_root=download_root,
            )
            logger.info(f"Model downloaded: {model_repo} on {device}")
        except Exception as e:
            logger.warning(f"Error loading model on {device}: {e}")
            logger.info("Falling back to CPU...")
            try:
                model = WhisperModel(
                    model_repo,
                    device="cpu",
                    compute_type="float32",
                    download_root=download_root,
                )  # Force float32 for CPU
                logger.info(f"Model loaded: {model_repo} on CPU")
            except Exception as final_error:
                raise ModelLoadError(
                    f"Failed to load Whisper model {model_repo} on both {device} and CPU.",
                    context={
                        "model": model_repo,
                        "initial_device": device,
                        "initial_error": str(e),
                        "final_error": str(final_error),
                    },
                ) from final_error

    return model


def transcribe(
    audio_data: NDArray[np.int16] | None, local_model: "WhisperModel | None" = None
) -> tuple[str, int]:
    """
    Transcribe audio data to text using faster-whisper.

    Converts int16 to float32, runs VAD-filtered transcription,
    then post-processes the result.

    Returns:
        Tuple of (transcription_text, speech_duration_ms)
        speech_duration_ms is the sum of all speech segments after VAD filtering
    """
    if audio_data is None:
        return "", 0

    if local_model is None:
        local_model = create_local_model()

    model_options = ConfigManager.get_config_section("model_options")
    language: str | None = model_options.get("language", "en") or None
    vad_filter: bool = model_options.get("vad_filter", True)

    # Convert int16 to float32 (required by faster-whisper)
    try:
        audio_float: NDArray[np.float32] = (
            audio_data.astype(np.float32) / AudioConfig.INT16_SCALE
        )

        # Transcribe with VAD for cleaner output
        segments, _ = local_model.transcribe(
            audio=audio_float,
            language=language,
            vad_filter=vad_filter,
        )

        # Combine segments and calculate effective speech duration
        segment_list = list(segments)
        transcription = "".join(segment.text for segment in segment_list).strip()

        # Calculate total speech duration from segments (end - start of each segment)
        speech_duration_seconds = sum(
            segment.end - segment.start for segment in segment_list
        )
        speech_duration_ms = int(speech_duration_seconds * 1000)

        return post_process_transcription(transcription), speech_duration_ms

    except Exception as e:
        raise TranscriptionError(
            f"Transcription failed: {str(e)}",
            context={
                "audio_size_samples": len(audio_data),
                "language": language,
                "model_type": str(type(local_model)),
            },
        ) from e


def post_process_transcription(transcription: str | None) -> str:
    """Apply user-configured post-processing (strip whitespace, add trailing space)."""
    if not transcription:
        return ""

    result = transcription.strip()

    output_options = ConfigManager.get_config_section("output_options")

    if output_options.get("add_trailing_space", True):
        result += " "

    return result
