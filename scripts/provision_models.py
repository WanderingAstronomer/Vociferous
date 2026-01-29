#!/usr/bin/env python3
"""
Model Provisioning CLI Tool

This script provides a command-line interface for downloading and converting
SLM models used by Vociferous for text refinement.

Run this script BEFORE starting Vociferous to ensure all models are ready
for offline use.

Usage:
    python scripts/provision_models.py --list          # List available models
    python scripts/provision_models.py --model qwen4b  # Provision a specific model
    python scripts/provision_models.py --all           # Provision all models
    python scripts/provision_models.py --check         # Check dependency status
"""

import argparse
import importlib.util
import logging
import shutil
import subprocess
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def check_dependencies() -> tuple[list[str], list[str]]:
    """Check which dependencies are installed and which are missing."""
    required = ["ctranslate2", "transformers", "torch", "huggingface_hub", "modelscope"]
    installed = []
    missing = []
    
    for dep in required:
        if importlib.util.find_spec(dep) is not None:
            installed.append(dep)
        else:
            missing.append(dep)
    
    return installed, missing


def print_dependency_status():
    """Print the status of required dependencies."""
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
        print("\nTo install missing dependencies, run:")
        print(f"  pip install {' '.join(missing)}")
        print("\nOr install all dependencies:")
        print("  pip install -r requirements.txt")
    else:
        print("\n✓ All dependencies are installed!")
    
    return len(missing) == 0


def list_models():
    """List available models and their status."""
    try:
        from src.core.config_manager import get_model_cache_dir
        from src.core.model_registry import MODELS
    except ImportError as e:
        logger.error(f"Failed to import model registry: {e}")
        logger.error("Make sure you're running from the project root directory.")
        return
    
    cache_dir = get_model_cache_dir()
    
    print("\n=== Available Models ===\n")
    print(f"Cache directory: {cache_dir}\n")
    
    for model_id, model in MODELS.items():
        model_dir = cache_dir / model.dir_name
        
        # Check if model is provisioned
        has_vocab = (model_dir / "vocabulary.json").exists() or (model_dir / "vocabulary.txt").exists()
        has_model = (model_dir / "model.bin").exists()
        has_config = (model_dir / "config.json").exists()
        is_ready = has_vocab and has_model and has_config
        
        status = "✓ Ready" if is_ready else "✗ Not provisioned"
        
        print(f"  [{model_id}] {model.name}")
        print(f"      Source: {model.source} ({model.repo_id})")
        print(f"      VRAM Required: ~{model.required_vram_mb} MB")
        print(f"      Quantization: {model.quantization}")
        print(f"      Status: {status}")
        print()


