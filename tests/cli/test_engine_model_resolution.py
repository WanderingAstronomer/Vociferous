import pytest

from vociferous.cli.helpers import build_transcribe_configs_from_cli
from vociferous.config.schema import AppConfig
from vociferous.domain.model import DEFAULT_CANARY_MODEL, DEFAULT_WHISPER_MODEL
from vociferous.engines.model_registry import normalize_model_name


@pytest.mark.parametrize(
    "engine,expected",
    [
        ("whisper_turbo", DEFAULT_WHISPER_MODEL),
        ("voxtral_local", normalize_model_name("voxtral_local", None)),
    ],
)
def test_cli_engine_override_uses_engine_defaults(engine: str, expected: str) -> None:
    """When CLI engine differs from app default (canary), use target engine defaults."""
    app_config = AppConfig()

    bundle = build_transcribe_configs_from_cli(
        app_config=app_config,
        engine=engine,
        language="en",
        preset=None,
        refine=None,
    )

    assert bundle.engine_config.model_name == expected


def test_normalize_remaps_canary_for_other_engines() -> None:
    """Cross-engine model names fall back to the requested engine's default."""
    voxtral_default = normalize_model_name("voxtral_local", None)

    assert normalize_model_name("whisper_turbo", DEFAULT_CANARY_MODEL) == DEFAULT_WHISPER_MODEL
    assert normalize_model_name("voxtral_local", DEFAULT_CANARY_MODEL) == voxtral_default
    assert normalize_model_name("whisper_turbo", "nvidia/canary-1b") == DEFAULT_WHISPER_MODEL
