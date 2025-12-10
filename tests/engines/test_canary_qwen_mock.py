from __future__ import annotations

from pathlib import Path
from vociferous.domain.model import EngineConfig, TranscriptionOptions
from vociferous.engines.canary_qwen import CanaryQwenEngine


def _engine(use_mock: bool = True) -> CanaryQwenEngine:
    config = EngineConfig(
        model_name="nvidia/canary-qwen-2.5b",
        params={"mode": "asr", "use_mock": str(use_mock).lower()},
    )
    return CanaryQwenEngine(config)


def test_canary_qwen_transcribe_file(tmp_path: Path) -> None:
    audio_path = tmp_path / "audio.raw"
    audio_path.write_bytes(b"\x01" * 64000)

    engine = _engine()
    segments = engine.transcribe_file(audio_path, TranscriptionOptions(language="en"))

    assert segments
    assert segments[0].text


def test_canary_qwen_refine_text() -> None:
    engine = _engine()
    refined = engine.refine_text("hello world")

    assert refined.startswith("Hello")
    assert refined.endswith("[refined]")
