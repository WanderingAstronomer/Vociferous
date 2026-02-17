# GPU Setup (NVIDIA on Linux)

## The Problem

NVIDIA GPU acceleration on Linux involves three separate pain points that interact badly. This page documents all of them and the fixes.

## Issue 1: NVIDIA UVM Kernel Module

### Symptom

CUDA initialization fails with errors like:
```
CUDA driver version is insufficient for CUDA runtime version
```
or whisper.cpp silently falls back to CPU inference.

### Cause

The `nvidia_uvm` (Unified Virtual Memory) kernel module is not loaded at boot, or the `/dev/nvidia-uvm` device node doesn't exist. This is common on Debian-based distributions where the module name may be `nvidia-current-uvm` instead of the expected `nvidia_uvm`.

### Fix

```bash
sudo bash scripts/fix_gpu.sh
```

The script:
1. Detects whether the module is named `nvidia_uvm` or `nvidia-current-uvm` (Debian naming)
2. Loads the module via `modprobe` (or falls back to `nvidia-modprobe -u`)
3. Creates `/dev/nvidia-uvm` if the device node is missing (via `nvidia-modprobe` or manual `mknod`)
4. Sets permissions to `0666` so non-root users can access CUDA
5. Verifies the Python CUDA environment

### Making It Persistent

The fix script applies to the current session only. To persist across reboots:

```bash
# Add the module to load at boot
echo "nvidia_uvm" | sudo tee /etc/modules-load.d/nvidia-uvm.conf

# Or for Debian's naming scheme:
echo "nvidia-current-uvm" | sudo tee /etc/modules-load.d/nvidia-uvm.conf
```

## Issue 2: pywhispercpp Bundled libcuda

### Symptom

`pywhispercpp` loads but GPU inference doesn't work, even though `nvidia-smi` shows the GPU fine.

### Cause

The `pywhispercpp` pip package bundles its own `libcuda.so` in `pywhispercpp.libs/`. This bundled copy may be older or incompatible with your installed driver version, causing silent fallback to CPU.

### Fix

The `fix_gpu.sh` script handles this automatically. It:

1. Locates the system `libcuda.so.1` via `ldconfig -p`
2. Finds the bundled copy in `pywhispercpp.libs/`
3. Backs up the bundled copy (`.bak`)
4. Replaces it with a symlink to the system driver

Manual equivalent:
```bash
# Find system libcuda
SYSTEM_LIBCUDA=$(ldconfig -p | awk '/libcuda\.so\.1 /{print $NF; exit}')

# Find bundled copy
BUNDLED=$(find .venv/lib -path "*/pywhispercpp.libs/libcuda-*.so.*" | head -1)

# Replace with symlink
mv "$BUNDLED" "${BUNDLED}.bak"
ln -s "$SYSTEM_LIBCUDA" "$BUNDLED"
```

## Issue 3: WebKitGTK + NVIDIA DRM

### Symptom

On Linux with NVIDIA proprietary drivers, the pywebview window:
- Shows a blank white screen
- Crashes with GPU-related errors in WebKitGTK
- Logs DMA-BUF or DRM errors

### Cause

WebKitGTK's compositor attempts to use DMA-BUF and DRM for GPU-accelerated rendering. NVIDIA's proprietary driver has incomplete or buggy support for these interfaces, especially under Wayland.

### Fix

Set these environment variables before launching:

```bash
export WEBKIT_DISABLE_COMPOSITING_MODE=1
export WEBKIT_DISABLE_DMABUF_RENDERER=1
```

The `vociferous.sh` launcher script sets these automatically. If you're running manually:

```bash
WEBKIT_DISABLE_COMPOSITING_MODE=1 WEBKIT_DISABLE_DMABUF_RENDERER=1 python -m src.main
```

## Development Environment Reference

The primary development system:

| Component | Version |
|-----------|---------|
| Distro | Debian 13 (Trixie) |
| Kernel | 6.12.69+deb13-amd64 |
| DE / Compositor | GNOME / Wayland |
| GPU | NVIDIA GeForce RTX 3090 |
| Driver | 550.163.01 |
| CUDA | 12.4 |

## Troubleshooting Checklist

1. **Is the NVIDIA driver loaded?** — `nvidia-smi` should show GPU info
2. **Is UVM loaded?** — `lsmod | grep nvidia_uvm` should show the module
3. **Does /dev/nvidia-uvm exist?** — `ls -la /dev/nvidia-uvm`
4. **Is libcuda symlinked correctly?** — Check `pywhispercpp.libs/` for `.bak` file and symlink
5. **Are WebKitGTK env vars set?** — Check `WEBKIT_DISABLE_COMPOSITING_MODE` and `WEBKIT_DISABLE_DMABUF_RENDERER`
6. **Run the fix script** — `sudo bash scripts/fix_gpu.sh` handles issues 1 and 2

If all else fails, the application still works on CPU — inference is slower but functional.
