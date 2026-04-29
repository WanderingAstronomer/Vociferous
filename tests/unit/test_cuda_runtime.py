"""Tests for Linux CUDA runtime probing and vendored library preloading."""

from __future__ import annotations

import sys
import types
from pathlib import Path

from src.core import cuda_runtime


def _fake_nvidia_spec(nvidia_root: Path) -> types.SimpleNamespace:
    return types.SimpleNamespace(submodule_search_locations=[str(nvidia_root)])


def _fake_nvidia_tree(tmp_path: Path) -> Path:
    nvidia_root = tmp_path / "nvidia"
    library_paths = [
        nvidia_root / "cuda_runtime" / "lib" / "libcudart.so.12",
        nvidia_root / "cublas" / "lib" / "libcublasLt.so.12",
        nvidia_root / "cublas" / "lib" / "libcublas.so.12",
        nvidia_root / "cudnn" / "lib" / "libcudnn.so.9",
    ]
    for path in library_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

    return nvidia_root


def test_detect_cuda_runtime_preloads_vendored_linux_libraries(monkeypatch, tmp_path: Path) -> None:
    cuda_runtime._LINUX_LOADED_CUDA_LIBRARIES.clear()
    nvidia_root = _fake_nvidia_tree(tmp_path)
    loaded_targets: list[str] = []

    def fake_cdll(target: str, mode: int = 0) -> object:
        target_path = Path(target)
        if target_path.is_absolute():
            loaded_targets.append(target)
            return object()
        raise OSError(f"{target} is not found or cannot be loaded")

    monkeypatch.setattr(cuda_runtime.sys, "platform", "linux")
    monkeypatch.setattr(cuda_runtime.importlib.util, "find_spec", lambda _name: _fake_nvidia_spec(nvidia_root))
    monkeypatch.setattr(cuda_runtime.ctypes, "CDLL", fake_cdll)
    monkeypatch.setattr(
        cuda_runtime.subprocess,
        "run",
        lambda *args, **kwargs: types.SimpleNamespace(
            returncode=0,
            stdout="RTX 3080, 10240, 512, 9728\n",
        ),
    )

    fake_ctranslate2 = types.SimpleNamespace(get_cuda_device_count=lambda: 1)
    with monkeypatch.context() as import_patch:
        import_patch.setitem(sys.modules, "ctranslate2", fake_ctranslate2)
        status = cuda_runtime.detect_cuda_runtime()

    assert status.cuda_available is True
    assert status.cuda_device_count == 1
    assert "Preloaded vendored CUDA libs" in status.detail
    assert loaded_targets == [
        str((nvidia_root / "cuda_runtime" / "lib" / "libcudart.so.12").resolve()),
        str((nvidia_root / "cublas" / "lib" / "libcublasLt.so.12").resolve()),
        str((nvidia_root / "cublas" / "lib" / "libcublas.so.12").resolve()),
        str((nvidia_root / "cudnn" / "lib" / "libcudnn.so.9").resolve()),
    ]


def test_detect_cuda_runtime_rejects_gpu_when_cublas_remains_unloadable(monkeypatch, tmp_path: Path) -> None:
    cuda_runtime._LINUX_LOADED_CUDA_LIBRARIES.clear()
    nvidia_root = tmp_path / "nvidia"
    nvidia_root.mkdir()

    monkeypatch.setattr(cuda_runtime.sys, "platform", "linux")
    monkeypatch.setattr(cuda_runtime.importlib.util, "find_spec", lambda _name: _fake_nvidia_spec(nvidia_root))
    monkeypatch.setattr(
        cuda_runtime.ctypes,
        "CDLL",
        lambda target, mode=0: (_ for _ in ()).throw(OSError(f"{target} is not found or cannot be loaded")),
    )
    monkeypatch.setattr(
        cuda_runtime.subprocess,
        "run",
        lambda *args, **kwargs: types.SimpleNamespace(
            returncode=0,
            stdout="RTX 3080, 10240, 512, 9728\n",
        ),
    )

    fake_ctranslate2 = types.SimpleNamespace(get_cuda_device_count=lambda: 1)
    with monkeypatch.context() as import_patch:
        import_patch.setitem(sys.modules, "ctranslate2", fake_ctranslate2)
        status = cuda_runtime.detect_cuda_runtime()

    assert status.cuda_available is False
    assert status.cuda_device_count == 0
    assert "libcublas.so.12 is not loadable" in status.detail
    assert "NVIDIA driver is present but the CUDA runtime libraries are not usable" in status.detail