def provision_model(model_id: str) -> bool:
    """Provision a specific model."""
    try:
        from src.core.config_manager import get_model_cache_dir
        from src.core.model_registry import MODELS
    except ImportError as e:
        logger.error(f"Failed to import model registry: {e}")
        return False
    
    if model_id not in MODELS:
        logger.error(f"Unknown model ID: {model_id}")
        logger.error(f"Available models: {', '.join(MODELS.keys())}")
        return False
    
    # Check dependencies first
    _, missing = check_dependencies()
    model = MODELS[model_id]
    
    # Check model-specific dependencies
    if model.source == "ModelScope" and "modelscope" in missing:
        logger.error("modelscope is required for this model but not installed.")
        logger.error("Install it with: pip install modelscope")
        return False
    
    core_missing = [d for d in missing if d not in ["modelscope"]]
    if core_missing:
        logger.error(f"Missing required dependencies: {', '.join(core_missing)}")
        logger.error("Install them with: pip install " + " ".join(core_missing))
        return False
    
    cache_dir = get_model_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    model_dir = cache_dir / model.dir_name
    source_dir = cache_dir / "slm-source-temp"
    
    # Check if already provisioned
    has_vocab = (model_dir / "vocabulary.json").exists() or (model_dir / "vocabulary.txt").exists()
    has_model = (model_dir / "model.bin").exists()
    has_config = (model_dir / "config.json").exists()
    
    if has_vocab and has_model and has_config:
        logger.info(f"Model {model.name} is already provisioned.")
        return True
    
    logger.info(f"Provisioning model: {model.name}")
    logger.info(f"Source: {model.source} / {model.repo_id}")
    
    try:
        # 1. Download source model
        logger.info("Downloading source model...")
        
        if model.source == "ModelScope":
            from modelscope.hub.snapshot_download import snapshot_download as ms_dl
            downloaded_path = ms_dl(
                model_id=model.repo_id,
                cache_dir=str(cache_dir),
                revision=model.revision,
            )
            source_dir = Path(downloaded_path)
        else:
            from huggingface_hub import snapshot_download as hf_dl
            hf_dl(
                repo_id=model.repo_id,
                local_dir=source_dir,
                revision=model.revision,
            )
        
        logger.info("Download complete.")
        
        # 2. Convert model
        logger.info("Converting model to CTranslate2 format...")
        
        script_name = "ct2-transformers-converter"
        script_path = None
        possible_paths = [
            Path(sys.executable).parent / script_name,
            Path(sys.executable).parent / "Scripts" / f"{script_name}.exe",
        ]
        for p in possible_paths:
            if p.exists():
                script_path = str(p)
                break
        
        if not script_path:
            script_path = script_name
        
        cmd_args = [
            "--model", str(source_dir),
            "--output_dir", str(model_dir),
            "--quantization", model.quantization,
            "--force",
        ]
        
        # Skip quantization arg for int4_awq
        if model.quantization == "int4_awq":
            cmd_args = [
                "--model", str(source_dir),
                "--output_dir", str(model_dir),
                "--force",
            ]
        
        try:
            cmd = [script_path] + cmd_args
            subprocess.check_call(cmd)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.info("Script execution failed, trying module...")
            cmd = [sys.executable, "-m", "ctranslate2.converters.transformers"] + cmd_args
            subprocess.check_call(cmd)
        
        logger.info("Conversion complete.")
        
        # 3. Copy tokenizer
        logger.info("Copying tokenizer artifacts...")
        source_tokenizer = source_dir / "tokenizer.json"
        if source_tokenizer.exists():
            shutil.copy2(source_tokenizer, model_dir / "tokenizer.json")
        else:
            logger.warning("tokenizer.json not found in source.")
        
        # 4. Clean up source
        logger.info("Cleaning up temporary files...")
        if source_dir.exists() and "slm-source-temp" in str(source_dir):
            shutil.rmtree(source_dir, ignore_errors=True)
        
        logger.info(f"✓ Model {model.name} provisioned successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Provisioning failed: {e}")
        # Clean up on failure
        if model_dir.exists():
            shutil.rmtree(model_dir, ignore_errors=True)
        return False
    finally:
        # Always clean up source
        if source_dir.exists() and "slm-source-temp" in str(source_dir):
            shutil.rmtree(source_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(
        description="Vociferous Model Provisioning Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s --check              Check if dependencies are installed
    %(prog)s --list               List available models and their status
    %(prog)s --model qwen4b       Provision the Qwen 4B model
    %(prog)s --all                Provision all available models
""",
    )
    
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available models and their provisioning status",
    )
    parser.add_argument(
        "--check", "-c",
        action="store_true",
        help="Check if required dependencies are installed",
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        help="Model ID to provision (e.g., qwen4b)",
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Provision all available models",
    )
    
    args = parser.parse_args()
    
    if not any([args.list, args.check, args.model, args.all]):
        parser.print_help()
        return 0
    
    if args.check:
        success = print_dependency_status()
        return 0 if success else 1
    
    if args.list:
        list_models()
        return 0
    
    if args.model:
        success = provision_model(args.model)
        return 0 if success else 1
    
    if args.all:
        try:
            from src.core.model_registry import MODELS
        except ImportError as e:
            logger.error(f"Failed to import model registry: {e}")
            return 1
        
        all_success = True
        for model_id in MODELS.keys():
            if not provision_model(model_id):
                all_success = False
        
        return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())
