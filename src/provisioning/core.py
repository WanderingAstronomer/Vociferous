import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional, List

from src.core.model_registry import SupportedModel
from src.provisioning.requirements import check_dependencies

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None]  # Simple status message callback


class ProvisioningError(Exception):
    """Raised when provisioning fails."""

    pass


def get_conversion_script_command(
    source_dir: Path, output_dir: Path, model: SupportedModel
) -> List[str]:
    """
    Construct the ctranslate2 conversion command.
    Heuristically finds the executable or falls back to python module.
    """
    script_name = "ct2-transformers-converter"
    script_path = None
    possible_paths = [
        Path(sys.executable).parent / script_name,
        Path(sys.executable).parent
        / "Scripts"
        / f"{script_name}.exe",  # Windows logic just in case
    ]
    for p in possible_paths:
        if p.exists():
            script_path = str(p)
            break

    if not script_path:
        script_path = script_name

    # Check for script existence in PATH or fallback to module
    use_module = False
    if script_path == script_name:
        # Check if it's in PATH
        if not shutil.which(script_name):
            use_module = True

    cmd_prefix = []
    if use_module:
        cmd_prefix = [sys.executable, "-m", "ctranslate2.converters.transformers"]
    else:
        cmd_prefix = [script_path]

    cmd_args = [
        "--model",
        str(source_dir),
        "--output_dir",
        str(output_dir),
        "--force",
    ]

    # Special handling for quantization args if needed
    if model.quantization != "int4_awq":
        cmd_args.extend(
            [
                "--quantization",
                model.quantization,
            ]
        )

    return cmd_prefix + cmd_args


def convert_model(
    model: SupportedModel,
    source_dir: Path,
    output_dir: Path,
    progress_callback: Optional[ProgressCallback] = None,
) -> None:
    """
    Run the ctranslate2 conversion process.
    """
    if progress_callback:
        progress_callback(f"Converting model {model.id} (this may take a while)...")

    logger.info(f"Converting model from {source_dir} to {output_dir}")

    # Pre-flight check
    _, missing = check_dependencies(["ctranslate2", "transformers", "torch"])
    if missing:
        raise ProvisioningError(f"Cannot convert: Missing dependencies {missing}")

    cmd = get_conversion_script_command(source_dir, output_dir, model)

    try:
        # Run conversion
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        # Retry with module if we weren't already using it and it failed?
        # The get_conversion_script_command logic tries to be smart, but let's stick to the content of the original code
        # The original code had a specific 'except' block to fallback to module.

        # Check if we already tried module
        is_module_call = (cmd[1] == "-m") if len(cmd) > 1 else False

        if not is_module_call:
            logger.warning(
                "Script execution failed, falling back to python module execution..."
            )
            # Reconstruct command forcing module
            # Re-build args only
            current_cmd_str = " ".join(cmd)
            # Extract args after --model
            try:
                idx = cmd.index("--model")
                args_only = cmd[idx:]

                fallback_cmd = [
                    sys.executable,
                    "-m",
                    "ctranslate2.converters.transformers",
                ] + args_only
                subprocess.check_call(fallback_cmd)
                return  # Success on fallback
            except ValueError:
                raise ProvisioningError(
                    f"Could not parse failed command args to retry: {current_cmd_str}"
                ) from e
            except subprocess.CalledProcessError as e2:
                raise ProvisioningError(
                    f"Conversion failed (module fallback): {e2}"
                ) from e2

        raise ProvisioningError(f"Conversion failed: {e}") from e


def download_model_source(
    model: SupportedModel,
    destination_dir: Path,
    progress_callback: Optional[ProgressCallback] = None,
) -> Path:
    """
    Download the raw model weights from HF or ModelScope.
    Returns the path to the downloaded directory.
    """
    if progress_callback:
        progress_callback(f"Downloading source: {model.repo_id}...")

    try:
        if model.source == "ModelScope":
            from modelscope.hub.snapshot_download import snapshot_download as ms_dl

            logger.info(f"Using ModelScope to download {model.repo_id}")
            # ModelScope download logic
            # output_dir is cache_dir in original code, returning a path
            # We want to force it to destination_dir if possible, or move it?
            # Original: cache_dir=str(self.cache_dir) -> ms_dl returns a specific path inside named usually/
            # If we want to strictly control 'destination_dir' as the source root, we need to be careful.
            # Original: source_dir = Path(downloaded_path)

            # For ModelScope, checking docs/original code: it manages its own cache structure usually.
            # But the original code passed `cache_dir=str(self.cache_dir)` and got a path back.

            downloaded = ms_dl(
                model_id=model.repo_id,
                cache_dir=str(
                    destination_dir.parent
                ),  # Use parent so it creates the folder inside?
                revision=model.revision,
            )
            return Path(downloaded)

        else:
            from huggingface_hub import snapshot_download as hf_dl

            logger.info(f"Using HuggingFace to download {model.repo_id}")

            hf_dl(
                repo_id=model.repo_id,
                local_dir=destination_dir,
                revision=model.revision,
            )
            return destination_dir

    except ImportError as e:
        raise ProvisioningError(f"Download library missing: {e}")
    except Exception as e:
        raise ProvisioningError(f"Download failed: {e}")


