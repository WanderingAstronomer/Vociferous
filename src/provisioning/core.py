"""
Model Provisioning Core — Download GGUF/GGML models from HuggingFace.

v4.0: No more CTranslate2 conversion pipeline. Models are pre-quantized
GGUF/GGML files downloaded directly from HuggingFace repos.
"""

import logging
from pathlib import Path
from typing import Callable, Optional

from src.core.model_registry import ASRModel, SLMModel

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None]


class ProvisioningError(Exception):
    """Raised when provisioning fails."""


def download_model_file(
    repo_id: str,
    filename: str,
    target_dir: Path,
    progress_callback: Optional[ProgressCallback] = None,
) -> Path:
    """
    Download a single model file from a HuggingFace repository.

    Args:
        repo_id: HuggingFace repo (e.g. 'ggerganov/whisper.cpp').
        filename: File to download (e.g. 'ggml-large-v3-turbo-q5_0.bin').
        target_dir: Local directory for the downloaded file.
        progress_callback: Optional status callback.

    Returns:
        Path to the downloaded file.
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
        logger.info("Downloaded %s -> %s", filename, downloaded)

        if progress_callback:
            progress_callback(f"Downloaded {filename} successfully.")

        return Path(downloaded)

    except Exception as e:
        raise ProvisioningError(f"Failed to download {filename} from {repo_id}: {e}") from e


def provision_asr_model(
    model: ASRModel,
    cache_dir: Path,
    progress_callback: Optional[ProgressCallback] = None,
) -> Path:
    """
    Provision an ASR (whisper.cpp) model.

    Downloads the GGML file from the model's HuggingFace repo.
    """
    return download_model_file(
        repo_id=model.repo,
        filename=model.filename,
        target_dir=cache_dir,
        progress_callback=progress_callback,
    )


def provision_slm_model(
    model: SLMModel,
    cache_dir: Path,
    progress_callback: Optional[ProgressCallback] = None,
) -> Path:
    """
    Provision an SLM (llama.cpp) model.

    Downloads the GGUF file from the model's HuggingFace repo.
    """
    return download_model_file(
        repo_id=model.repo,
        filename=model.filename,
        target_dir=cache_dir,
        progress_callback=progress_callback,
    )
