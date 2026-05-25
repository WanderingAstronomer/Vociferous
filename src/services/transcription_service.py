"""
Transcription module using faster-whisper (CTranslate2 Whisper backend).

Provides speech-to-text via OpenAI Whisper models loaded through
the faster-whisper library, which wraps CTranslate2 for inference.
"""

from __future__ import annotations

import io
import logging
import os
import time
import wave
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from numpy.typing import NDArray

from src.core.constants import AudioConfig
from src.core.cuda_runtime import CudaRuntimeStatus, detect_cuda_runtime
from src.core.exceptions import EngineError
from src.core.model_registry import ASR_MODELS, get_asr_model
from src.core.resource_manager import ResourceManager
from src.core.settings import VociferousSettings

if TYPE_CHECKING:
    from src.services.audio_pipeline import AudioPipeline

logger = logging.getLogger(__name__)

_EXTERNAL_ASR_PROVIDERS = frozenset({"groq"})


class TranscriptionProviderRequestError(RuntimeError):
    """Raised when an external transcription provider rejects or cannot serve a request."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def describe_asr_runtime(
    settings: VociferousSettings,
    *,
    cuda_status: CudaRuntimeStatus | None = None,
) -> dict[str, object]:
    """Return the resolved ASR runtime choices for support diagnostics."""
    provider_id = settings.model.provider
    if provider_id != "local_faster_whisper":
        provider_settings = getattr(settings.model, provider_id)
        return {
            "provider": provider_id,
            "model_id": provider_settings.model_id,
            "requested_model_id": provider_settings.model_id,
            "language": settings.model.language,
            "device_preference": "external",
            "resolved_device": "external",
            "base_url": provider_settings.base_url,
            "timeout_seconds": provider_settings.timeout_seconds,
            "api_key_env": provider_settings.api_key_env,
            "has_api_key": bool(
                provider_settings.api_key
                or _stored_api_key(provider_id)
                or _api_key_from_env(provider_id, provider_settings.api_key_env)
            ),
            "initial_prompt_enabled": bool(settings.model.initial_prompt),
        }

    status = cuda_status or detect_cuda_runtime()
    device_pref = (settings.model.device or "auto").strip().lower()

    if device_pref == "gpu":
        resolved_device = "cuda" if status.cuda_available else "unavailable"
    elif device_pref == "cpu":
        resolved_device = "cpu"
    else:
        resolved_device = "cuda" if status.cuda_available else "cpu"

    raw_compute_type = settings.model.compute_type
    if resolved_device == "cuda" and raw_compute_type == "int8":
        resolved_compute_type = "float16"
    elif resolved_device == "cpu" and raw_compute_type in {"float16", "bfloat16"}:
        resolved_compute_type = "float32"
    else:
        resolved_compute_type = raw_compute_type

    return {
        "provider": "local_faster_whisper",
        "model_id": settings.model.model,
        "language": settings.model.language,
        "device_preference": device_pref,
        "resolved_device": resolved_device,
        "cpu_threads": settings.model.n_threads,
        "compute_type_requested": raw_compute_type,
        "compute_type_resolved": resolved_compute_type,
        "initial_prompt_enabled": bool(settings.model.initial_prompt),
        "cuda_detail": status.detail,
    }


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
    if settings.model.provider != "local_faster_whisper":
        provider = OpenAICompatibleTranscriptionProvider(settings)
        provider.load()
        return provider

    from faster_whisper import WhisperModel

    model_dir = _resolve_model_path(settings)
    cuda_status = detect_cuda_runtime()
    runtime_summary = describe_asr_runtime(settings, cuda_status=cuda_status)

    # Resolve the requested device against what CTranslate2 can actually use.
    if runtime_summary["resolved_device"] == "unavailable":
        if runtime_summary["device_preference"] == "gpu":
            raise EngineError(f"GPU inference requested, but CUDA is not usable: {cuda_status.detail}")
        raise EngineError(f"ASR runtime is not usable: {cuda_status.detail}")

    fw_device = str(runtime_summary["resolved_device"])
    n_threads = int(runtime_summary["cpu_threads"])
    compute_type = str(runtime_summary["compute_type_resolved"])

    if runtime_summary["device_preference"] == "auto":
        if fw_device == "cpu":
            if cuda_status.driver_detected:
                logger.warning(
                    "ASR auto device fell back to CPU even though an NVIDIA GPU was detected: %s",
                    cuda_status.detail,
                )
            else:
                logger.info("ASR auto device resolved to CPU: %s", cuda_status.detail)

    raw_compute_type = str(runtime_summary["compute_type_requested"])
    if fw_device == "cpu" and compute_type != raw_compute_type:
        logger.warning(
            "ASR compute_type %s is not supported on CPU; using %s instead.",
            raw_compute_type,
            compute_type,
        )

    logger.info(
        "Loading faster-whisper model from %s (model_id=%s, language=%s, cpu_threads=%d, device_pref=%s, resolved_device=%s, compute_type=%s, cuda_detail=%s)...",
        model_dir,
        runtime_summary["model_id"],
        runtime_summary["language"],
        n_threads,
        runtime_summary["device_preference"],
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
        from src.core.engine_status import normalize_engine_error

        raise EngineError(normalize_engine_error(e, model_name=str(runtime_summary["model_id"]))) from e

    elapsed = time.perf_counter() - start
    logger.info("Whisper model loaded in %.2fs", elapsed)

    try:
        setattr(model, "_vociferous_runtime_summary", runtime_summary)
    except Exception:
        logger.debug("Could not attach runtime summary to Whisper model", exc_info=True)

    return model


class OpenAICompatibleTranscriptionProvider:
    """OpenAI-compatible speech-to-text provider for Groq."""

    def __init__(self, settings: VociferousSettings) -> None:
        provider_id = settings.model.provider
        if provider_id not in _EXTERNAL_ASR_PROVIDERS:
            raise ValueError(f"Unknown external transcription provider: {provider_id}")
        self._settings = settings
        self._provider_id = provider_id
        self._provider_settings = getattr(settings.model, provider_id)
        self._client: Any | None = None
        self._runtime_summary = describe_asr_runtime(settings)

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def _provider_label(self) -> str:
        return "Groq"

    @property
    def _api_key(self) -> str | None:
        from src.core.secret_store import normalize_provider_api_key

        return (
            normalize_provider_api_key(self._provider_id, self._provider_settings.api_key)
            or _stored_api_key(self._provider_id)
            or _api_key_from_env(self._provider_id, self._provider_settings.api_key_env)
        )

    def load(self) -> None:
        if not self._provider_settings.base_url.strip():
            raise ValueError(f"No base URL configured for {self._provider_label} transcription.")
        if not self._provider_settings.model_id.strip():
            raise ValueError(f"No model configured for {self._provider_label} transcription.")
        if self._provider_id == "groq":
            from src.core.secret_store import validate_provider_api_key

            try:
                validate_provider_api_key(self._provider_id, self._api_key)
            except ValueError as exc:
                if not self._api_key:
                    raise ValueError(
                        "Groq API key is not configured. Set GROQ_API_KEY or save a local provider API key."
                    ) from exc
                raise
        if self._provider_settings.model_list_enabled:
            self.list_models()

    def get_runtime_summary(self) -> dict[str, object]:
        return dict(self._runtime_summary)

    def list_models(self) -> list[dict[str, object]]:
        response = self._request("GET", "models")
        data = response.json().get("data", [])
        if not isinstance(data, list):
            raise RuntimeError(f"{self._provider_label} returned an invalid model list.")
        models: list[dict[str, object]] = []
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                models.append({"id": item["id"], "object": item.get("object", "model")})
        return models

    def transcribe(self, audio: NDArray[np.float32], settings: VociferousSettings) -> tuple[str, int, int]:
        start = time.perf_counter()
        prompt = _transcription_prompt(settings.model.initial_prompt)
        response = self._request(
            "POST",
            "audio/transcriptions",
            data=self._transcription_data(settings),
            files={"file": ("speech.wav", _wav_bytes(audio), "audio/wav")},
        )
        text, speech_duration_ms = _parse_external_transcription_response(response, len(audio))
        elapsed = time.perf_counter() - start
        transcription_time_ms = int(elapsed * 1000)
        logger.info(
            "External transcription completed in %.2fs (provider=%s, model_id=%s, resolved_device=%s, chars=%d, speech=%dms, prompt_words=%d)",
            elapsed,
            self._provider_id,
            self._provider_settings.model_id,
            self._runtime_summary.get("resolved_device"),
            len(text),
            speech_duration_ms,
            len(prompt.split()),
        )
        return post_process_transcription(text, settings), speech_duration_ms, transcription_time_ms

    def _transcription_data(self, settings: VociferousSettings) -> dict[str, str]:
        data = {
            "model": self._provider_settings.model_id,
            "response_format": "verbose_json",
            "temperature": str(max(0.0, float(self._provider_settings.temperature))),
        }
        if settings.model.language:
            data["language"] = settings.model.language
        prompt = _transcription_prompt(settings.model.initial_prompt)
        if prompt:
            data["prompt"] = prompt
        return data

    @property
    def _client_instance(self):
        if self._client is None:
            import httpx

            self._client = httpx.Client(timeout=self._provider_settings.timeout_seconds)
        return self._client

    def _headers(self) -> dict[str, str]:
        api_key = self._api_key
        return {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def _url(self, endpoint: str) -> str:
        base_url = self._provider_settings.base_url.rstrip("/")
        return f"{base_url}/{endpoint.lstrip('/')}"

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        data: dict[str, str] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
    ):
        import httpx

        if self._provider_id == "groq":
            from src.core.secret_store import validate_provider_api_key

            validate_provider_api_key(self._provider_id, self._api_key)

        attempts = max(1, int(getattr(self._provider_settings, "max_retries", 0)) + 1)
        for attempt in range(attempts):
            try:
                response = self._client_instance.request(
                    method,
                    self._url(endpoint),
                    headers=self._headers(),
                    data=data,
                    files=files,
                )
                if response.status_code < 400:
                    return response
                if attempt < attempts - 1 and self._should_retry(response.status_code):
                    time.sleep(float(getattr(self._provider_settings, "retry_backoff_seconds", 1.0)))
                    continue
                raise TranscriptionProviderRequestError(
                    self._error_message(response),
                    status_code=response.status_code,
                )
            except httpx.RequestError as exc:
                if attempt < attempts - 1:
                    time.sleep(float(getattr(self._provider_settings, "retry_backoff_seconds", 1.0)))
                    continue
                raise TranscriptionProviderRequestError(
                    f"{self._provider_label} transcription is unreachable at {self._provider_settings.base_url}: {exc}",
                    status_code=503,
                ) from exc
        raise TranscriptionProviderRequestError(f"{self._provider_label} transcription request failed")

    def _should_retry(self, status_code: int) -> bool:
        return self._provider_id == "groq" and status_code in {429, 498, 500, 502, 503}

    def _error_message(self, response) -> str:
        detail = response.text
        try:
            body = response.json()
            error = body.get("error") if isinstance(body, dict) else None
            if isinstance(error, dict) and isinstance(error.get("message"), str):
                detail = error["message"]
            elif isinstance(body, dict) and isinstance(body.get("message"), str):
                detail = body["message"]
        except ValueError:
            pass

        match response.status_code:
            case 401:
                return f"{self._provider_label} transcription authentication failed. Check the configured API key source in Settings."
            case 403:
                return f"{self._provider_label} rejected transcription. Check API key permissions and model access."
            case 404:
                return f"{self._provider_label} transcription endpoint or model was not found. Check base URL and model id."
            case 413:
                return f"{self._provider_label} rejected the audio because it is too large. Shorten the recording."
            case 422:
                return f"{self._provider_label} could not transcribe the audio: {detail}"
            case 429:
                return f"{self._provider_label} transcription rate limit exceeded."
            case _:
                return f"{self._provider_label} transcription failed with HTTP {response.status_code}: {detail}"


def _settings_for_external_provider(
    settings: VociferousSettings,
    provider_id: str,
) -> VociferousSettings:
    if provider_id not in _EXTERNAL_ASR_PROVIDERS:
        raise ValueError(f"Unknown external transcription provider: {provider_id}")
    merged = settings.model_dump()
    merged["model"]["provider"] = provider_id
    return VociferousSettings(**merged)


def list_external_transcription_provider_models(
    settings: VociferousSettings,
    provider_id: str,
) -> list[dict[str, object]]:
    provider = OpenAICompatibleTranscriptionProvider(_settings_for_external_provider(settings, provider_id))
    provider.load()
    models = provider.list_models()
    # Groq's /models endpoint returns every model they serve (LLMs, embeddings, etc.).
    # Their audio/transcriptions endpoint only accepts whisper-family models.
    # Filter everything else out so the picker doesn't show nonsense.
    if provider_id == "groq":
        models = [m for m in models if str(m.get("id", "")).lower().startswith("whisper")]
    return models


def test_external_transcription_provider(settings: VociferousSettings, provider_id: str) -> dict[str, object]:
    provider = OpenAICompatibleTranscriptionProvider(_settings_for_external_provider(settings, provider_id))
    provider.load()
    models = provider.list_models() if provider._provider_settings.model_list_enabled else []
    return {"ok": True, "provider": provider_id, "models": models}


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

    language = settings.model.language or "en"

    if local_model is None:
        local_model = create_local_model(settings)

    # ── Audio pre-processing: Silero VAD pipeline ──
    if audio_pipeline is None:
        from src.services.audio_pipeline import AudioPipeline

        audio_pipeline = AudioPipeline(sample_rate=AudioConfig.DEFAULT_SAMPLE_RATE)

    clean_audio = audio_pipeline.process(audio_data, sample_rate=AudioConfig.DEFAULT_SAMPLE_RATE)

    if clean_audio is None:
        logger.info("AudioPipeline detected no speech; skipping transcription")
        return "", 0, 0

    if isinstance(local_model, OpenAICompatibleTranscriptionProvider):
        return local_model.transcribe(clean_audio, settings)

    try:
        audio_float: NDArray[np.float32] = clean_audio
        runtime_summary = getattr(local_model, "_vociferous_runtime_summary", None)

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
        realtime_multiplier = estimated_audio_seconds / elapsed if elapsed > 0 else 0.0
        logger.info(
            "Transcription completed in %.2fs (audio=%.2fs, realtime=%.2fx, segments=%d, speech=%dms, model=%s, resolved_device=%s, compute_type=%s, cpu_threads=%s, prompt_words=%d)",
            elapsed,
            estimated_audio_seconds,
            realtime_multiplier,
            len(segment_texts),
            speech_duration_ms,
            (runtime_summary or {}).get("model_id", settings.model.model),
            (runtime_summary or {}).get("resolved_device", settings.model.device),
            (runtime_summary or {}).get("compute_type_resolved", settings.model.compute_type),
            (runtime_summary or {}).get("cpu_threads", settings.model.n_threads),
            len((initial_prompt or "").split()),
        )

        if estimated_audio_seconds >= 5.0 and realtime_multiplier <= 1.0:
            logger.warning(
                "Slow ASR run detected (audio=%.2fs, wall=%.2fs, realtime=%.2fx, model=%s, resolved_device=%s, compute_type=%s, cpu_threads=%s, language=%s)",
                estimated_audio_seconds,
                elapsed,
                realtime_multiplier,
                (runtime_summary or {}).get("model_id", settings.model.model),
                (runtime_summary or {}).get("resolved_device", settings.model.device),
                (runtime_summary or {}).get("compute_type_resolved", settings.model.compute_type),
                (runtime_summary or {}).get("cpu_threads", settings.model.n_threads),
                (runtime_summary or {}).get("language", language),
            )

        return post_process_transcription(transcription, settings), speech_duration_ms, transcription_time_ms

    except Exception as e:
        from src.core.engine_status import normalize_engine_error

        raise EngineError(normalize_engine_error(e, model_name=settings.model.model)) from e


def describe_transcription_capture(settings: VociferousSettings, *, local_model=None) -> dict[str, object]:
    """Return the ASR provider/model plus the exact prompt text sent for this run."""
    runtime_summary: dict[str, object] | None = None
    if isinstance(local_model, OpenAICompatibleTranscriptionProvider):
        runtime_summary = local_model.get_runtime_summary()
    else:
        candidate = getattr(local_model, "_vociferous_runtime_summary", None)
        if isinstance(candidate, dict):
            runtime_summary = candidate
    if runtime_summary is None:
        runtime_summary = describe_asr_runtime(settings)

    provider = str(runtime_summary.get("provider") or settings.model.provider)
    model_id = str(runtime_summary.get("model_id") or settings.model.model)
    resolved_device = str(runtime_summary.get("resolved_device") or "")
    compute_type = str(runtime_summary.get("compute_type_resolved") or runtime_summary.get("compute_type") or "")
    cpu_threads = int(runtime_summary.get("cpu_threads") or 0)
    prompt_text = (
        _transcription_prompt(settings.model.initial_prompt)
        if provider != "local_faster_whisper"
        else (settings.model.initial_prompt or "")
    )

    return {
        "transcription_provider": provider,
        "transcription_model_id": model_id,
        "transcription_resolved_device": resolved_device,
        "transcription_compute_type": compute_type,
        "transcription_cpu_threads": cpu_threads,
        "transcription_prompt_text": prompt_text,
        "transcription_prompt_chars": len(prompt_text),
        "transcription_prompt_words": len(prompt_text.split()),
    }


def _wav_bytes(audio: NDArray[np.float32]) -> bytes:
    clipped = np.clip(audio, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(AudioConfig.DEFAULT_SAMPLE_RATE)
        wav.writeframes(pcm.tobytes())
    return buffer.getvalue()


def _transcription_prompt(prompt: str | None) -> str:
    if not prompt:
        return ""
    # Groq documents a 224-token prompt limit. Words are a conservative enough
    # boundary here; the prompt is guidance, not a payload transport.
    return " ".join(prompt.split()[:160])


def _parse_external_transcription_response(response: Any, audio_samples: int) -> tuple[str, int]:
    content_type = response.headers.get("content-type", "")
    fallback_duration_ms = int(audio_samples / AudioConfig.DEFAULT_SAMPLE_RATE * 1000)

    if "application/json" not in content_type.lower():
        return response.text.strip(), fallback_duration_ms

    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError("External transcription provider returned an invalid response.")

    text = body.get("text")
    if not isinstance(text, str):
        raise RuntimeError("External transcription provider returned no transcription text.")

    segments = body.get("segments")
    if isinstance(segments, list):
        segment_ends = [item.get("end") for item in segments if isinstance(item, dict)]
        numeric_ends = [float(end) for end in segment_ends if isinstance(end, int | float)]
        if numeric_ends:
            return text, int(max(numeric_ends) * 1000)

    duration = body.get("duration")
    if isinstance(duration, int | float):
        return text, int(float(duration) * 1000)

    return text, fallback_duration_ms


def _api_key_from_env(provider_id: str, env_name: str | None) -> str | None:
    if not env_name:
        return None
    try:
        from src.core.secret_store import normalize_provider_api_key

        return normalize_provider_api_key(provider_id, os.environ.get(env_name))
    except Exception:
        return os.environ.get(env_name) or None


def _stored_api_key(provider_id: str) -> str | None:
    try:
        from src.core.secret_store import get_provider_api_key

        return get_provider_api_key(provider_id)
    except Exception:
        return None


# Post-processing helpers were extracted to src.services.transcription.post_process.
# The names below are re-exported here as the legacy single-underscore aliases used
# by tests and by other modules that imported from this file before the split.
from src.services.transcription.post_process import (  # noqa: E402
    collapse_repeated_phrases as _collapse_repeated_phrases,
    merge_segment_texts as _merge_segment_texts,
    needs_boundary_space as _needs_boundary_space,
    normalize_sentence_casing as _normalize_sentence_casing,
    post_process_transcription as post_process_transcription,
)

__all__ = [
    "_collapse_repeated_phrases",
    "_merge_segment_texts",
    "_needs_boundary_space",
    "_normalize_sentence_casing",
    "create_local_model",
    "describe_asr_runtime",
    "describe_transcription_capture",
    "list_external_transcription_provider_models",
    "post_process_transcription",
    "test_external_transcription_provider",
    "transcribe",
    "OpenAICompatibleTranscriptionProvider",
    "TranscriptionProviderRequestError",
]
