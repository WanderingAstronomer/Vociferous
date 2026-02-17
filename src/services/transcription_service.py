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


def _strip_internal_silence(
    audio_data: NDArray[np.int16],
    sample_rate: int = AudioConfig.DEFAULT_SAMPLE_RATE,
    frame_ms: int = 30,
    vad_aggressiveness: int = 2,
    pad_frames: int = 5,
    min_silence_ms: int = 600,
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

    # Strip internal silence to prevent whisper hallucinations
    # (repeated phrases, phantom "thank you") on long pauses mid-recording.
    audio_data = _strip_internal_silence(audio_data)

    # Trim trailing silence to prevent whisper hallucinations
    # ("thank you", "thanks for watching", etc.) on silent frames.
    audio_data = _trim_trailing_silence(audio_data)

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
        # Keep parameters compatible with installed pywhispercpp versions.
        segments = local_model.transcribe(
            audio_float,
            language=language,
        )

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

    # Ensure a space after sentence-ending punctuation (. ! ? or ellipsis)
    # when immediately followed by a letter.  Protects decimals (3.14)
    # because digits don't match [A-Za-z].
    result = re.sub(r"([.!?]+)([A-Za-z])", r"\1 \2", result)

    if settings.output.add_trailing_space:
        result += " "

    return result
