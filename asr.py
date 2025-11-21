"""ASR engine dispatcher for ChatterBug.

Primary engine: Whisper Large v3 Turbo via transformers (HF layout).
Fallback: Faster-Whisper small/int8 (converted weights).

Models live under `models/` by default and are never downloaded automatically.
Use `python -m download --model whisper-large-v3-turbo` to fetch the primary model.
"""
from __future__ import annotations

import io
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import soundfile as sf
import tomllib

LOGGER = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path.home() / ".chatterbug" / "config.toml"
DEFAULT_MODELS_ROOT = Path(__file__).resolve().parent / "models"

DEFAULT_MODELS: Dict[str, Dict[str, object]] = {
    "whisper_large_v3_turbo": {
        "format": "hf_whisper",
        "id": "openai/whisper-large-v3-turbo",
        "local_dir": "whisper-large-v3-turbo",
        "max_new_tokens": 448,
    },
    "faster_whisper_small": {
        "format": "fw",
        "id": "guillaumekln/faster-whisper-small-int8",
        "local_dir": "faster_whisper_small",
        "compute_type": "int8",
        "max_new_tokens": 320,
    },
}

DEFAULT_CONFIG: Dict[str, object] = {
    "engine": "whisper_large_v3_turbo",
    "fallbacks": ["faster_whisper_small"],
    "models_root": str(DEFAULT_MODELS_ROOT),
    "models": DEFAULT_MODELS,
}

CONFIG_CACHE: Optional[Dict[str, object]] = None
ENGINE_CACHE: Dict[str, "BaseEngine"] = {}
FAILED_ENGINES: set[str] = set()


class EngineUnavailable(RuntimeError):
    """Raised when an engine cannot serve transcription."""


@dataclass
class EngineSpec:
    name: str
    model_id: str
    format: str
    local_dir: Path
    max_new_tokens: int = 512
    compute_type: Optional[str] = None


class BaseEngine:
    name = "base"

    def transcribe(self, wav_bytes: bytes, language_hint: Optional[str] = "en") -> Tuple[str, Dict]:
        raise NotImplementedError

    def is_available(self) -> Tuple[bool, str]:
        return True, "ok"


class TransformersWhisperEngine(BaseEngine):
    def __init__(self, spec: EngineSpec):
        self.name = spec.name
        self.spec = spec
        self.model = None
        self.processor = None
        self.device = None
        self.dtype = None
        self.max_target_positions = 448
        self.generate_defaults = {
            "num_beams": 1,
            "condition_on_prev_tokens": False,
            "temperature": 0.0,
            "compression_ratio_threshold": 1.35,
            "logprob_threshold": -1.0,
            "no_speech_threshold": 0.6,
        }

    def _lazy_load(self):
        if self.model and self.processor:
            return
        if not self.spec.local_dir.exists():
            raise EngineUnavailable(f"Model path not found: {self.spec.local_dir}")
        try:
            import torch  # type: ignore
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor  # type: ignore
        except Exception as exc:
            raise EngineUnavailable("transformers/torch not installed") from exc

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        try:
            processor = AutoProcessor.from_pretrained(self.spec.local_dir)
            model = AutoModelForSpeechSeq2Seq.from_pretrained(
                self.spec.local_dir,
                dtype=dtype,
                low_cpu_mem_usage=True,
                use_safetensors=True,
            )
        except Exception as exc:
            raise EngineUnavailable(f"Failed to load whisper model: {exc}") from exc

        model.to(device)
        self.model = model
        self.processor = processor
        self.device = device
        self.dtype = dtype
        self.max_target_positions = getattr(getattr(model, "config", {}), "max_target_positions", 448)

    def transcribe(self, wav_bytes: bytes, language_hint: Optional[str] = "en") -> Tuple[str, Dict]:
        if not wav_bytes:
            raise EngineUnavailable("No audio provided")
        self._lazy_load()
        assert self.model is not None and self.processor is not None

        import torch  # type: ignore

        audio_arr, sample_rate = sf.read(io.BytesIO(wav_bytes))
        if audio_arr.ndim > 1:
            audio_arr = audio_arr.mean(axis=1)
        duration_s = float(len(audio_arr)) / float(sample_rate) if sample_rate else 0.0
        processed = self.processor(
            audio_arr,
            sampling_rate=sample_rate,
            return_tensors="pt",
            padding="longest",
        )

        input_features = processed["input_features"].to(self.device)
        attention_mask = processed.get("attention_mask")
        if attention_mask is not None:
            attention_mask = attention_mask.to(self.device)

        gen_kwargs = dict(self.generate_defaults)
        max_allowed = max(1, int(self.max_target_positions) - 8)
        requested = int(self.spec.max_new_tokens or max_allowed)
        gen_kwargs["max_new_tokens"] = max(32, min(requested, max_allowed))
        if language_hint:
            gen_kwargs["language"] = language_hint
            gen_kwargs["task"] = "transcribe"

        start = time.time()
        try:
            with torch.no_grad():
                generated_ids = self.model.generate(
                    input_features=input_features,
                    attention_mask=attention_mask,
                    **gen_kwargs,
                )
            text = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        except Exception as exc:
            raise EngineUnavailable(f"Whisper Turbo generation failed: {exc}") from exc

        latency_s = time.time() - start
        rtf = latency_s / duration_s if duration_s > 0 else 0.0
        meta = {
            "engine": self.name,
            "model": self.spec.model_id,
            "quantization": "fp16" if self.dtype == torch.float16 else "fp32",
            "duration_s": duration_s,
            "latency_s": latency_s,
            "rtf": rtf,
            "device": str(self.device),
            "lang": language_hint or "auto",
        }
        return text.strip(), meta

    def is_available(self) -> Tuple[bool, str]:
        if not self.spec.local_dir.exists():
            return False, f"Model path not found: {self.spec.local_dir}"
        try:
            import torch  # type: ignore
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor  # type: ignore
        except Exception:
            return False, "transformers/torch not installed"
        safetensors = list(self.spec.local_dir.glob("*.safetensors"))
        if not safetensors:
            return False, "no .safetensors files found (run downloader)"
        return True, "ok"


