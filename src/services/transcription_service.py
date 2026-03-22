"""
Transcription module using faster-whisper (CTranslate2 Whisper backend).

Provides speech-to-text via OpenAI Whisper models loaded through
the faster-whisper library, which wraps CTranslate2 for inference.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from src.core.constants import AudioConfig
from src.core.cuda_runtime import detect_cuda_runtime
from src.core.exceptions import EngineError
from src.core.model_registry import ASR_MODELS, get_asr_model
from src.core.resource_manager import ResourceManager
from src.core.settings import VociferousSettings

if TYPE_CHECKING:
    from src.services.audio_pipeline import AudioPipeline

logger = logging.getLogger(__name__)


def _resolve_model_path(settings: VociferousSettings) -> Path:
    """Resolve the filesystem path to the currently configured CT2 Whisper model directory."""
    model_id = settings.model.model
    asr_model = get_asr_model(model_id)

    if asr_model is None:
        # Fallback to default
        model_id = "large-v3-turbo-int8"
        asr_model = ASR_MODELS[model_id]

    cache_dir = ResourceManager.get_user_cache_dir("models")
    # CT2 models are directories named after the repo slug
    local_dir_name = asr_model.repo.split("/")[-1]
    model_dir = cache_dir / local_dir_name

    if not (model_dir / asr_model.model_file).exists():
        raise EngineError(f"ASR model directory not found: {model_dir}. Run provisioning to download '{model_id}'.")

    return model_dir


def create_local_model(settings: VociferousSettings):
    """
    Create and return a faster-whisper WhisperModel instance.

    Loads the CTranslate2-format model directory from the cache.
    faster-whisper wraps ctranslate2 and provides the full transcription
    pipeline: audio preprocessing, tokenization, and segment extraction.
    """
    from faster_whisper import WhisperModel

    model_dir = _resolve_model_path(settings)
    n_threads = settings.model.n_threads
    device_pref = (settings.model.device or "auto").strip().lower()
    cuda_status = detect_cuda_runtime()

    # Resolve the requested device against what CTranslate2 can actually use.
    if device_pref == "gpu":
        if not cuda_status.cuda_available:
            raise EngineError(f"GPU inference requested, but CUDA is not usable: {cuda_status.detail}")
        fw_device = "cuda"
    elif device_pref == "cpu":
        fw_device = "cpu"
    else:
        fw_device = "cuda" if cuda_status.cuda_available else "cpu"
        if fw_device == "cpu":
            if cuda_status.driver_detected:
                logger.warning(
                    "ASR auto device fell back to CPU even though an NVIDIA GPU was detected: %s",
                    cuda_status.detail,
                )
            else:
                logger.info("ASR auto device resolved to CPU: %s", cuda_status.detail)

    # int8 on GPU requires explicit Tensor Core GEMM support and can hang silently
    # without it. float16 on CPU is also bogus, so normalize that to float32.
    raw_compute_type = settings.model.compute_type
    if fw_device == "cuda" and raw_compute_type == "int8":
        compute_type = "float16"
    elif fw_device == "cpu" and raw_compute_type in {"float16", "bfloat16"}:
        compute_type = "float32"
        logger.warning(
            "ASR compute_type %s is not supported on CPU; using float32 instead.",
            raw_compute_type,
        )
    else:
        compute_type = raw_compute_type

    logger.info(
        "Loading faster-whisper model from %s (cpu_threads=%d, device_pref=%s, resolved_device=%s, compute_type=%s, cuda_detail=%s)...",
        model_dir,
        n_threads,
        device_pref,
        fw_device,
        compute_type,
        cuda_status.detail,
    )

    start = time.perf_counter()

    try:
        model = WhisperModel(
            str(model_dir),
            device=fw_device,
            cpu_threads=n_threads,
            compute_type=compute_type,
            local_files_only=True,
        )
    except Exception as e:
        raise EngineError(f"Failed to load faster-whisper model: {e}") from e

    elapsed = time.perf_counter() - start
    logger.info("Whisper model loaded in %.2fs", elapsed)

    return model


def transcribe(
    audio_data: NDArray[np.int16] | None,
    settings: VociferousSettings,
    local_model=None,
    audio_pipeline: AudioPipeline | None = None,
) -> tuple[str, int, int]:
    """
    Transcribe audio data to text using faster-whisper (CTranslate2 backend).

    Runs the AudioPipeline (normalize → highpass → Silero VAD) to
    strip silence and extract speech, then feeds clean float32 to Whisper.

    Args:
        audio_data: Raw audio samples (int16, 16kHz mono).
        settings: Current application settings.
        local_model: A faster_whisper.WhisperModel instance (created if None).
        audio_pipeline: Reusable AudioPipeline instance (created if None).

    Returns:
        Tuple of (transcription_text, speech_duration_ms, transcription_time_ms).
    """
    if audio_data is None or len(audio_data) == 0:
        return "", 0, 0

    if local_model is None:
        local_model = create_local_model(settings)

    language = settings.model.language or "en"

    # ── Audio pre-processing: Silero VAD pipeline ──
    if audio_pipeline is None:
        from src.services.audio_pipeline import AudioPipeline

        audio_pipeline = AudioPipeline(sample_rate=AudioConfig.DEFAULT_SAMPLE_RATE)

    clean_audio = audio_pipeline.process(audio_data, sample_rate=AudioConfig.DEFAULT_SAMPLE_RATE)

    if clean_audio is None:
        logger.info("AudioPipeline detected no speech; skipping transcription")
        return "", 0, 0

    try:
        audio_float: NDArray[np.float32] = clean_audio

        start = time.perf_counter()
        estimated_audio_seconds = len(audio_data) / AudioConfig.DEFAULT_SAMPLE_RATE
        logger.info(
            "Transcription started (language=%s, samples=%d, audio=%.2fs)",
            language,
            len(audio_data),
            estimated_audio_seconds,
        )

        # Flush the log so we know exactly how far we got if something crashes.
        for handler in logging.getLogger().handlers:
            handler.flush()

        # ── faster-whisper inference ──
        initial_prompt = settings.model.initial_prompt or None

        segments_iter, _ = local_model.transcribe(
            audio_float,
            language=language,
            initial_prompt=initial_prompt,
            beam_size=5,
            patience=1.0,
            repetition_penalty=1.0,
            no_speech_threshold=0.5,
            condition_on_previous_text=False,
        )

        # Consume the segment iterator and extract text
        segment_texts: list[str] = []
        total_duration_ms = 0
        for seg in segments_iter:
            segment_texts.append(seg.text)
            total_duration_ms = int(seg.end * 1000)

        transcription = _merge_segment_texts(segment_texts)

        # Compute speech duration from the last segment end
        speech_duration_ms = total_duration_ms if total_duration_ms > 0 else 0

        elapsed = time.perf_counter() - start
        transcription_time_ms = int(elapsed * 1000)
        logger.info(
            "Transcription completed in %.2fs (%d segments, speech=%dms)",
            elapsed,
            len(segment_texts),
            speech_duration_ms,
        )

        return post_process_transcription(transcription, settings), speech_duration_ms, transcription_time_ms

    except Exception as e:
        raise EngineError(f"Transcription failed: {e}") from e


def _collapse_repeated_phrases(text: str, min_phrase_words: int = 3, max_phrase_words: int = 30) -> str:
    """
    Detect and collapse repeated phrases in transcription output.

    Whisper (especially v3) sometimes gets stuck in a loop, emitting the same
    phrase or sentence 5-50+ times consecutively.  This function detects any
    n-gram (from *min_phrase_words* to *max_phrase_words* words) that repeats
    3 or more times in a row and collapses it to a single occurrence.

    This is a safety net — the beam-search / entropy-threshold parameters on
    the model should catch most cases, but when they don't, this prevents
    the output from being unusable.
    """
    if not text:
        return text

    words = text.split()
    if len(words) < min_phrase_words * 3:
        return text  # Too short to contain meaningful repetition

    result = text
    # Try phrase lengths from longest to shortest (greedy — catch big loops first)
    for phrase_len in range(min(max_phrase_words, len(words) // 3), min_phrase_words - 1, -1):
        # Build a regex that matches the phrase repeated 3+ times
        # Applying iteratively on the current result — not the original — because a longer
        # match may have already cleaned part of it.
        result_words = result.split()
        i = 0
        cleaned_words: list[str] = []
        while i < len(result_words):
            # Check if the next phrase_len words repeat at least twice more
            if i + phrase_len * 3 <= len(result_words):
                phrase = result_words[i : i + phrase_len]
                repeats = 1
                j = i + phrase_len
                while j + phrase_len <= len(result_words):
                    candidate = result_words[j : j + phrase_len]
                    if candidate == phrase:
                        repeats += 1
                        j += phrase_len
                    else:
                        break
                if repeats >= 3:
                    # Collapse: keep one occurrence, skip the rest
                    logger.warning(
                        "Collapsed %d consecutive repetitions of %d-word phrase: '%s'",
                        repeats,
                        phrase_len,
                        " ".join(phrase[:8]) + ("..." if phrase_len > 8 else ""),
                    )
                    cleaned_words.extend(phrase)
                    i = j
                    continue
            cleaned_words.append(result_words[i])
            i += 1
        result = " ".join(cleaned_words)

    return result


def _needs_boundary_space(left_text: str, right_text: str) -> bool:
    """Return True when a single separator space should be inserted."""
    if not left_text or not right_text:
        return False

    left_char = left_text[-1]
    right_char = right_text[0]

    if left_char.isspace() or right_char.isspace():
        return False

    if left_char.isalnum() and right_char.isalnum():
        return True

    if left_char in ".!?;:," and right_char.isalnum():
        return True

    return False


def _merge_segment_texts(segment_texts: list[str]) -> str:
    """Merge ASR segment text with boundary-aware whitespace handling."""
    merged = ""

    for chunk in segment_texts:
        if not chunk:
            continue

        if not merged:
            merged = chunk
            continue

        if _needs_boundary_space(merged, chunk):
            merged += " " + chunk.lstrip()
        else:
            merged += chunk

    return merged.strip()


def _normalize_sentence_casing(text: str) -> str:
    """Capitalize the first alphabetical character of each sentence."""
    if not text:
        return text

    chars = list(text)
    should_capitalize = True

    for i, char in enumerate(chars):
        if char.isalpha():
            if should_capitalize:
                chars[i] = char.upper()
                should_capitalize = False
            continue

        if char in ".!?":
            should_capitalize = True

    return "".join(chars)


def post_process_transcription(
    transcription: str | None,
    settings: VociferousSettings,
) -> str:
    """Apply user-configured post-processing.

    Normalises whitespace artefacts from segment joining and applies
    output settings (e.g. trailing space).
    """
    if not transcription:
        return ""

    result = transcription.strip()

    # Collapse repeated phrases (whisper hallucination safety net)
    result = _collapse_repeated_phrases(result)

    # Deterministic whitespace normalization.
    result = re.sub(r"\s+", " ", result).strip()

    # Remove spacing before punctuation marks.
    result = re.sub(r"\s+([,.;:!?])", r"\1", result)

    # Ensure spacing after punctuation when followed by letters.
    # Keep decimal numbers intact (e.g., 3.14).
    result = re.sub(r"(\.\.\.)([A-Za-z])", r"\1 \2", result)
    result = re.sub(r"(?<!\d)\.([A-Za-z])", r". \1", result)
    result = re.sub(r"([!?;:,])([A-Za-z])", r"\1 \2", result)

    # Deterministic sentence-start capitalization.
    result = _normalize_sentence_casing(result)

    if settings.output.add_trailing_space:
        result += " "

    return result
