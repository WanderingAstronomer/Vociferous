"""
Transcription module using pywhispercpp (whisper.cpp).

Provides speech-to-text via OpenAI Whisper GGML models loaded through
the whisper.cpp C++ library with Python bindings.
"""

import logging
import re
import time
from inspect import signature
from pathlib import Path

import numpy as np
import webrtcvad
from numpy.typing import NDArray

from src.core.constants import AudioConfig
from src.core.exceptions import EngineError
from src.core.model_registry import ASR_MODELS, get_asr_model
from src.core.resource_manager import ResourceManager
from src.core.settings import VociferousSettings

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


def _trim_trailing_silence(
    audio_data: NDArray[np.int16],
    sample_rate: int = AudioConfig.DEFAULT_SAMPLE_RATE,
    frame_ms: int = 30,
    silence_threshold: float = 0.005,
    min_trailing_silence_ms: int = 300,
) -> NDArray[np.int16]:
    """
    Remove trailing silence from audio using RMS energy detection.

    Walks backward through the audio in fixed-size frames and finds where
    speech energy last exceeded the threshold. Keeps a small tail
    (min_trailing_silence_ms) so whisper sees a clean ending.

    Args:
        audio_data: Raw int16 audio samples.
        sample_rate: Sample rate in Hz.
        frame_ms: Frame size in milliseconds for energy analysis.
        silence_threshold: RMS threshold below which a frame is silence.
        min_trailing_silence_ms: Milliseconds of silence to preserve after
            the last voiced frame so whisper has a clean segment boundary.

    Returns:
        Trimmed audio (or original if no significant silence found).
    """
    frame_size = int(sample_rate * frame_ms / 1000)
    total_frames = len(audio_data) // frame_size

    if total_frames < 2:
        return audio_data

    # Walk backward to find the last frame with speech energy
    last_speech_frame = total_frames - 1
    for i in range(total_frames - 1, -1, -1):
        frame_start = i * frame_size
        frame_end = frame_start + frame_size
        frame = audio_data[frame_start:frame_end].astype(np.float32) / AudioConfig.INT16_SCALE
        rms = np.sqrt(np.mean(frame**2))
        if rms > silence_threshold:
            last_speech_frame = i
            break
    else:
        # Entire recording is silence — return as-is and let whisper handle it
        return audio_data

    # Keep min_trailing_silence_ms of silence after the last voiced frame
    tail_frames = int(min_trailing_silence_ms / frame_ms)
    cut_frame = min(last_speech_frame + tail_frames + 1, total_frames)
    cut_sample = cut_frame * frame_size

    trimmed = audio_data[:cut_sample]
    trimmed_ms = (len(audio_data) - len(trimmed)) / sample_rate * 1000

    if trimmed_ms > 100:  # Only log if we actually trimmed something meaningful
        logger.info(
            "Trimmed %.0fms of trailing silence (kept %d of %d samples)",
            trimmed_ms,
            len(trimmed),
            len(audio_data),
        )

    return trimmed


def _trim_leading_silence(
    audio_data: NDArray[np.int16],
    sample_rate: int = AudioConfig.DEFAULT_SAMPLE_RATE,
    frame_ms: int = 30,
    silence_threshold: float = 0.005,
    min_leading_silence_ms: int = 200,
) -> NDArray[np.int16]:
    """
    Remove leading silence from audio using RMS energy detection.

    Walks forward through the audio in fixed-size frames and finds where
    speech energy first exceeds the threshold. Keeps a small lead-in
    (min_leading_silence_ms) so whisper sees a clean segment boundary.

    Without this, any silence at the start of a recording (e.g. the user
    pausing before speaking, or key-press skip not being long enough)
    gives whisper empty frames to hallucinate on.

    Args:
        audio_data: Raw int16 audio samples.
        sample_rate: Sample rate in Hz.
        frame_ms: Frame size in milliseconds for energy analysis.
        silence_threshold: RMS threshold below which a frame is silence.
        min_leading_silence_ms: Milliseconds of silence to preserve before
            the first voiced frame so whisper has a clean segment boundary.

    Returns:
        Trimmed audio (or original if no significant silence found).
    """
    frame_size = int(sample_rate * frame_ms / 1000)
    total_frames = len(audio_data) // frame_size

    if total_frames < 2:
        return audio_data

    # Walk forward to find the first frame with speech energy
    first_speech_frame = 0
    for i in range(total_frames):
        frame_start = i * frame_size
        frame_end = frame_start + frame_size
        frame = audio_data[frame_start:frame_end].astype(np.float32) / AudioConfig.INT16_SCALE
        rms = np.sqrt(np.mean(frame**2))
        if rms > silence_threshold:
            first_speech_frame = i
            break
    else:
        # Entire recording is silence — return as-is
        return audio_data

    # Keep min_leading_silence_ms of silence before the first voiced frame
    lead_frames = int(min_leading_silence_ms / frame_ms)
    cut_frame = max(first_speech_frame - lead_frames, 0)
    cut_sample = cut_frame * frame_size

    trimmed = audio_data[cut_sample:]
    trimmed_ms = cut_sample / sample_rate * 1000

    if trimmed_ms > 100:  # Only log if we actually trimmed something meaningful
        logger.info(
            "Trimmed %.0fms of leading silence (kept %d of %d samples)",
            trimmed_ms,
            len(trimmed),
            len(audio_data),
        )

    return trimmed


