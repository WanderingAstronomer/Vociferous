def get_optimal_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except (ImportError, OSError, RuntimeError):
        # Optional dependency; fall back to CPU if unavailable or broken
        pass
    return "cpu"

def get_optimal_compute_type(device: str) -> str:
    if device == "cuda":
        return "float16"
    # For CPU, int8 is generally faster and good enough for Whisper
    return "int8"
