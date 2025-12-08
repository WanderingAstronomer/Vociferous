"""Comprehensive tests to verify supported engines are known working."""
import pytest
from unittest.mock import patch, MagicMock

from vociferous.engines.whisper_turbo import WhisperTurboEngine
from vociferous.engines.voxtral_local import VoxtralLocalEngine
from vociferous.domain.model import EngineConfig, TranscriptionOptions, AudioChunk


def _config(**overrides) -> EngineConfig:
    """Build engine config with sensible defaults for testing, allowing overrides."""
    base = {
        "model_name": "turbo",
        "device": "auto",
        "compute_type": "auto",
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
        assert engine.enable_batching is True
        assert engine.batch_size == 8

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


class TestVoxtralLocalEngine:
    """Verify VoxtralLocalEngine exists and handles missing dependencies gracefully."""

    def test_voxtral_init(self) -> None:
        """VoxtralLocalEngine initializes without dependencies loaded yet."""
        config = _config(model_name="voxtral-mini")
        engine = VoxtralLocalEngine(config)
        
        # Model name is normalized to HuggingFace ID
        assert "Voxtral-Mini" in engine.model_name
        assert engine._model is None
        assert engine._processor is None

    def test_voxtral_missing_transformers_error(self) -> None:
        """VoxtralLocalEngine raises clear error when transformers not available."""
        config = _config()
        engine = VoxtralLocalEngine(config)
        
        options = TranscriptionOptions()
        
        with patch.dict("sys.modules", {"transformers": None}):
            with pytest.raises(RuntimeError, match="transformers and torch are required"):
                engine.start(options)  # start() calls _lazy_model()


class TestEngineFactory:
    """Verify factory can route to registered engines."""

    def test_factory_routes_to_whisper_turbo(self) -> None:
        """Factory builds WhisperTurbo for 'whisper_turbo' kind."""
        from vociferous.engines.factory import build_engine
        
        config = _config()
        engine = build_engine("whisper_turbo", config)
        
        assert isinstance(engine, WhisperTurboEngine)

    def test_factory_routes_to_voxtral(self) -> None:
        """Factory builds VoxtralLocalEngine for 'voxtral' alias."""
        from vociferous.engines.factory import build_engine
        
        config = _config(model_name="voxtral-mini")
        engine = build_engine("voxtral", config)
        
        assert isinstance(engine, VoxtralLocalEngine)

    def test_factory_rejects_unknown_engine(self) -> None:
        """Factory raises error for unknown engine kind."""
        from vociferous.engines.factory import build_engine
        
        config = _config()
        
        with pytest.raises(Exception, match="Unknown engine"):
            build_engine("unknown_engine", config)  # type: ignore
