import numpy as np
from pathlib import Path

from vociferous.audio.preprocessing import AudioPreProcessor
from vociferous.cli.helpers import build_audio_source
from vociferous.config.schema import AppConfig
from vociferous.domain.model import PreprocessingConfig
from vociferous.audio.sources import FileSource, PreprocessedFileSource


def _tone(sample_rate: int, duration_ms: int, amplitude: int = 10000) -> np.ndarray:
    samples = int(sample_rate * (duration_ms / 1000))
    return np.full(samples, amplitude, dtype=np.int16)


def _silence(sample_rate: int, duration_ms: int) -> np.ndarray:
    samples = int(sample_rate * (duration_ms / 1000))
    return np.zeros(samples, dtype=np.int16)


def test_analyze_pcm_speech_boundaries_splits_only_on_long_gaps() -> None:
    sample_rate = 16000
    config = PreprocessingConfig(gap_threshold_ms=5000)
    preprocessor = AudioPreProcessor(config)

    pcm = np.concatenate(
        [
            _tone(sample_rate, 1000),          # speech
            _silence(sample_rate, 4000),       # <5s pause should stay merged
            _tone(sample_rate, 1000),          # speech resumes
            _silence(sample_rate, 6000),       # >=5s pause should create gap
            _tone(sample_rate, 1000),          # final speech
        ],
        dtype=np.int16,
    ).tobytes()

    speech_map = preprocessor.analyze_pcm_speech_boundaries(pcm, sample_rate=sample_rate)

    assert len(speech_map.silence_gaps) == 1
    start_ms, end_ms, duration_ms = speech_map.silence_gaps[0]
    assert duration_ms >= 5900  # allow small rounding differences around 6s
    assert start_ms >= 5900 and end_ms >= 11900


def test_build_audio_source_uses_preprocessed_when_enabled() -> None:
    cfg = AppConfig(preprocessing_enabled=True, chunk_ms=1234)

    source = build_audio_source(Path("audio.wav"), cfg)

    assert isinstance(source, PreprocessedFileSource)
    assert source.chunk_ms == cfg.chunk_ms
    assert source.config.gap_threshold_ms == cfg.preprocessing_gap_threshold_ms
    assert source.config.split_on_gaps is True
    assert source.config.head_margin_ms == cfg.preprocessing_head_margin_ms
    assert source.config.tail_margin_ms == cfg.preprocessing_tail_margin_ms


def test_build_audio_source_defaults_to_file_source_when_disabled() -> None:
    cfg = AppConfig(preprocessing_enabled=False, chunk_ms=777)

    source = build_audio_source(Path("audio.wav"), cfg)

    assert isinstance(source, FileSource)
    assert source.chunk_ms == cfg.chunk_ms
