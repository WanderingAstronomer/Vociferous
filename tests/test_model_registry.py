from chatterbug.engines.model_registry import normalize_model_name


def test_normalize_model_name_alias() -> None:
    # faster-whisper whisper_turbo uses short names
    assert normalize_model_name("whisper_turbo", "distil-large-v3") == "distil-large-v3"
    # voxtral and parakeet use full HF paths
    assert normalize_model_name("voxtral", None) == "mistralai/Voxtral-Mini-3B-2507"
