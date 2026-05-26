"""
Model Provisioning Core — Download CTranslate2 model directories from HuggingFace.

v5.0: CT2 models are directories (model.bin + config.json + tokenizer files).
ASR and SLM provisioning uses snapshot_download(). VAD stays as single-file.
"""

import hashlib
import logging
from pathlib import Path
from typing import Callable

from src.core.model_registry import ASRModel, SLMModel, VADModel

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None]

_SHA256_BUF_SIZE = 1 << 18  # 256 KiB read chunks for hashing


class ProvisioningError(Exception):
    """Raised when provisioning fails."""


class IntegrityError(ProvisioningError):
    """Raised when a downloaded file fails SHA-256 verification."""


def _compute_sha256(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file without slurping it all into RAM."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_SHA256_BUF_SIZE):
            h.update(chunk)
    return h.hexdigest()


def _verify_integrity(path: Path, expected_sha256: str) -> None:
    """Verify file integrity against an expected SHA-256 hash.

    Deletes the file and raises IntegrityError on mismatch.
    """
    actual = _compute_sha256(path)
    if actual != expected_sha256:
        path.unlink(missing_ok=True)
        raise IntegrityError(
            f"SHA-256 mismatch for {path.name}: expected {expected_sha256}, got {actual}. Corrupted file removed."
        )


def download_model_file(
    repo_id: str,
    filename: str,
    target_dir: Path,
    progress_callback: ProgressCallback | None = None,
    expected_sha256: str | None = None,
) -> Path:
    """
    Download a single model file from a HuggingFace repository.

    Used for VAD (ONNX single-file models). CT2 models use download_model_directory().

    Args:
        repo_id: HuggingFace repo (e.g. 'deepghs/silero-vad-onnx').
        filename: File to download (e.g. 'silero_vad.onnx').
        target_dir: Local directory for the downloaded file.
        progress_callback: Status callback (called with message strings).
        expected_sha256: If provided, verify the file after download.

    Returns:
        Path to the downloaded file.

    Raises:
        ProvisioningError: On download failure.
        IntegrityError: On SHA-256 mismatch (file is deleted automatically).
    """
    from huggingface_hub import hf_hub_download

    target_dir.mkdir(parents=True, exist_ok=True)

    if progress_callback:
        progress_callback(f"Downloading {filename} from {repo_id}...")

    try:
        downloaded = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=str(target_dir),
        )
        result = Path(downloaded)
        logger.info("Downloaded %s -> %s", filename, downloaded)

        # --- SHA-256 integrity check ---
        if expected_sha256:
            if progress_callback:
                progress_callback(f"Verifying integrity of {filename}...")
            _verify_integrity(result, expected_sha256)
            logger.info("SHA-256 verified for %s", filename)

        if progress_callback:
            progress_callback(f"Downloaded {filename} successfully.")

        return result

    except IntegrityError:
        raise
    except Exception as e:
        raise ProvisioningError(f"Failed to download {filename} from {repo_id}: {e}") from e


def download_model_directory(
    repo_id: str,
    target_dir: Path,
    progress_callback: ProgressCallback | None = None,
    expected_sha256: str | None = None,
    model_file: str = "model.bin",
) -> Path:
    """
    Download a CTranslate2 model directory from a HuggingFace repository.

    CT2 models are directories containing model.bin, config.json, tokenizer files, etc.
    Uses snapshot_download() to fetch the entire repo as a local directory.

    Args:
        repo_id: HuggingFace repo (e.g. 'Systran/faster-whisper-large-v3').
        target_dir: Parent directory where the model dir will be created.
        progress_callback: Status callback (called with message strings).
        expected_sha256: If provided, verify model.bin after download.
        model_file: Name of the primary model binary for verification (default: 'model.bin').

    Returns:
        Path to the downloaded model directory.

    Raises:
        ProvisioningError: On download failure.
        IntegrityError: On SHA-256 mismatch.
    """
    from huggingface_hub import snapshot_download

    target_dir.mkdir(parents=True, exist_ok=True)

    # Use the repo name (after '/') as the local directory name
    local_dir_name = repo_id.split("/")[-1]
    local_dir = target_dir / local_dir_name

    if progress_callback:
        progress_callback(f"Downloading CT2 model from {repo_id}...")

    try:
        downloaded_path = snapshot_download(
            repo_id=repo_id,
            local_dir=str(local_dir),
        )
        result = Path(downloaded_path)
        logger.info("Downloaded CT2 model directory %s -> %s", repo_id, result)

        model_bin = result / model_file
        if not model_bin.exists():
            raise ProvisioningError(
                f"Downloaded CT2 model from {repo_id} is missing required file {model_file} in {result}."
            )

        # --- SHA-256 integrity check on the primary model binary ---
        if expected_sha256:
            if progress_callback:
                progress_callback(f"Verifying integrity of {model_file}...")
            _verify_integrity(model_bin, expected_sha256)
            logger.info("SHA-256 verified for %s/%s", repo_id, model_file)

        if progress_callback:
            progress_callback(f"Downloaded {repo_id} successfully.")

        return result

    except IntegrityError:
        raise
    except ProvisioningError:
        raise
    except Exception as e:
        raise ProvisioningError(f"Failed to download CT2 model from {repo_id}: {e}") from e


def provision_asr_model(
    model: ASRModel,
    cache_dir: Path,
    progress_callback: ProgressCallback | None = None,
) -> Path:
    """
    Provision an ASR (CTranslate2 Whisper) model.

    Downloads the CT2 model directory from the model's HuggingFace repo.
    """
    return download_model_directory(
        repo_id=model.repo,
        target_dir=cache_dir,
        progress_callback=progress_callback,
        expected_sha256=model.sha256,
        model_file=model.model_file,
    )


def provision_slm_model(
    model: SLMModel,
    cache_dir: Path,
    progress_callback: ProgressCallback | None = None,
) -> Path:
    """
    Provision an SLM (CTranslate2 Generator) model.

    Downloads the CT2 model directory from the model's HuggingFace repo.
    """
    return download_model_directory(
        repo_id=model.repo,
        target_dir=cache_dir,
        progress_callback=progress_callback,
        expected_sha256=model.sha256,
        model_file=model.model_file,
    )


def provision_vad_model(
    model: VADModel,
    cache_dir: Path,
    progress_callback: ProgressCallback | None = None,
) -> Path:
    """
    Provision the Silero VAD ONNX model.

    Downloads the ONNX file from the model's HuggingFace repo.
    """
    return download_model_file(
        repo_id=model.repo,
        filename=model.filename,
        target_dir=cache_dir,
        progress_callback=progress_callback,
        expected_sha256=model.sha256,
    )
