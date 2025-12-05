from __future__ import annotations

from pathlib import Path
from typing import Mapping

from chatterbug.domain.model import DEFAULT_MODEL_CACHE_DIR
from chatterbug.polish.base import NullPolisher, Polisher, PolisherConfig, RuleBasedPolisher
from chatterbug.polish.llama_cpp_polisher import LlamaCppPolisher, LlamaPolisherOptions

DEFAULT_POLISH_MODEL = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
DEFAULT_POLISH_REPO = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
DEFAULT_POLISH_CACHE = Path(DEFAULT_MODEL_CACHE_DIR) / "polish"


def build_polisher(config: PolisherConfig | None) -> Polisher:
    """Construct a polisher from config.

    The default is a no-op polisher to keep behavior unchanged unless the user
    opts in. A lightweight rule-based polisher is provided as a local-first
    baseline when enabled without a model.
    """

    if config is None or not config.enabled:
        return NullPolisher()

    model = config.model.strip() if config.model else None
    params: Mapping[str, str] | None = config.params
    if params is not None:
        params = {k: v for k, v in params.items() if v.strip()}

    if model is None:
        model = DEFAULT_POLISH_MODEL

    model_lower = model.lower()
    if model_lower in {"rule", "rule_based", "heuristic"}:
        return RuleBasedPolisher()

    if model_lower.endswith(".gguf"):
        return _build_llama_polisher(model, params)

    raise ValueError(f"Unknown polisher model '{model}'")


def _build_llama_polisher(model_name: str, params: Mapping[str, str] | None) -> Polisher:
    parsed_params = params or {}
    model_dir = Path(parsed_params.get("model_dir", DEFAULT_POLISH_CACHE))
    model_path_override = parsed_params.get("model_path")
    max_tokens = int(parsed_params.get("max_tokens", "128") or 128)
    temperature = float(parsed_params.get("temperature", "0.2") or 0.2)
    gpu_layers = int(parsed_params.get("gpu_layers", "0") or 0)
    ctx_len = int(parsed_params.get("context_length", "2048") or 2048)
    skip_download = parsed_params.get("skip_download", "false").lower() == "true"

    if model_path_override:
        path = Path(model_path_override)
    else:
        path = model_dir / model_name

    if not path.exists():
        if skip_download:
            raise ValueError(f"Polisher model not found at {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            import warnings
            from huggingface_hub import hf_hub_download  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError(
                "huggingface_hub is required to download polisher models; pip install .[polish]"
            ) from exc

        repo_id = parsed_params.get("repo_id", DEFAULT_POLISH_REPO)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, module="huggingface_hub")
            hf_hub_download(
                repo_id=repo_id,
                filename=model_name,
                local_dir=str(model_dir),
                local_dir_use_symlinks=False,
            )

    options = LlamaPolisherOptions(
        model_path=path,
        max_tokens=max_tokens,
        temperature=temperature,
        gpu_layers=gpu_layers,
        context_length=ctx_len,
    )
    return LlamaCppPolisher(options)
