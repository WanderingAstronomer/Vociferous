import logging

logger = logging.getLogger(__name__)


def get_optimal_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        # Optional dependency; fall back to CPU if unavailable or broken
        pass
    except (OSError, RuntimeError) as exc:
        logger.warning("CUDA detected but initialization failed: %s. Falling back to CPU.", exc)
    return "cpu"


def get_optimal_compute_type(device: str) -> str:
    if device == "cuda":
        return "float16"
    # For CPU, int8 is generally faster and good enough for Whisper
    return "int8"