def _validate_source_dir(source_dir: Path) -> None:
    """Validate that a local source directory looks like a Transformers model.

    Raises ProvisioningError if validation fails.
    """
    required_files = ["config.json"]
    model_candidates = ["model.safetensors", "pytorch_model.bin", "model.bin"]

    missing = []
    for f in required_files:
        if not (source_dir / f).exists():
            missing.append(f)

    found_model = any((source_dir / m).exists() for m in model_candidates)
    if not found_model:
        missing.append("one of: " + ", ".join(model_candidates))

    if missing:
        raise ProvisioningError(
            f"Invalid source directory: missing {', '.join(missing)}. "
            "Source must contain a Transformers model layout (config.json and model file)."
        )


def provision_model(
    model: SupportedModel,
    cache_root: Path,
    progress_callback: Optional[ProgressCallback] = None,
    source_dir: Optional[Path] = None,
) -> bool:
    """
    Orchestrate the full provisioning flow: Download -> Convert -> Install Artifacts.

    Args:
        model: The model definition.
        cache_root: The root directory where 'models' and temp files live.
                   The model will represent a subdir internally usually?
                   In registry: model.dir_name is the target folder name.
        source_dir: Optional local source directory to use instead of downloading (offline).
    """
    # Define paths
    final_model_dir = cache_root / model.dir_name
    source_temp_dir = cache_root / "slm-source-temp"

    # Use a dedicated temporary output dir for conversion to ensure atomic install
    import hashlib
    import json
    import os
    import uuid

    temp_install_dir = cache_root / f"{model.dir_name}.tmp-{uuid.uuid4().hex}"

    # Clean start for temp
    if source_temp_dir.exists():
        shutil.rmtree(source_temp_dir, ignore_errors=True)
    if temp_install_dir.exists():
        shutil.rmtree(temp_install_dir, ignore_errors=True)

    downloaded_source = None
    try:
        # 1. Obtain source (download or use provided)
        if source_dir:
            source_dir = Path(source_dir)
            _validate_source_dir(source_dir)
            downloaded_source = source_dir
            if progress_callback:
                progress_callback(f"Using local source: {source_dir}")
        else:
            downloaded_source = download_model_source(
                model, source_temp_dir, progress_callback=progress_callback
            )

        # 2. Convert into temporary install dir
        temp_install_dir.mkdir(parents=True)

        convert_model(
            model,
            downloaded_source,
            temp_install_dir,
            progress_callback=progress_callback,
        )

        # 3. Artifacts (tokenizer.json) - copy into temp dir
        logger.info("Copying tokenizer artifacts into temp install dir...")
        source_tokenizer = downloaded_source / "tokenizer.json"
        if source_tokenizer.exists():
            shutil.copy2(source_tokenizer, temp_install_dir / "tokenizer.json")
        else:
            logger.warning(
                "tokenizer.json not found in source. If you have a custom tokenizer, ensure tokenization artifacts are present."
            )

        # 4. Validate artifacts in temp dir and write manifest with checksums
        def _sha256_hex(p: Path) -> str:
            h = hashlib.sha256()
            with p.open("rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()

        manifest = {
            "model_id": model.id,
            "revision": getattr(model, "revision", ""),
            "created_at": int(__import__("time").time()),
            "files": {},
        }

        # Files to include if they exist
        candidate_files = ["model.bin", "config.json", "tokenizer.json", "vocabulary.json", "vocabulary.txt"]
        for fname in candidate_files:
            p = temp_install_dir / fname
            if p.exists():
                manifest["files"][fname] = _sha256_hex(p)

        # Require model.bin and config.json at minimum
        if "model.bin" not in manifest["files"] or "config.json" not in manifest["files"]:
            raise ProvisioningError("Converted artifacts incomplete: missing model.bin or config.json")

        # Write manifest atomically into temp_install_dir
        manifest_path = temp_install_dir / "manifest.json"
        tmp_manifest = manifest_path.with_suffix(".tmp")
        with tmp_manifest.open("w", encoding="utf-8") as mf:
            json.dump(manifest, mf, indent=2)
            mf.flush()
            os.fsync(mf.fileno())
        os.replace(str(tmp_manifest), str(manifest_path))

        # 5. Atomic install: move temp_install_dir into final_model_dir
        # If final exists, remove it first to ensure replace succeeds
        if final_model_dir.exists():
            shutil.rmtree(final_model_dir, ignore_errors=True)

        os.replace(str(temp_install_dir), str(final_model_dir))

        # fsync parent dir to make the rename durable (best-effort)
        try:
            dirfd = os.open(str(cache_root), os.O_DIRECTORY)
            os.fsync(dirfd)
            os.close(dirfd)
        except Exception:
            logger.exception("Failed to fsync cache directory after installing model")

        if progress_callback:
            progress_callback("Provisioning complete.")

        return True

    except Exception as e:
        logger.error(f"Provisioning failed: {e}")
        # Clean up partial results
        # Remove final dir if it's present (shouldn't be on failure)
        if final_model_dir.exists():
            shutil.rmtree(final_model_dir, ignore_errors=True)
        # Remove temp install dir if present
        if temp_install_dir.exists():
            shutil.rmtree(temp_install_dir, ignore_errors=True)
        raise
    finally:
        # Cleanup source if we downloaded it into the temp dir
        if source_dir is None and downloaded_source is not None:
            # downloaded_source may be equal to source_temp_dir or a path inside it
            if (
                downloaded_source == source_temp_dir
                or source_temp_dir in downloaded_source.parents
            ):
                shutil.rmtree(source_temp_dir, ignore_errors=True)
            elif downloaded_source.is_dir():
                shutil.rmtree(downloaded_source, ignore_errors=True)
