#!/usr/bin/env python3
"""
Refinement Setup Utility.

This script manages the heavy lifting for the SLM (Small Language Model) runtime:
1. Installs build dependencies (Torch, Transformers, AutoAWQ).
2. Downloads the base model (HuggingFace/ModelScope).
3. Converts the model to CTranslate2 format.
4. Generates a 'manifest.json' for the runtime to use.
5. Cleans up build dependencies to save space.

Usage:
    python scripts/setup_refinement.py --model qwen4b
"""

import argparse
import json
import logging
import platform
import shutil
import subprocess
import sys
import importlib.util
from pathlib import Path

# Add src to sys.path to allow importing model_registry
sys.path.append(str(Path(__file__).parent.parent / "src"))

from core.model_registry import MODELS, SupportedModel

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("setup_refinement")

# Constants
CACHE_DIR_NAME = "vociferous/models"
SOURCE_DIR_NAME = "slm-source-temp"


def get_cache_dir() -> Path:
    """Resolve XDG cache directory."""
    if platform.system() == "Windows":
        base = Path(sys.getenv("LOCALAPPDATA"))
        return base / CACHE_DIR_NAME
    else:
        # Linux / MacOS
        xdg_cache = sys.getenv("XDG_CACHE_HOME", str(Path.home() / ".cache"))
        return Path(xdg_cache) / CACHE_DIR_NAME


def install_dependencies():
    """Install build dependencies required for conversion."""
    logger.info("Installing build dependencies (Torch, Transformers, AutoAWQ)...")
    try:
        # 1. Install torch
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "torch",
                "--no-warn-script-location",
            ]
        )
        # 2. Install transformers & accel
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "transformers>=4.49.0",
                "sentencepiece",
                "accelerate",
                "--no-warn-script-location",
            ]
        )
        # 3. Install autoawq (no isolation to use installed torch)
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "autoawq",
                "--no-build-isolation",
                "--no-warn-script-location",
            ]
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install dependencies: {e}")
        sys.exit(1)


def uninstall_dependencies():
    """Remove heavy build dependencies."""
    logger.info("Cleaning up build dependencies...")
    try:
        subprocess.call(
            [
                sys.executable,
                "-m",
                "pip",
                "uninstall",
                "-y",
                "torch",
                "transformers",
                "sentencepiece",
                "autoawq",
            ]
        )
    except Exception as e:
        logger.warning(f"Cleanup failed: {e}")


def download_model(model: SupportedModel, temp_dir: Path) -> Path:
    """Download model using huggingface_hub."""
    logger.info(f"Downloading {model.repo_id}...")

    # We assume 'huggingface_hub' is in the base requirements or we install it.
    # It is usually a dev dependency or part of the larger suite.
    # For robust setup, we might want to pip install it too if missing.
    try:
        import huggingface_hub
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "huggingface_hub"]
        )
        import huggingface_hub

    return Path(
        huggingface_hub.snapshot_download(
            repo_id=model.repo_id,
            local_dir=str(temp_dir),
            revision=model.revision,
        )
    )


def convert_model(model: SupportedModel, source_path: Path, output_path: Path):
    """Run conversion using ctranslate2."""
    logger.info("Converting model to CTranslate2 format...")

    # Ensure CTranslate2 is valid
    if not importlib.util.find_spec("ctranslate2"):
        subprocess.check_call([sys.executable, "-m", "pip", "install", "ctranslate2"])

    # We invoke the converter via subprocess to avoid import hell if dependencies clash,
    # and because `ct2-transformers-converter` is a script entry point.

    cmd = [
        sys.executable,
        "-m",
        "ctranslate2.converters.transformers",
        "--model",
        str(source_path),
        "--output_dir",
        str(output_path),
        "--quantization",
        model.quantization,
        "--force",
    ]

    if model.quantization == "int4_awq":
        # Remove quantization flag for AWQ as it might be implicit or handled differently
        # Keeping simple for now based on original SLMService
        pass

    subprocess.check_call(cmd)


def generate_manifest(model: SupportedModel, output_path: Path):
    """Write manifest.json."""
    manifest = {
        "id": model.id,
        "name": model.name,
        "revision": model.revision,
        "quantization": model.quantization,
        "conversion_date": "Now",
    }
    with open(output_path / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)


def provision_model(model_id: str, base_dir: Path | None = None):
    """Main provisioning workflow."""
    if model_id not in MODELS:
        logger.error(f"Unknown model: {model_id}")
        sys.exit(1)

    model = MODELS[model_id]
    cache_root = base_dir or get_cache_dir()
    cache_root.mkdir(parents=True, exist_ok=True)

    temp_source = cache_root / SOURCE_DIR_NAME
    final_output = cache_root / model.dir_name

    logger.info(f"Provisioning {model.name} to {final_output}")

    try:
        install_dependencies()
        download_model(model, temp_source)
        convert_model(model, temp_source, final_output)

        # Copy tokenizer
        tokenizer_src = temp_source / "tokenizer.json"
        if tokenizer_src.exists():
            shutil.copy2(tokenizer_src, final_output / "tokenizer.json")

        generate_manifest(model, final_output)

        logger.info("Provisioning complete!")

    except Exception as e:
        logger.error(f"Provisioning failed: {e}")
        # Cleanup partial output
        if final_output.exists():
            shutil.rmtree(final_output)
        raise
    finally:
        if temp_source.exists():
            shutil.rmtree(temp_source)
        # We no longer uninstall dependencies automatically to prevent issues with other models
        # or runtime environments that expect a consistent virtual environment.


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Provision SLM models for Vociferous.")
    parser.add_argument(
        "--model",
        type=str,
        default="qwen4b",
        choices=MODELS.keys(),
        help="Model ID to provision",
    )
    args = parser.parse_args()

    provision_model(args.model)
