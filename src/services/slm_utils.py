import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

def get_gpu_memory_map() -> tuple[int, int] | None:
    """Get (total, free) GPU memory in MB via nvidia-smi."""
    try:
        # Check if nvidia-smi exists
        smi_path = shutil.which("nvidia-smi")
        if not smi_path:
            return None

        # Run nvidia-smi
        result = subprocess.check_output(
            [
                smi_path,
                "--query-gpu=memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ],
            encoding="utf-8",
        )
        # Parse first line (assuming single GPU or taking first)
        lines = result.strip().split("\n")
        if not lines:
            return None

        total_str, free_str = lines[0].split(",")
        return int(total_str), int(free_str)
    except Exception as e:
        logger.warning(f"Failed to query GPU memory: {e}")
        return None

def validate_model_artifacts(model_dir: Path) -> bool:
    """Check if all required model artifacts exist."""
    if not model_dir.exists():
        return False

    # CTranslate2 can produce vocabulary.json OR vocabulary.txt, check loosely
    has_vocab = (model_dir / "vocabulary.json").exists() or (
        model_dir / "vocabulary.txt"
    ).exists()
    has_model = (model_dir / "model.bin").exists()
    has_config = (model_dir / "config.json").exists()

    if not (has_vocab and has_model and has_config):
        logger.warning(f"Missing artifacts in {model_dir}")
        return False

    return True