class FasterWhisperEngine(BaseEngine):
    def __init__(self, spec: EngineSpec):
        self.name = spec.name
        self.spec = spec
        self.model = None

    def _lazy_load(self):
        if self.model:
            return
        if not self.spec.local_dir.exists():
            raise EngineUnavailable(f"Model path not found: {self.spec.local_dir}")
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except Exception as exc:
            raise EngineUnavailable("faster-whisper not installed") from exc
        device, compute_type = select_device_and_precision(self.spec.compute_type)
        try:
            self.model = WhisperModel(str(self.spec.local_dir), device=device, compute_type=compute_type)
        except Exception as exc:
            raise EngineUnavailable(f"Failed to load Faster-Whisper: {exc}") from exc

    def transcribe(self, wav_bytes: bytes, language_hint: Optional[str] = "en") -> Tuple[str, Dict]:
        if not wav_bytes:
            raise EngineUnavailable("No audio provided")
        self._lazy_load()
        assert self.model is not None

        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            tmp.write(wav_bytes)
            tmp.flush()
            start = time.time()
            try:
                segments, info = self.model.transcribe(tmp.name, language=language_hint or None, beam_size=1)
                transcript = " ".join(seg.text.strip() for seg in segments).strip()
            except Exception as exc:
                raise EngineUnavailable(f"Faster-Whisper failed: {exc}") from exc

        latency_s = time.time() - start
        duration_s = getattr(info, "duration", 0.0) or 0.0
        rtf = latency_s / duration_s if duration_s > 0 else 0.0
        meta = {
            "engine": self.name,
            "model": self.spec.model_id,
            "quantization": self.spec.compute_type or "int8",
            "duration_s": duration_s,
            "latency_s": latency_s,
            "rtf": rtf,
            "device": getattr(self.model, "device", "cpu"),
            "lang": language_hint or "auto",
        }
        return transcript, meta

    def is_available(self) -> Tuple[bool, str]:
        if not self.spec.local_dir.exists():
            return False, f"Model path not found: {self.spec.local_dir}"
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except Exception:
            return False, "faster-whisper not installed"
        bin_files = list(self.spec.local_dir.glob("*.bin"))
        if not bin_files:
            return False, "no .bin files found (use Faster-Whisper conversion)"
        return True, "ok"


def load_config(config_path: Optional[Path] = None) -> Dict[str, object]:
    cfg = dict(DEFAULT_CONFIG)
    cfg["models"] = dict(DEFAULT_MODELS)
    path = config_path or DEFAULT_CONFIG_PATH
    if path.exists():
        try:
            with path.open("rb") as f:
                user_cfg = tomllib.load(f)
            cfg.update({k: v for k, v in user_cfg.items() if k in ("engine", "fallbacks", "models_root", "models")})
            if "models" in user_cfg:
                merged = dict(DEFAULT_MODELS)
                merged.update(user_cfg["models"])
                cfg["models"] = merged
        except Exception as exc:
            LOGGER.warning("Failed to read config %s: %s", path, exc)
    return cfg


