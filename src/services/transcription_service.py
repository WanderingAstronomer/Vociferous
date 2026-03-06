"""
Transcription module using pywhispercpp (whisper.cpp).

Provides speech-to-text via OpenAI Whisper GGML models loaded through
the whisper.cpp C++ library with Python bindings.
"""

from __future__ import annotations

import logging
import re
import time
from inspect import signature
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from src.core.constants import AudioConfig
from src.core.exceptions import EngineError
from src.core.model_registry import ASR_MODELS, get_asr_model
from src.core.resource_manager import ResourceManager
from src.core.settings import VociferousSettings

if TYPE_CHECKING:
    from src.services.audio_pipeline import AudioPipeline

logger = logging.getLogger(__name__)


def _resolve_model_path(settings: VociferousSettings) -> Path:
    """Resolve the filesystem path to the currently configured GGML model file."""
    model_id = settings.model.model
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


def create_local_model(settings: VociferousSettings):
    """
    Create and return a pywhispercpp Model instance.

    Loads the GGML model file from the cache directory.
    """
    from pywhispercpp.model import Model

    model_path = _resolve_model_path(settings)
    n_threads = settings.model.n_threads
    device_pref = (settings.model.device or "auto").strip().lower()
    logger.info(
        "Loading whisper.cpp model from %s (n_threads=%d, device=%s)...",
        model_path,
        n_threads,
        device_pref,
    )

    start = time.perf_counter()

    try:
        init_kwargs: dict[str, object] = {
            "n_threads": n_threads,
            "print_realtime": False,
            "print_progress": False,
            # ── Anti-hallucination / anti-repetition settings ──
            # Reduce max context tokens fed back to decoder. Default 16384
            # causes the model to fixate on its own prior output and loop.
            # 64 retains enough context for coherent output without looping.
            "n_max_text_ctx": 64,
            # Raise entropy threshold so repetitive/low-entropy segments get
            # rejected and re-sampled at higher temperature (default 2.4).
            "entropy_thold": 2.8,
            # ── Break the feedback loop ──
            # Prevent the decoder from using its own prior output as context
            # for subsequent 30-second chunks. This is THE critical defense:
            # without it, hallucinated text on a silent chunk gets fed back
            # as prompt for the next chunk, priming the decoder to repeat
            # the same garbage. For a dictation app, cross-chunk context
            # coherence is not worth the catastrophic failure mode.
            "no_context": True,
            # Lower no-speech threshold (default 0.6). Segments where
            # whisper's own model thinks prob(no_speech) > 0.5 get
            # suppressed at the decoder level — before they ever become text.
            "no_speech_thold": 0.5,
        }

        # params_sampling_strategy is a named __init__ arg, not a **params kwarg.
        # 1 = BEAM_SEARCH — better decoding quality than greedy.
        constructor_kwargs: dict[str, object] = {
            "params_sampling_strategy": 1,
        }

        # beam_search config — only meaningful with beam search strategy.
        whisper_params: dict[str, object] = {
            "beam_search": {"beam_size": 5, "patience": -1.0},
        }

        try:
            supported_kwargs = set(signature(Model.__init__).parameters.keys())
        except Exception:
            supported_kwargs = set()

        if device_pref in {"cpu", "gpu"} and supported_kwargs:
            if device_pref == "cpu" and "no_gpu" in supported_kwargs:
                init_kwargs["no_gpu"] = True
            elif device_pref == "gpu" and "use_gpu" in supported_kwargs:
                init_kwargs["use_gpu"] = True
            elif device_pref == "gpu" and "no_gpu" in supported_kwargs:
                init_kwargs["no_gpu"] = False
            else:
                logger.info(
                    "Device preference '%s' requested but pywhispercpp does not expose a matching init flag; using default backend selection.",
                    device_pref,
                )

        # Merge constructor-level args (positional/keyword params of __init__)
        # and whisper params (**params kwargs) into init_kwargs.
        # Only include constructor kwargs the signature actually accepts.
        for k, v in constructor_kwargs.items():
            if k in supported_kwargs:
                init_kwargs[k] = v
            else:
                logger.debug("Skipping unsupported constructor arg: %s", k)

        # Whisper params go through _set_params → setattr on the C struct.
        # Probe each one against the PARAMS_SCHEMA and skip if the C binding
        # doesn't actually expose the attribute (schema/binding mismatches).
        try:
            from pywhispercpp.constants import PARAMS_SCHEMA

            valid_params = set(PARAMS_SCHEMA.keys())
        except Exception:
            valid_params = set()

        for k, v in whisper_params.items():
            if not valid_params or k in valid_params:
                init_kwargs[k] = v
            else:
                logger.debug("Skipping unsupported whisper param: %s", k)

        model = Model(str(model_path), **init_kwargs)
    except Exception as e:
        raise EngineError(f"Failed to load whisper.cpp model: {e}") from e

    elapsed = time.perf_counter() - start
    logger.info("Whisper model loaded in %.2fs", elapsed)

    return model


