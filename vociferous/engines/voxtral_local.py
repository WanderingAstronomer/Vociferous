from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from vociferous.domain.model import (
    DEFAULT_MODEL_CACHE_DIR,
    EngineConfig,
    EngineMetadata,
    TranscriptSegment,
    TranscriptionEngine,
    TranscriptionOptions,
)
from vociferous.domain.exceptions import DependencyError, EngineError
from vociferous.engines.audio_loader import load_audio_file
from vociferous.engines.cache_manager import configure_hf_cache
from vociferous.engines.hardware import get_optimal_device, get_optimal_compute_type
from vociferous.engines.model_registry import normalize_model_name

if TYPE_CHECKING:
    from transformers import VoxtralForConditionalGeneration, AutoProcessor  # type: ignore


def required_packages() -> list[str]:
    """Return list of required Python packages for Voxtral engine."""
    return ["transformers>=4.38.0", "torch>=2.0.0", "accelerate>=0.28.0"]


def required_models() -> list[dict[str, str]]:
    """Return list of required model descriptors for Voxtral engine."""
    return [
        {
            "name": "mistralai/Voxtral-Mini-3B-2507",
            "repo_id": "mistralai/Voxtral-Mini-3B-2507",
            "description": "Mistral Voxtral Mini 3B model (default)",
        }
    ]


class VoxtralLocalEngine(TranscriptionEngine):
    """
    Transformers-based local Voxtral engine for offline audio transcription.

    Runs entirely locally using the transformers library with direct GPU/CPU
    inference. Slower than WhisperTurbo but provides smarter punctuation and
    formatting without relying on external services.
    """

    def __init__(self, config: EngineConfig) -> None:
        self.config = config
        self.model_name = normalize_model_name("voxtral_local", config.model_name)
        # Hardware-aware defaults
        self.device = config.device if config.device != "auto" else get_optimal_device()
        self.precision = config.compute_type if config.compute_type != "auto" else get_optimal_compute_type(self.device)
        cache_root = Path(config.model_cache_dir or DEFAULT_MODEL_CACHE_DIR).expanduser()
        cache_root.mkdir(parents=True, exist_ok=True)
        self.cache_dir = cache_root
        self._model: VoxtralForConditionalGeneration | None = None
        self._processor: AutoProcessor | None = None

    def _lazy_model(self):
        if self._model is not None:
            return
        try:
            from transformers import VoxtralForConditionalGeneration, AutoProcessor
            import torch
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise RuntimeError(
                "transformers and torch are required for VoxtralEngine; install with vociferous[voxtral]"
            ) from exc

        if self.device == "cuda" and not torch.cuda.is_available():
            raise EngineError("CUDA requested for Voxtral but no GPU is available")

        # Use cache manager to prevent duplicate downloads to ~/.cache/huggingface/hub
        with configure_hf_cache(self.cache_dir):
            self._processor = AutoProcessor.from_pretrained(
                self.model_name, cache_dir=str(self.cache_dir)
            )
            dtype = torch.bfloat16 if self.device == "cuda" else torch.float32
            self._model = VoxtralForConditionalGeneration.from_pretrained(
                self.model_name,
                dtype=dtype,
                cache_dir=str(self.cache_dir),
            ).to(self.device)

    def transcribe_file(
        self, 
        audio_path: Path, 
        options: TranscriptionOptions
    ) -> list[TranscriptSegment]:
        """Transcribe entire audio file in one batch operation.
        
        This is the new simplified interface that processes preprocessed audio files.
        Audio should already be decoded and condensed via the audio preprocessing pipeline.
        
        Args:
            audio_path: Path to preprocessed audio file (16kHz mono PCM WAV)
            options: Transcription options (language, etc.)
            
        Returns:
            List of transcript segments with timestamps
        """
        self._lazy_model()
        
        if self._processor is None or self._model is None:
            raise RuntimeError("Model not loaded")

        import torch

        # Load audio file
        audio_np = load_audio_file(audio_path)

        processor = self._processor
        model = self._model

        inputs = processor.apply_transcription_request(
            audio=[audio_np],
            language=options.language or "en",
            model_id=self.model_name,
            sampling_rate=16000,
            format=["wav"],
        ).to(self.device, dtype=model.dtype)

        gen_kwargs = {}
        params = options.params or {}
        if "max_new_tokens" in params:
            gen_kwargs["max_new_tokens"] = int(params["max_new_tokens"])
        else:
            gen_kwargs["max_new_tokens"] = 2048

        with torch.inference_mode():
            outputs = model.generate(**inputs, **gen_kwargs)

        input_length = inputs.input_ids.shape[1]
        new_tokens = outputs[:, input_length:]
        transcription = processor.batch_decode(
            new_tokens, skip_special_tokens=True
        )[0]

        result = []
        if transcription.strip():
            result.append(TranscriptSegment(
                text=transcription.strip(),
                start_s=0.0,
                end_s=len(audio_np) / 16000.0,
                language=options.language or "en",
                confidence=1.0
            ))

        return result

    @property
    def metadata(self) -> EngineMetadata:
        """Return engine metadata for result building."""
        return EngineMetadata(
            model_name=self.model_name,
            device=self.device,
            precision=self.precision,
        )
