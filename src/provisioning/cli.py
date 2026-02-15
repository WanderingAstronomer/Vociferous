"""
Vociferous Model Provisioning CLI.

v4.0: Downloads pre-quantized GGUF/GGML models directly from HuggingFace.
No more CTranslate2 conversion pipeline.
"""

import logging

import typer

from src.core.resource_manager import ResourceManager
from src.core.model_registry import ASR_MODELS, SLM_MODELS, get_asr_model, get_slm_model
from src.provisioning.core import (
    provision_asr_model,
    provision_slm_model,
    ProvisioningError,
)
from src.provisioning.requirements import (
    check_dependencies,
    get_missing_dependency_message,
)

# Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("provision-cli")

app = typer.Typer(help="Vociferous Model Provisioning Tool", add_completion=False)


def _get_cache_dir():
    return ResourceManager.get_user_cache_dir("models")


@app.command("list")
def list_models():
    """List available models and their status."""
    cache_dir = _get_cache_dir()
    print(f"\nModel Directory: {cache_dir}\n")

    print("=== ASR Models (whisper.cpp GGML) ===")
    print(f"{'ID':<25} {'Name':<30} {'Size':<10} {'Status':<10}")
    print("-" * 75)
    for model_id, model in ASR_MODELS.items():
        path = cache_dir / model.filename
        status = "INSTALLED" if path.exists() else "MISSING"
        print(f"{model_id:<25} {model.name:<30} {model.size_mb}MB{'':<5} {status:<10}")

    print(f"\n=== SLM Models (llama.cpp GGUF) ===")
    print(f"{'ID':<25} {'Name':<30} {'Size':<10} {'Status':<10}")
    print("-" * 75)
    for model_id, model in SLM_MODELS.items():
        path = cache_dir / model.filename
        status = "INSTALLED" if path.exists() else "MISSING"
        print(f"{model_id:<25} {model.name:<30} {model.size_mb}MB{'':<5} {status:<10}")
    print()


@app.command()
def check():
    """Verify runtime environment dependencies."""
    installed, missing = check_dependencies()

    print("\n=== Dependency Status ===\n")
    if installed:
        print("Installed:")
        for dep in installed:
            print(f"  + {dep}")

    if missing:
        print("\nMissing:")
        for dep in missing:
            print(f"  - {dep}")
        print("\n" + get_missing_dependency_message(missing))
        raise typer.Exit(code=1)
    else:
        print("\nEnvironment is ready.")


@app.command()
def install(
    model_id: str = typer.Argument(
        ..., help="ID of the model to install (e.g., large-v3-turbo-q5_0, qwen4b)"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Re-download even if already present"
    ),
):
    """Download and install a specific model."""
    cache_dir = _get_cache_dir()

    # Determine if it's an ASR or SLM model
    asr_model = get_asr_model(model_id)
    slm_model = get_slm_model(model_id)

    if asr_model is None and slm_model is None:
        all_ids = list(ASR_MODELS.keys()) + list(SLM_MODELS.keys())
        logger.error("Unknown model ID: %s", model_id)
        logger.info("Available models: %s", ", ".join(all_ids))
        raise typer.Exit(code=1)

    def on_progress(msg: str):
        print(f"-> {msg}")

    try:
        if asr_model:
            target = cache_dir / asr_model.filename
            if target.exists() and not force:
                logger.info("Model '%s' already installed at %s", model_id, target)
                logger.info("Use --force to re-download.")
                return
            provision_asr_model(asr_model, cache_dir, progress_callback=on_progress)
        else:
            assert slm_model is not None
            target = cache_dir / slm_model.filename
            if target.exists() and not force:
                logger.info("Model '%s' already installed at %s", model_id, target)
                logger.info("Use --force to re-download.")
                return
            provision_slm_model(slm_model, cache_dir, progress_callback=on_progress)

        logger.info("Successfully installed %s.", model_id)

    except ProvisioningError as e:
        logger.error("Failed: %s", e)
        raise typer.Exit(code=1)
    except Exception as e:
        logger.exception(e)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
