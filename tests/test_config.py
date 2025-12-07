from vociferous.config.schema import AppConfig


def test_app_config_defaults_params() -> None:
    cfg = AppConfig()
    assert cfg.params["enable_batching"] == "false"
    assert cfg.params["batch_size"] == "1"
    assert cfg.params["word_timestamps"] == "false"


def test_app_config_polish_defaults() -> None:
    cfg = AppConfig()
    assert cfg.polish_enabled is False
    assert cfg.polish_model == "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    assert cfg.polish_params["repo_id"] == "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
    assert cfg.polish_params["max_tokens"] == "128"


def test_app_config_numexpr_default() -> None:
    cfg = AppConfig()
    assert cfg.numexpr_max_threads is None
