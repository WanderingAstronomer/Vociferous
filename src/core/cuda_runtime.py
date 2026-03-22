from __future__ import annotations

import subprocess
from dataclasses import dataclass


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

    try:
        import ctranslate2

        cuda_device_count = int(ctranslate2.get_cuda_device_count())
        if cuda_device_count > 0:
            detail = f"CTranslate2 detected {cuda_device_count} CUDA device(s)"
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
