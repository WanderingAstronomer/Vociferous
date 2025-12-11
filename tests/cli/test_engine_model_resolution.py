import pytest

from vociferous.cli.helpers import build_transcribe_configs_from_cli
from vociferous.config.schema import AppConfig
from vociferous.domain.model import DEFAULT_CANARY_MODEL, DEFAULT_WHISPER_MODEL
from vociferous.engines.model_registry import normalize_model_name


@pytest.mark.parametrize(
    "engine,expected",
    [
        ("whisper_turbo", DEFAULT_WHISPER_MODEL),
        ("canary_qwen", DEFAULT_CANARY_MODEL),
    ],
)
def test_cli_engine_override_uses_engine_defaults(engine: str, expected: str) -> None:
    """When CLI engine differs from app default, use target engine defaults."""
    app_config = AppConfig()

    bundle = build_transcribe_configs_from_cli(
        app_config=app_config,
        engine=engine,
        language="en",
        refine=None,
    )

    assert bundle.engine_config.model_name == expected


def test_whisper_rejects_invalid_model_names() -> None:
    """Invalid model names for whisper_turbo raise ValueError."""
    # Whisper should reject a Canary model name
    with pytest.raises(ValueError, match="Invalid model"):
        normalize_model_name("whisper_turbo", DEFAULT_CANARY_MODEL)
    
    with pytest.raises(ValueError, match="Invalid model"):
        normalize_model_name("whisper_turbo", "nvidia/canary-1b")
