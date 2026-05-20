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


def _fake_windows_nvidia_tree(tmp_path: Path) -> Path:
    nvidia_root = tmp_path / "nvidia"
    dll_paths = [
        nvidia_root / "cuda_runtime" / "bin" / "cudart64_12.dll",
        nvidia_root / "cublas" / "bin" / "cublas64_12.dll",
        nvidia_root / "cublas" / "bin" / "cublasLt64_12.dll",
        nvidia_root / "cudnn" / "bin" / "cudnn64_9.dll",
    ]
    for path in dll_paths:
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


def test_detect_cuda_runtime_registers_vendored_windows_cuda_dirs(monkeypatch, tmp_path: Path) -> None:
    cuda_runtime._WINDOWS_DLL_DIRECTORY_HANDLES.clear()
    cuda_runtime._WINDOWS_REGISTERED_CUDA_DIRS.clear()
    nvidia_root = _fake_windows_nvidia_tree(tmp_path)
    dll_loads: list[str] = []
    registered_dirs: list[str] = []

    def fake_windll(name: str) -> object:
        dll_loads.append(name)
        return object()

    def fake_add_dll_directory(path: str) -> object:
        registered_dirs.append(path)
        return object()

    monkeypatch.setattr(cuda_runtime.sys, "platform", "win32")
    monkeypatch.setenv("PATH", "C:\\Windows\\System32")
    monkeypatch.setattr(cuda_runtime.importlib.util, "find_spec", lambda _name: _fake_nvidia_spec(nvidia_root))
    monkeypatch.setattr(cuda_runtime.ctypes, "WinDLL", fake_windll, raising=False)
    monkeypatch.setattr(cuda_runtime.os, "add_dll_directory", fake_add_dll_directory, raising=False)
    monkeypatch.setattr(
        cuda_runtime.subprocess,
        "run",
        lambda *args, **kwargs: types.SimpleNamespace(
            returncode=0,
            stdout="RTX 3090, 24576, 1024, 23552\n",
        ),
    )

    fake_ctranslate2 = types.SimpleNamespace(get_cuda_device_count=lambda: 1)
    with monkeypatch.context() as import_patch:
        import_patch.setitem(sys.modules, "ctranslate2", fake_ctranslate2)
        status = cuda_runtime.detect_cuda_runtime()

    assert status.cuda_available is True
    assert status.cuda_device_count == 1
    assert "Registered vendored CUDA DLL dirs" in status.detail
    assert dll_loads == ["cudart64_12.dll", "cublas64_12.dll", "cublasLt64_12.dll", "cudnn64_9.dll"]
    assert registered_dirs == [
        str((nvidia_root / "cublas" / "bin").resolve()),
        str((nvidia_root / "cuda_runtime" / "bin").resolve()),
        str((nvidia_root / "cudnn" / "bin").resolve()),
    ]


def test_detect_cuda_runtime_rejects_windows_gpu_when_cuda_dll_missing(monkeypatch, tmp_path: Path) -> None:
    cuda_runtime._WINDOWS_DLL_DIRECTORY_HANDLES.clear()
    cuda_runtime._WINDOWS_REGISTERED_CUDA_DIRS.clear()
    nvidia_root = tmp_path / "nvidia"
    nvidia_root.mkdir()

    def fake_windll(name: str) -> object:
        raise OSError(f"{name} is not found or cannot be loaded")

    monkeypatch.setattr(cuda_runtime.sys, "platform", "win32")
    monkeypatch.setattr(cuda_runtime.importlib.util, "find_spec", lambda _name: _fake_nvidia_spec(nvidia_root))
    monkeypatch.setattr(cuda_runtime.ctypes, "WinDLL", fake_windll, raising=False)
    monkeypatch.setattr(cuda_runtime.os, "add_dll_directory", lambda path: object(), raising=False)
    monkeypatch.setattr(
        cuda_runtime.subprocess,
        "run",
        lambda *args, **kwargs: types.SimpleNamespace(
            returncode=0,
            stdout="RTX 3090, 24576, 1024, 23552\n",
        ),
    )

    fake_ctranslate2 = types.SimpleNamespace(get_cuda_device_count=lambda: 1)
    with monkeypatch.context() as import_patch:
        import_patch.setitem(sys.modules, "ctranslate2", fake_ctranslate2)
        status = cuda_runtime.detect_cuda_runtime()

    assert status.cuda_available is False
    assert status.cuda_device_count == 0
    assert "cublas64_12.dll is not loadable" in status.detail
    assert "NVIDIA driver is present but the CUDA runtime libraries are not usable" in status.detail
