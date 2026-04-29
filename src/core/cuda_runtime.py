from __future__ import annotations

import ctypes
import importlib.util
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_LINUX_REQUIRED_CUDA_SONAMES = (
    "libcudart.so.12",
    "libcublasLt.so.12",
    "libcublas.so.12",
    "libcudnn.so.9",
)
_LINUX_LOADED_CUDA_LIBRARIES: dict[str, object] = {}


@dataclass(frozen=True, slots=True)
class CudaRuntimeStatus:
    driver_detected: bool = False
    cuda_available: bool = False
    cuda_device_count: int = 0
    gpu_name: str = ""
    vram_total_mb: int = 0
    vram_used_mb: int = 0
    vram_free_mb: int = 0
    detail: str = ""


def _linux_dlopen_mode() -> int:
    return getattr(os, "RTLD_GLOBAL", 0) | getattr(os, "RTLD_NOW", 0)


def _get_vendored_linux_cuda_dirs() -> list[Path]:
    spec = importlib.util.find_spec("nvidia")
    if spec is None or spec.submodule_search_locations is None:
        return []

    directories: list[Path] = []
    seen: set[str] = set()
    for nvidia_root in spec.submodule_search_locations:
        base = Path(nvidia_root)
        for pattern in ("*/lib", "*/lib64"):
            for candidate in sorted(base.glob(pattern)):
                if not candidate.is_dir():
                    continue

                resolved = str(candidate.resolve())
                if resolved in seen:
                    continue

                seen.add(resolved)
                directories.append(candidate)

    return directories


def _load_linux_cuda_library(load_target: str, *, cache_key: str) -> None:
    if cache_key in _LINUX_LOADED_CUDA_LIBRARIES:
        return

    _LINUX_LOADED_CUDA_LIBRARIES[cache_key] = ctypes.CDLL(load_target, mode=_linux_dlopen_mode())


def _find_vendored_linux_cuda_library(soname: str) -> Path | None:
    for lib_dir in _get_vendored_linux_cuda_dirs():
        candidate = lib_dir / soname
        if candidate.exists():
            return candidate

    return None


def _ensure_linux_cuda_library(soname: str) -> tuple[str | None, str | None]:
    if soname in _LINUX_LOADED_CUDA_LIBRARIES:
        return None, None

    try:
        _load_linux_cuda_library(soname, cache_key=soname)
        return None, None
    except OSError as direct_exc:
        candidate = _find_vendored_linux_cuda_library(soname)
        if candidate is None:
            return None, f"{soname} is not loadable: {direct_exc}"

        cache_key = str(candidate.resolve())
        if cache_key in _LINUX_LOADED_CUDA_LIBRARIES:
            return None, None

        try:
            _load_linux_cuda_library(cache_key, cache_key=cache_key)
            return candidate.name, None
        except OSError as vendored_exc:
            return None, f"{soname} is not loadable: {vendored_exc}"


def _probe_linux_cuda_runtime() -> tuple[list[str], list[str]]:
    loaded: list[str] = []
    failures: list[str] = []
    for soname in _LINUX_REQUIRED_CUDA_SONAMES:
        loaded_name, error = _ensure_linux_cuda_library(soname)
        if loaded_name:
            loaded.append(loaded_name)
        if error:
            failures.append(error)

    return loaded, failures


def prepare_cuda_runtime() -> str:
    """Best-effort preload of vendored CUDA shared libraries on Linux."""
    if not sys.platform.startswith("linux"):
        return ""

    loaded, _ = _probe_linux_cuda_runtime()
    if not loaded:
        return ""

    return f"Preloaded vendored CUDA libs: {', '.join(loaded)}"


def detect_cuda_runtime() -> CudaRuntimeStatus:
    """Return whether CTranslate2 can actually use CUDA on this machine.

    An NVIDIA driver being present is not the same thing as inference being
    possible.  On Windows especially, ``nvidia-smi`` can work while the CUDA
    runtime DLLs needed by CTranslate2 are missing.
    """

    gpu_name = ""
    vram_total_mb = 0
    vram_used_mb = 0
    vram_free_mb = 0
    driver_detected = False
    driver_detail = ""
    bootstrap_detail = ""

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            driver_detected = True
            parts = [p.strip() for p in result.stdout.strip().split("\n")[0].split(",")]
            gpu_name = parts[0] if len(parts) > 0 else "unknown"
            driver_detail = f"NVIDIA driver detected ({gpu_name})"
            try:
                vram_total_mb = int(parts[1]) if len(parts) > 1 else 0
                vram_used_mb = int(parts[2]) if len(parts) > 2 else 0
                vram_free_mb = int(parts[3]) if len(parts) > 3 else 0
            except (ValueError, IndexError):
                pass
        else:
            driver_detail = "nvidia-smi failed or no GPU found"
    except FileNotFoundError:
        driver_detail = "nvidia-smi not found - no NVIDIA driver"
    except Exception as exc:
        driver_detail = f"nvidia-smi probe failed: {exc}"

    if sys.platform.startswith("linux"):
        bootstrap_detail = prepare_cuda_runtime()
        _, bootstrap_failures = _probe_linux_cuda_runtime()
        if bootstrap_failures:
            detail = "; ".join(bootstrap_failures)
            if bootstrap_detail:
                detail += f"; {bootstrap_detail}"
            if driver_detected:
                detail += "; NVIDIA driver is present but the CUDA runtime libraries are not usable"
            else:
                detail += f"; {driver_detail}"
            return CudaRuntimeStatus(
                driver_detected=driver_detected,
                cuda_available=False,
                cuda_device_count=0,
                gpu_name=gpu_name,
                vram_total_mb=vram_total_mb,
                vram_used_mb=vram_used_mb,
                vram_free_mb=vram_free_mb,
                detail=detail,
            )

    try:
        import ctranslate2

        cuda_device_count = int(ctranslate2.get_cuda_device_count())
        if cuda_device_count > 0:
            detail = f"CTranslate2 detected {cuda_device_count} CUDA device(s)"
            if bootstrap_detail:
                detail += f"; {bootstrap_detail}"
            return CudaRuntimeStatus(
                driver_detected=driver_detected,
                cuda_available=True,
                cuda_device_count=cuda_device_count,
                gpu_name=gpu_name,
                vram_total_mb=vram_total_mb,
                vram_used_mb=vram_used_mb,
                vram_free_mb=vram_free_mb,
                detail=detail,
            )

        detail = "CTranslate2 detected 0 CUDA devices"
        if bootstrap_detail:
            detail += f"; {bootstrap_detail}"
        if driver_detected:
            detail += "; NVIDIA driver is present but the CUDA runtime is not usable"
        return CudaRuntimeStatus(
            driver_detected=driver_detected,
            cuda_available=False,
            cuda_device_count=0,
            gpu_name=gpu_name,
            vram_total_mb=vram_total_mb,
            vram_used_mb=vram_used_mb,
            vram_free_mb=vram_free_mb,
            detail=detail,
        )
    except Exception as exc:
        detail = f"CTranslate2 CUDA probe failed: {exc}"
        if bootstrap_detail:
            detail += f"; {bootstrap_detail}"
        if driver_detected:
            detail += "; NVIDIA driver is present but the CTranslate2 runtime could not initialize CUDA"
        else:
            detail += f"; {driver_detail}"
        return CudaRuntimeStatus(
            driver_detected=driver_detected,
            cuda_available=False,
            cuda_device_count=0,
            gpu_name=gpu_name,
            vram_total_mb=vram_total_mb,
            vram_used_mb=vram_used_mb,
            vram_free_mb=vram_free_mb,
            detail=detail,
        )