def select_device_and_precision(explicit_compute_type: Optional[str] = None) -> Tuple[str, str]:
    device = "cpu"
    try:
        import torch  # type: ignore

        if torch.cuda.is_available():
            device = "cuda"
    except Exception:
        device = "cpu"
    compute_type = explicit_compute_type or ("int8_float16" if device == "cuda" else "int8")
    return device, compute_type


def _resolve_engine_spec(name: str, cfg: Dict[str, object]) -> EngineSpec:
    models_root = Path(str(cfg.get("models_root", DEFAULT_MODELS_ROOT)))
    models_cfg = cfg.get("models", {}) or {}
    raw = dict(DEFAULT_MODELS.get(name, {}))
    raw.update(models_cfg.get(name, {}))  # type: ignore
    local_dir = models_root / str(raw.get("local_dir", name))
    spec = EngineSpec(
        name=name,
        model_id=str(raw.get("id", name)),
        format=str(raw.get("format", "hf_whisper")),
        local_dir=local_dir,
        max_new_tokens=int(raw.get("max_new_tokens", 512) or 512),
        compute_type=raw.get("compute_type"),
    )
    return spec


def _engine_order(cfg: Dict[str, object]) -> List[str]:
    primary = str(cfg.get("engine", DEFAULT_CONFIG["engine"]))
    fallbacks = [str(f) for f in cfg.get("fallbacks", DEFAULT_CONFIG["fallbacks"])]
    order = [primary] + [f for f in fallbacks if f != primary]
    seen = set()
    deduped: List[str] = []
    for name in order:
        if name not in seen:
            deduped.append(name)
            seen.add(name)
    return deduped


def _engine_for(name: str, cfg: Dict[str, object]) -> BaseEngine:
    if name in FAILED_ENGINES:
        raise EngineUnavailable(f"{name} previously failed")
    if name in ENGINE_CACHE:
        return ENGINE_CACHE[name]
    spec = _resolve_engine_spec(name, cfg)
    if spec.format == "hf_whisper":
        engine: BaseEngine = TransformersWhisperEngine(spec)
    elif spec.format == "fw":
        engine = FasterWhisperEngine(spec)
    else:
        raise EngineUnavailable(f"Unsupported engine format: {spec.format}")
    ENGINE_CACHE[name] = engine
    return engine


def _get_config() -> Dict[str, object]:
    global CONFIG_CACHE
    if CONFIG_CACHE is None:
        CONFIG_CACHE = load_config()
    return CONFIG_CACHE


def transcribe_wav(wav_bytes: bytes, language_hint: Optional[str] = "en") -> Tuple[str, Dict]:
    cfg = _get_config()
    order = _engine_order(cfg)
    errors: List[str] = []

    for name in order:
        try:
            engine = _engine_for(name, cfg)
            text, meta = engine.transcribe(wav_bytes, language_hint=language_hint)
            meta["dur_s"] = meta.get("duration_s", 0.0)
            return text, meta
        except EngineUnavailable as exc:
            FAILED_ENGINES.add(name)
            msg = f"{name} unavailable: {exc}"
            LOGGER.warning(msg)
            errors.append(msg)
        except Exception as exc:  # pragma: no cover
            FAILED_ENGINES.add(name)
            msg = f"{name} failed unexpectedly: {exc}"
            LOGGER.exception(msg)
            errors.append(msg)

    meta = {
        "engine": "unavailable",
        "model": "none",
        "quantization": "none",
        "duration_s": 0.0,
        "latency_s": 0.0,
        "rtf": 0.0,
        "device": "cpu",
        "lang": language_hint or "en",
        "error": "; ".join(errors) if errors else "no engines configured",
        "dur_s": 0.0,
    }
    return "[transcription unavailable]", meta


def check_engine_availability() -> Tuple[bool, Dict[str, str]]:
    cfg = _get_config()
    order = _engine_order(cfg)
    details: Dict[str, str] = {}
    overall_ok = False
    for name in order:
        try:
            engine = _engine_for(name, cfg)
            ok, msg = engine.is_available()
            details[name] = msg if ok else f"missing: {msg}"
            if ok and not overall_ok:
                overall_ok = True
        except Exception as exc:
            details[name] = f"error: {exc}"
    return overall_ok, details
