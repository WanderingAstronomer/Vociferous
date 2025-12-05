"""Comprehensive tests to verify all three supported engines are known working."""
import pytest
from unittest.mock import patch, MagicMock

from chatterbug.engines.whisper_turbo import WhisperTurboEngine
from chatterbug.engines.voxtral import VoxtralEngine
from chatterbug.engines.parakeet import ParakeetEngine
from chatterbug.domain.model import EngineConfig, TranscriptionOptions, AudioChunk


def _config(**overrides) -> EngineConfig:
    """Build engine config with sensible defaults for testing, allowing overrides."""
    base = {
        "model_name": "turbo",
        "device": "cpu",
        "compute_type": "int8",
        "params": {},
    }
    base.update(overrides)
    return EngineConfig(**base)


class TestWhisperTurboEngine:
    """Verify WhisperTurbo (default engine, faster-whisper) works."""

    def test_whisper_turbo_init(self) -> None:
        """WhisperTurbo initializes with model name normalization."""
        config = _config(model_name="turbo")
        engine = WhisperTurboEngine(config)
        
        assert engine.model_name == "large-v3-turbo"
        assert engine.enable_batching is False
        assert engine.batch_size == 1

    def test_whisper_turbo_push_based_api(self) -> None:
        """WhisperTurbo implements push-based API correctly."""
        config = _config()
        engine = WhisperTurboEngine(config)
        
        with patch("faster_whisper.WhisperModel") as mock_model_class:
            mock_instance = MagicMock()
            mock_model_class.return_value = mock_instance
            mock_instance.transcribe.return_value = (iter([]), MagicMock())
            
            engine._lazy_model()
            
            chunk = AudioChunk(
                samples=b"\x00\x01" * 16000,
                sample_rate=16000,
                channels=1,
                start_s=0.0,
                end_s=1.0
            )
            
            options = TranscriptionOptions()
            engine.start(options)
            engine.push_audio(chunk.samples, 0)
            engine.flush()
            
            segments = engine.poll_segments()
            assert isinstance(segments, list)


class TestVoxtralEngine:
    """Verify VoxtralEngine exists and handles missing dependencies gracefully."""

    def test_voxtral_init(self) -> None:
        """VoxtralEngine initializes without dependencies loaded yet."""
        config = _config(model_name="voxtral-mini")
        engine = VoxtralEngine(config)
        
        # Model name is normalized to HuggingFace ID
        assert "Voxtral-Mini" in engine.model_name
        assert engine._model is None
        assert engine._processor is None

    def test_voxtral_missing_transformers_error(self) -> None:
        """VoxtralEngine raises clear error when transformers not available."""
        config = _config()
        engine = VoxtralEngine(config)
        
        options = TranscriptionOptions()
        
        # flush() will try to load model and fail with actionable error
        with patch.dict("sys.modules", {"transformers": None}):
            with pytest.raises(RuntimeError, match="transformers and torch are required"):
                engine.start(options)  # start() calls _lazy_model()


class TestParakeetEngine:
    """Verify ParakeetEngine exists and works in offline-only mode."""

    def test_parakeet_init(self) -> None:
        """ParakeetEngine initializes in offline-only mode (no endpoint)."""
        config = _config()
        engine = ParakeetEngine(config)
        
        assert engine.model_name is not None
        assert engine._segments == []
        assert engine._buffer == bytearray()

    def test_parakeet_push_based_api(self) -> None:
        """ParakeetEngine exposes push/flush and can emit a segment when model is ready."""
        config = _config(model_name="nvidia/parakeet-rnnt-1.1b")
        engine = ParakeetEngine(config)

        # Stub the model to avoid heavyweight downloads in unit tests
        class DummyModel:
            def transcribe(self, paths, batch_size=1, num_workers=0):
                return ["dummy transcript"]

        engine._lazy_model = lambda: None  # type: ignore[attr-defined]
        engine._model = DummyModel()
        engine._sample_rate = 16000
        engine._punct_model = None
        engine._apply_punctuation = lambda t: t  # type: ignore[attr-defined]

        options = TranscriptionOptions()
        engine.start(options)
        
        chunk = AudioChunk(
            samples=b"\x00\x01" * 16000,
            sample_rate=16000,
            channels=1,
            start_s=0.0,
            end_s=1.0
        )
        
        engine.push_audio(chunk.samples, 0)
        engine.flush()
        
        segments = engine.poll_segments()
        assert isinstance(segments, list)
        assert segments and segments[0].text == "dummy transcript"


class TestEngineFactory:
    """Verify factory can route to all three engines."""

    def test_factory_routes_to_whisper_turbo(self) -> None:
        """Factory builds WhisperTurbo for 'whisper_turbo' kind."""
        from chatterbug.engines.factory import build_engine
        
        config = _config()
        engine = build_engine("whisper_turbo", config)
        
        assert isinstance(engine, WhisperTurboEngine)

    def test_factory_routes_to_voxtral(self) -> None:
        """Factory builds VoxtralEngine for 'voxtral' kind."""
        from chatterbug.engines.factory import build_engine
        
        config = _config(model_name="voxtral-mini")
        engine = build_engine("voxtral", config)
        
        assert isinstance(engine, VoxtralEngine)

    def test_factory_routes_to_parakeet(self) -> None:
        """Factory builds ParakeetEngine for 'parakeet_rnnt' kind."""
        from chatterbug.engines.factory import build_engine
        
        config = _config()
        engine = build_engine("parakeet_rnnt", config)
        
        assert isinstance(engine, ParakeetEngine)

    def test_factory_rejects_unknown_engine(self) -> None:
        """Factory raises ValueError for unknown engine kind."""
        from chatterbug.engines.factory import build_engine
        
        config = _config()
        
        with pytest.raises(ValueError, match="Unknown engine"):
            build_engine("unknown_engine", config)  # type: ignore