def _strip_internal_silence(
    audio_data: NDArray[np.int16],
    sample_rate: int = AudioConfig.DEFAULT_SAMPLE_RATE,
    frame_ms: int = 30,
    vad_aggressiveness: int = 3,
    pad_frames: int = 5,
    min_silence_ms: int = 400,
) -> NDArray[np.int16]:
    """
    Remove long internal silence from audio using WebRTC VAD.

    Whisper hallucinations (repeated phrases, phantom "thank you") are
    caused by feeding it silent audio frames.  This function classifies
    each frame as speech/non-speech using webrtcvad and collapses any
    silent gap longer than *min_silence_ms* down to a short splice pad.

    Short pauses (< min_silence_ms) are preserved unchanged so that
    natural phrasing and sentence boundaries remain intact.

    Args:
        audio_data: Raw int16 audio samples (mono, 16 kHz).
        sample_rate: Sample rate in Hz.
        frame_ms: Frame duration for VAD analysis (10, 20, or 30).
        vad_aggressiveness: WebRTC VAD aggressiveness 0-3.
        pad_frames: Number of silent frames to keep around each speech
            segment so whisper sees clean boundaries.
        min_silence_ms: Silence gaps shorter than this are left untouched
            (preserves natural pauses).

    Returns:
        Audio with long silence gaps collapsed.
    """
    frame_size = int(sample_rate * frame_ms / 1000)
    total_frames = len(audio_data) // frame_size

    if total_frames < 3:
        return audio_data

    vad = webrtcvad.Vad(vad_aggressiveness)

    # Classify every frame
    is_speech: list[bool] = []
    for i in range(total_frames):
        start = i * frame_size
        end = start + frame_size
        frame_bytes = audio_data[start:end].tobytes()
        try:
            is_speech.append(vad.is_speech(frame_bytes, sample_rate))
        except Exception:
            is_speech.append(True)  # Fail-open: treat unknown as speech

    # Find contiguous silent runs
    min_silence_frames = int(min_silence_ms / frame_ms)
    keep_mask = [True] * total_frames

    i = 0
    stripped_total_ms = 0
    while i < total_frames:
        if not is_speech[i]:
            # Scan ahead for run length
            run_start = i
            while i < total_frames and not is_speech[i]:
                i += 1
            run_len = i - run_start

            if run_len >= min_silence_frames:
                # This is a long silence gap — collapse it.
                # Keep pad_frames at each end (if available) and discard the rest.
                for j in range(run_start, run_start + run_len):
                    frames_from_start = j - run_start
                    frames_from_end = (run_start + run_len - 1) - j
                    if frames_from_start >= pad_frames and frames_from_end >= pad_frames:
                        keep_mask[j] = False

                discarded = sum(1 for j in range(run_start, run_start + run_len) if not keep_mask[j])
                stripped_total_ms += discarded * frame_ms
        else:
            i += 1

    if stripped_total_ms == 0:
        return audio_data

    # Build output from kept frames
    kept_chunks: list[NDArray[np.int16]] = []
    for i in range(total_frames):
        if keep_mask[i]:
            start = i * frame_size
            end = start + frame_size
            kept_chunks.append(audio_data[start:end])

    # Append any leftover samples beyond the last full frame
    leftover_start = total_frames * frame_size
    if leftover_start < len(audio_data):
        kept_chunks.append(audio_data[leftover_start:])

    result = np.concatenate(kept_chunks)

    logger.info(
        "Stripped %.0fms of internal silence (%d -> %d samples, %.1f%% removed)",
        stripped_total_ms,
        len(audio_data),
        len(result),
        (1 - len(result) / len(audio_data)) * 100,
    )

    return result


