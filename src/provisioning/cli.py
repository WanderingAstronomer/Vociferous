import logging
from pathlib import Path
from typing import Optional

import typer
from typing_extensions import Annotated

from src.core.config_manager import get_model_cache_dir
from src.core.model_registry import MODELS
from src.provisioning.core import provision_model, ProvisioningError
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


@app.command()
def list():
    """List available models and their status."""
    cache_dir = get_model_cache_dir()
    print(f"\nModel Directory: {cache_dir}\n")
    print(f"{'ID':<15} {'Name':<30} {'Status':<15}")
    print("-" * 60)

    for model_id, model in MODELS.items():
        model_dir = cache_dir / model.dir_name

        # Simple existence check
        is_ready = (model_dir / "model.bin").exists() and (
            model_dir / "config.json"
        ).exists()
        status = "INSTALLED" if is_ready else "MISSING"

        print(f"{model_id:<15} {model.name:<30} {status:<15}")
    print("\n")


@app.command()
def check():
    """Verify runtime environment dependencies."""
    installed, missing = check_dependencies()

    print("\n=== Dependency Status ===\n")
    if installed:
        print("✓ Installed:")
        for dep in installed:
            print(f"  - {dep}")

    if missing:
        print("\n✗ Missing:")
        for dep in missing:
            print(f"  - {dep}")
        print("\n" + get_missing_dependency_message(missing))
        raise typer.Exit(code=1)
    else:
        print("\n✓ Environment is ready for model conversion.")


@app.command()
def install(
    model_id: str = typer.Argument(
        ..., help="ID of the model to install (e.g., qwen4b)"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Re-install even if already present"
    ),
    source_dir: Annotated[
        Optional[Path],
        typer.Option(help="Use a local directory as source instead of downloading"),
    ] = None,
):
    """
    Provision a specific model. Downloads and converts weights.

    If --source-dir is provided, it must point to a directory containing a valid
    HuggingFace Transformers model (config.json, model.safetensors/bin, tokenizer.json).
    The tool will convert it to CTranslate2 format.
    """
    if model_id not in MODELS:
        logger.error(f"Unknown model ID: {model_id}")
        logger.info(f"Available models: {', '.join(MODELS.keys())}")
        raise typer.Exit(code=1)

    model = MODELS[model_id]
    cache_dir = get_model_cache_dir()
    target_dir = cache_dir / model.dir_name

    if target_dir.exists() and not force:
        # Quick check for artifacts
        if (target_dir / "model.bin").exists():
            logger.info(f"Model '{model_id}' appears to be installed at {target_dir}.")
            logger.info("Use --force to reinstall.")
            return

    # Check deps before starting
    _, missing = check_dependencies()
    if missing:
        logger.error("Missing dependencies for conversion.")
        print(get_missing_dependency_message(missing))
        raise typer.Exit(code=1)

    logger.info(f"Starting provisioning for {model_id}...")

    def on_progress(msg):
        print(f"-> {msg}")

    try:
        # TODO: Implement source_dir support in core.py if 'source_dir' is provided (Offline mode)
        # For now, if source_dir is passed, we might need a custom flow or update core.py
        # The core logic assumes 'download' handles obtaining source.
        # I'll update core.py later to allow skipping download if needed, but for now standard flow:

        if source_dir:
            # If a local source is provided, let core handle validation and conversion.
            logger.info(f"Using local source: {source_dir}")
            provision_model(
                model,
                cache_dir,
                progress_callback=on_progress,
                source_dir=source_dir,
            )
            logger.info("Provisioning complete (Offline).")
            return

        provision_model(model, cache_dir, progress_callback=on_progress)
        logger.info(f"Successfully installed {model_id}.")

    except ProvisioningError as e:
        logger.error(f"Failed: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.exception(e)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
