"""
Runtime dependency checking for Vociferous v4.0.
"""

import importlib.util
import sys
from typing import List, Tuple

# Core runtime dependencies (v4.0 — GGUF/GGML stack)
REQUIRED_DEPENDENCIES = [
    "pywhispercpp",
    "llama_cpp",
    "numpy",
    "sounddevice",
    "webrtcvad",
    "huggingface_hub",
]


def check_dependencies(
    dependencies: List[str] | None = None,
) -> Tuple[List[str], List[str]]:
    """
    Check availability of specified python packages.

    Returns:
        Tuple of (installed_packages, missing_packages)
    """
    if dependencies is None:
        dependencies = REQUIRED_DEPENDENCIES

    installed = []
    missing = []

    for dep in dependencies:
        if importlib.util.find_spec(dep) is not None:
            installed.append(dep)
        else:
            missing.append(dep)

    return installed, missing


def get_missing_dependency_message(missing: List[str]) -> str:
    """Generate a helpful error message for missing dependencies."""
    if not missing:
        return ""

    missing_str = ", ".join(missing)
    return (
        f"Missing runtime dependencies: {missing_str}.\n\n"
        "Please install the missing dependencies:\n\n"
        f"  {sys.executable} -m pip install {' '.join(missing)}\n\n"
        "Or re-run the full installation:\n"
        "  pip install -r requirements.txt"
    )


def verify_environment_integrity() -> None:
    """
    Strict environment check. Raises RuntimeError if dependencies are missing.
    """
    _, missing = check_dependencies()
    if missing:
        raise RuntimeError(get_missing_dependency_message(missing))
