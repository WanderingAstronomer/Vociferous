from pathlib import Path

import chatterbug.polish.factory as factory
from chatterbug.polish.base import NullPolisher, PolisherConfig, RuleBasedPolisher
from chatterbug.polish.factory import build_polisher


def test_null_polisher_noop() -> None:
    polisher = NullPolisher()
    assert polisher.polish("hello world") == "hello world"


def test_rule_based_polisher_fixes_spacing_and_hyphens() -> None:
    polisher = RuleBasedPolisher()
    text = "the mo- del , with extra   spaces ."
    assert polisher.polish(text) == "the model, with extra spaces."


def test_rule_based_polisher_preserves_real_hyphens() -> None:
    polisher = RuleBasedPolisher()
    text = "state-of-the-art system"
    assert polisher.polish(text) == "state-of-the-art system"


def test_build_polisher_defaults_to_null_when_disabled() -> None:
    polisher = build_polisher(PolisherConfig(enabled=False))
    assert isinstance(polisher, NullPolisher)


def test_build_polisher_raises_for_unknown_model() -> None:
    config = PolisherConfig(enabled=True, model="does-not-exist")
    try:
        build_polisher(config)
    except ValueError as exc:
        assert "Unknown polisher model" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected ValueError for unknown model")


def test_build_polisher_alias_heuristic() -> None:
    polisher = build_polisher(PolisherConfig(enabled=True, model="heuristic"))
    assert isinstance(polisher, RuleBasedPolisher)


def test_build_polisher_llama_cpp_with_existing_file(monkeypatch, tmp_path) -> None:
    fake_model = tmp_path / "model.gguf"
    fake_model.write_text("stub")

    class FakePolisher:
        def __init__(self, options) -> None:
            self.options = options

        def polish(self, text: str) -> str:  # pragma: no cover - trivial
            return text

    monkeypatch.setattr(factory, "LlamaCppPolisher", FakePolisher)

    polisher = build_polisher(
        PolisherConfig(
            enabled=True,
            model="qwen2.5-1.5b-instruct-q4_k_m.gguf",
            params={"model_path": str(fake_model), "skip_download": "true"},
        )
    )

    assert isinstance(polisher, FakePolisher)
    assert isinstance(polisher.options.model_path, Path)