def _is_effective_silence(
    audio_data: NDArray[np.int16],
    sample_rate: int = AudioConfig.DEFAULT_SAMPLE_RATE,
    frame_ms: int = 30,
    vad_aggressiveness: int = 3,
    min_speech_frames: int = 2,
    rms_threshold: float = 0.003,
    peak_threshold: float = 0.02,
) -> bool:
    """Return True when audio is effectively silent.

    Uses a hybrid check:
    1) Fast energy gate (RMS + peak) to reject obvious silence/noise floor.
    2) WebRTC VAD frame count for low-amplitude edge cases.
    """
    if audio_data.size == 0:
        return True

    audio_float = audio_data.astype(np.float32) / AudioConfig.INT16_SCALE
    rms = float(np.sqrt(np.mean(audio_float**2)))
    peak = float(np.max(np.abs(audio_float)))

    if rms < rms_threshold and peak < peak_threshold:
        return True

    frame_size = int(sample_rate * frame_ms / 1000)
    total_frames = len(audio_data) // frame_size
    if total_frames == 0:
        return True

    vad = webrtcvad.Vad(vad_aggressiveness)
    speech_frames = 0

    for i in range(total_frames):
        start = i * frame_size
        end = start + frame_size
        frame = audio_data[start:end]
        try:
            if vad.is_speech(frame.tobytes(), sample_rate):
                speech_frames += 1
                if speech_frames >= min_speech_frames:
                    return False
        except Exception:
            # If VAD fails on a frame, do not hard-fail transcription.
            continue

    return True


def transcribe(
    audio_data: NDArray[np.int16] | None,
    settings: VociferousSettings,
    local_model=None,
) -> tuple[str, int]:
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
        local_model = create_local_model(settings)

    language = settings.model.language or "en"

    # ── Audio pre-processing: strip silence before whisper sees it ──
    # Order matters: leading → internal → trailing.
    # Each step logs what it removed for diagnostics.

    # 1. Clip leading silence (user paused before speaking, key-press
    #    skip was too short, etc.).
    audio_data = _trim_leading_silence(audio_data)

    # 2. Collapse internal silence gaps > 400ms to short splice pads.
    #    Prevents whisper from hallucinating on mid-recording pauses.
    audio_data = _strip_internal_silence(audio_data)

    # 3. Clip trailing silence ("thank you", "thanks for watching"
    #    hallucinations on silent frames at the end).
    audio_data = _trim_trailing_silence(audio_data)

    # 4. Explicit silence guard.  If the recording contains no effective speech,
    #    do not call whisper at all (prevents silent hallucinations like
    #    "thank you"/"thanks for watching").
    if _is_effective_silence(audio_data):
        logger.info("Detected raw silence after pre-processing; skipping transcription")
        return "", 0

    # Convert int16 → float32 (whisper.cpp expects float32 in [-1, 1])
    try:
        audio_float: NDArray[np.float32] = audio_data.astype(np.float32) / AudioConfig.INT16_SCALE

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

        transcription = "".join(seg.text for seg in segments).strip()

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

    # Ensure a space after sentence-ending punctuation (. ! ? or ellipsis)
    # when immediately followed by a letter.  Protects decimals (3.14)
    # because digits don't match [A-Za-z].
    result = re.sub(r"([.!?]+)([A-Za-z])", r"\1 \2", result)

    # Ensure a space after commas when immediately followed by a letter.
    # Whisper frequently outputs "hello,world" or "yes,but" without the space.
    # Protects numbers like "1,000" because digits don't match [A-Za-z].
    result = re.sub(r",([A-Za-z])", r", \1", result)

    # Same treatment for semicolons and colons followed by a letter.
    result = re.sub(r";([A-Za-z])", r"; \1", result)
    result = re.sub(r":([A-Za-z])", r": \1", result)

    if settings.output.add_trailing_space:
        result += " "

    return result
