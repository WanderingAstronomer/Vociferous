"""
Tests for the v4 model registry.

Verifies model catalog structure and lookups.
"""

from src.core.model_registry import (
    ASR_MODELS,
    SLM_MODELS,
    ASRModel,
    SLMModel,
    get_asr_model,
    get_model_catalog,
    get_slm_model,
)


class TestASRModels:
    def test_default_model_exists(self):
        assert "large-v3-turbo-q5_0" in ASR_MODELS

    def test_asr_model_type(self):
        m = ASR_MODELS["large-v3-turbo-q5_0"]
        assert isinstance(m, ASRModel)
        assert m.filename.endswith(".bin")
        assert m.repo == "ggerganov/whisper.cpp"

    def test_get_asr_model(self):
        m = get_asr_model("large-v3-turbo-q5_0")
        assert m is not None
        assert m.tier == "fast"

    def test_get_asr_model_missing(self):
        assert get_asr_model("nonexistent") is None


class TestSLMModels:
    def test_default_slm_exists(self):
        assert "qwen4b" in SLM_MODELS

    def test_slm_model_type(self):
        m = SLM_MODELS["qwen4b"]
        assert isinstance(m, SLMModel)
        assert m.filename.endswith(".gguf")
        assert m.quant == "Q4_K_M"

    def test_get_slm_model(self):
        m = get_slm_model("qwen8b")
        assert m is not None
        assert m.tier == "quality"

    def test_get_slm_model_missing(self):
        assert get_slm_model("nonexistent") is None


class TestCatalog:
    def test_catalog_structure(self):
        cat = get_model_catalog()
        assert "asr" in cat
        assert "slm" in cat
        assert len(cat["asr"]) == len(ASR_MODELS)
        assert len(cat["slm"]) == len(SLM_MODELS)
