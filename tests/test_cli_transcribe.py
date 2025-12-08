"""CLI integration tests for transcribe command with simplified signature."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest
from typer.testing import CliRunner

from vociferous.cli.main import app
from vociferous.domain.model import DEFAULT_WHISPER_MODEL


class _FakeConfig:
    model_name = DEFAULT_WHISPER_MODEL
    engine = "whisper_turbo"
    compute_type = "auto"
    device = "auto"
    model_cache_dir = "/tmp/vociferous-model-cache"
    vllm_endpoint = "http://localhost:8000"
    chunk_ms = 960
    params: Dict[str, str] = {
        "enable_batching": "true",
        "batch_size": "16",
        "word_timestamps": "false",
        "vad_filter": "true",
    }
    history_dir = "/tmp/vociferous-history"
    history_limit = 20
    numexpr_max_threads = None
    polish_enabled = False
    polish_model = None
    polish_params: Dict[str, str] = {
        "max_tokens": "128",
        "temperature": "0.2",
        "gpu_layers": "0",
        "context_length": "2048",
    }


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

    monkeypatch.setattr("vociferous.cli.main.load_config", lambda: _FakeConfig())
    monkeypatch.setattr("vociferous.cli.main.build_engine", fake_build_engine)
    monkeypatch.setattr("vociferous.cli.main.FileSource", FakeFileSource)
    monkeypatch.setattr("vociferous.cli.main.build_polisher", lambda cfg: None)
    monkeypatch.setattr("vociferous.cli.main.TranscriptionSession", FakeSession)

    return calls


def test_cli_transcribe_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that basic transcription works with defaults from config."""
    calls = _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    result = CliRunner().invoke(app, ["transcribe", str(audio)])

    assert result.exit_code == 0
    cfg = calls["engine_config"]
    # Config values should be applied
    assert cfg.params["enable_batching"] == "true"
    assert cfg.params["batch_size"] == "16"
    assert cfg.params["word_timestamps"] == "false"
    assert cfg.params["clean_disfluencies"] == "true"
    assert calls["engine_kind"] == "whisper_turbo"


def test_cli_transcribe_engine_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that --engine flag overrides config engine."""
    calls = _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    result = CliRunner().invoke(
        app,
        ["transcribe", str(audio), "--engine", "voxtral_local"],
    )

    assert result.exit_code == 0
    assert calls["engine_kind"] == "voxtral_local"


def test_cli_transcribe_preset_fast(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that --preset fast selects fast model and settings."""
    calls = _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    result = CliRunner().invoke(
        app,
        ["transcribe", str(audio), "--preset", "fast"],
    )

    assert result.exit_code == 0
    cfg = calls["engine_config"]
    assert cfg.params["preset"] == "fast"
    # Fast preset should enable batching
    assert cfg.params["enable_batching"] == "true"
    # Fast uses turbo model
    assert "turbo" in cfg.model_name.lower()
    # Check options
    start_args = calls["start_args"]
    options = start_args[3]
    assert options.preset == "fast"
    assert options.beam_size == 1


def test_cli_transcribe_preset_high_accuracy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that --preset high_accuracy selects high quality model and settings."""
    calls = _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    result = CliRunner().invoke(
        app,
        ["transcribe", str(audio), "--preset", "high_accuracy"],
    )

    assert result.exit_code == 0
    cfg = calls["engine_config"]
    assert cfg.params["preset"] == "high_accuracy"
    # High accuracy uses large model
    assert "large" in cfg.model_name.lower()
    # Check options
    start_args = calls["start_args"]
    options = start_args[3]
    assert options.preset == "high_accuracy"
    assert options.beam_size == 2


def test_cli_transcribe_engine_short_alias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that -e short alias for --engine works."""
    calls = _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    result = CliRunner().invoke(
        app,
        ["transcribe", str(audio), "-e", "voxtral_local"],
    )

    assert result.exit_code == 0
    assert calls["engine_kind"] == "voxtral_local"


def test_cli_transcribe_language_short_alias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that -l short alias for --language works."""
    calls = _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    result = CliRunner().invoke(
        app,
        ["transcribe", str(audio), "-l", "es"],
    )

    assert result.exit_code == 0
    start_args = calls["start_args"]
    options = start_args[3]
    assert options.language == "es"


def test_cli_transcribe_output_short_alias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that -o short alias for --output works."""
    calls = _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")
    output_file = tmp_path / "out.txt"

    result = CliRunner().invoke(
        app,
        ["transcribe", str(audio), "-o", str(output_file)],
    )

    assert result.exit_code == 0


def test_cli_transcribe_preset_short_alias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that -p short alias for --preset works."""
    calls = _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    result = CliRunner().invoke(
        app,
        ["transcribe", str(audio), "-p", "high_accuracy"],
    )

    assert result.exit_code == 0
    cfg = calls["engine_config"]
    assert cfg.params.get("preset") == "high_accuracy"


def test_cli_transcribe_rejects_directory_as_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that passing a directory instead of a file shows clear error."""
    calls = _setup_cli_fixtures(monkeypatch)
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()

    result = CliRunner().invoke(
        app,
        ["transcribe", str(audio_dir)],
    )

    assert result.exit_code != 0
    assert "directory" in result.stdout.lower()


def test_cli_transcribe_rejects_output_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that passing a directory for --output shows clear error."""
    calls = _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    result = CliRunner().invoke(
        app,
        ["transcribe", str(audio), "-o", str(output_dir)],
    )

    assert result.exit_code != 0
    assert "directory" in result.stdout.lower()


def test_cli_transcribe_language_english(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that language flag works correctly."""
    calls = _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    result = CliRunner().invoke(
        app,
        ["transcribe", str(audio), "--language", "en"],
    )

    assert result.exit_code == 0
    start_args = calls["start_args"]
    options = start_args[3]
    assert options.language == "en"


def test_cli_transcribe_vllm_engine_gets_balanced_preset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that vLLM engines default to balanced preset."""
    calls = _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    result = CliRunner().invoke(
        app,
        ["transcribe", str(audio), "--engine", "whisper_vllm"],
    )

    assert result.exit_code == 0
    cfg = calls["engine_config"]
    # vLLM should default to balanced preset
    assert cfg.params["preset"] == "balanced"
    assert "turbo" in cfg.model_name.lower()

