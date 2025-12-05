"""CLI integration tests for batching/VAD flags in transcribe command."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest
from typer.testing import CliRunner

from chatterbug.cli.main import app


class _FakeConfig:
    model_name = "distil-whisper/distil-large-v3"
    engine = "whisper_turbo"
    compute_type = "int8"
    device = "cpu"
    model_cache_dir = "/tmp/chatterbug-model-cache"
    params: Dict[str, str] = {}
    history_dir = "/tmp/chatterbug-history"
    history_limit = 20
    numexpr_max_threads = None
    polish_enabled = False
    polish_model = None
    polish_params: Dict[str, str] = {}


def _setup_cli_fixtures(monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    calls: Dict[str, Any] = {}

    fake_engine = object()

    def fake_build_engine(kind: str, cfg: Any) -> object:
        calls["engine_kind"] = kind
        calls["engine_config"] = cfg
        return fake_engine

    class FakeFileSource:
        def __init__(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - trivial capture
            calls["file_source_args"] = (args, kwargs)

    class FakeSession:
        def __init__(self) -> None:
            calls["session_init"] = True

        def start(
            self,
            source: Any,
            engine_adapter: Any,
            sink: Any,
            options: Any,
            engine_kind: str,
            polisher: Any = None,
        ) -> None:
            calls["start_args"] = (source, engine_adapter, sink, options, engine_kind, polisher)

        def join(self) -> None:
            calls["join_called"] = True

    monkeypatch.setattr("chatterbug.cli.main.load_config", lambda: _FakeConfig())
    monkeypatch.setattr("chatterbug.cli.main.build_engine", fake_build_engine)
    monkeypatch.setattr("chatterbug.cli.main.FileSource", FakeFileSource)
    monkeypatch.setattr("chatterbug.cli.main.build_polisher", lambda cfg: "polisher")
    monkeypatch.setattr("chatterbug.cli.main.TranscriptionSession", FakeSession)

    return calls


def test_cli_transcribe_defaults_enable_batching(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that batching is enabled by default for file transcription."""
    calls = _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    result = CliRunner().invoke(app, ["transcribe", str(audio)])

    assert result.exit_code == 0
    cfg = calls["engine_config"]
    assert cfg.params["enable_batching"] == "true"
    assert cfg.params["batch_size"] == "16"
    assert cfg.params["word_timestamps"] == "false"
    # Clean disfluencies enabled by default
    assert cfg.params["clean_disfluencies"] == "true"


def test_cli_transcribe_enable_batching_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    result = CliRunner().invoke(
        app,
        [
            "transcribe",
            str(audio),
            "--enable-batching",
            "--batch-size",
            "8",
            "--word-timestamps",
        ],
    )

    assert result.exit_code == 0
    cfg = calls["engine_config"]
    assert cfg.params["enable_batching"] == "true"
    assert cfg.params["batch_size"] == "8"
    assert cfg.params["word_timestamps"] == "true"


def test_cli_transcribe_fast_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that --fast flag enables optimized settings."""
    calls = _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    result = CliRunner().invoke(
        app,
        ["transcribe", str(audio), "--fast", "--language", "en"],
    )

    assert result.exit_code == 0
    cfg = calls["engine_config"]
    # Fast mode should enable batching with batch_size >= 16
    assert cfg.params["enable_batching"] == "true"
    assert int(cfg.params["batch_size"]) >= 16
    # Fast mode should use distil-large-v3 for English
    assert cfg.model_name == "distil-large-v3"
    # Check beam_size in options
    start_args = calls["start_args"]
    options = start_args[3]
    assert options.beam_size == 1


def test_cli_transcribe_no_clean_disfluencies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that --no-clean-disfluencies disables disfluency cleaning."""
    calls = _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    result = CliRunner().invoke(
        app,
        ["transcribe", str(audio), "--no-clean-disfluencies"],
    )

    assert result.exit_code == 0
    cfg = calls["engine_config"]
    assert cfg.params["clean_disfluencies"] == "false"


def test_cli_transcribe_clean_disfluencies_explicit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that --clean-disfluencies explicitly enables cleaning."""
    calls = _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    result = CliRunner().invoke(
        app,
        ["transcribe", str(audio), "--clean-disfluencies"],
    )

    assert result.exit_code == 0
    cfg = calls["engine_config"]
    assert cfg.params["clean_disfluencies"] == "true"