def transcribe(
    audio_data: NDArray[np.int16] | None,
    settings: VociferousSettings,
    local_model=None,
    audio_pipeline: AudioPipeline | None = None,
) -> tuple[str, int]:
    """
    Transcribe audio data to text using pywhispercpp.

    Runs the AudioPipeline (normalize → highpass → gate → Silero VAD) to
    strip silence and extract speech, then feeds clean float32 to whisper.

    Args:
        audio_data: Raw audio samples (int16, 16kHz mono).
        settings: Current application settings.
        local_model: A pywhispercpp.Model instance (created if None).
        audio_pipeline: Reusable AudioPipeline instance (created if None).

    Returns:
        Tuple of (transcription_text, speech_duration_ms).
    """
    if audio_data is None or len(audio_data) == 0:
        return "", 0

    if local_model is None:
        local_model = create_local_model(settings)

    language = settings.model.language or "en"

    # ── Audio pre-processing: Silero VAD pipeline ──
    # Replace the old four-function gauntlet (leading trim, internal strip,
    # trailing trim, silence guard) with a single neural VAD pass that
    # produces clean float32 speech or None.
    if audio_pipeline is None:
        from src.services.audio_pipeline import AudioPipeline

        audio_pipeline = AudioPipeline(sample_rate=AudioConfig.DEFAULT_SAMPLE_RATE)

    clean_audio = audio_pipeline.process(audio_data, sample_rate=AudioConfig.DEFAULT_SAMPLE_RATE)

    if clean_audio is None:
        logger.info("AudioPipeline detected no speech; skipping transcription")
        return "", 0

    # Pipeline already returns float32 in [-1, 1] — feed directly to whisper
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

        # pywhispercpp transcribe returns a list of Segment objects.
        # NOTE: initial_prompt is intentionally NOT passed here.
        # pywhispercpp 1.4.1 has a dangling pointer bug: _set_params() stores a
        # raw const char* to the Python str's internal buffer, but that object
        # may be GC'd before whisper_full() dereferences the pointer → SIGSEGV.
        # The setting is preserved in ModelSettings for future use once the
        # pywhispercpp binding is fixed upstream.
        transcribe_kwargs: dict[str, object] = {"language": language}

        segments = local_model.transcribe(audio_float, **transcribe_kwargs)

        transcription = _merge_segment_texts([seg.text for seg in segments])

        # Compute speech duration from segment timestamps.
        # Segment.t0 and .t1 are in centiseconds (10ms units).
        if segments:
            speech_duration_ms = int(segments[-1].t1 * 10) - int(segments[0].t0 * 10)
        else:
            speech_duration_ms = 0

        elapsed = time.perf_counter() - start
        logger.info(
            "Transcription completed in %.2fs (%d segments, speech=%dms)", elapsed, len(segments), speech_duration_ms
        )

        return post_process_transcription(transcription, settings), speech_duration_ms

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
        # We work on the current result, not the original, because a longer
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
