#!/bin/bash
# Script to fix NVIDIA UVM (Unified Virtual Memory) for CUDA
# Usage: sudo bash scripts/fix_gpu.sh

set -euo pipefail

if [ "${EUID}" -ne 0 ]; then
    if [ -t 0 ]; then
        echo "This script requires root privileges. Re-running with sudo..."
        exec sudo --preserve-env=PATH bash "$0" "$@"
    fi

    echo "✗ This script requires root privileges and an interactive terminal."
    echo "  Run it directly in a terminal:"
    echo "    sudo bash scripts/fix_gpu.sh"
    exit 1
fi

echo "Checking NVIDIA UVM status..."

# Debian specific: Check for suffixed module names
UVM_MODULE="nvidia_uvm"
if ! /sbin/modinfo nvidia-uvm &> /dev/null; then
    if /sbin/modinfo nvidia-current-uvm &> /dev/null; then
        echo "  Detected Debian 'nvidia-current' naming scheme."
        UVM_MODULE="nvidia-current-uvm"
    fi
fi

if lsmod | grep -q "$UVM_MODULE" || lsmod | grep -q "nvidia_uvm"; then
    echo "✓ $UVM_MODULE module is loaded."
else
    echo "✗ $UVM_MODULE module is NOT loaded."
    echo "  Attempting to load it..."
    
    # Try modprobe directly first
    if modprobe "$UVM_MODULE"; then
        echo "  ✓ Successfully loaded $UVM_MODULE via modprobe."
    else
        echo "  ! modprobe failed. Trying nvidia-modprobe..."
        if command -v nvidia-modprobe &> /dev/null; then
            echo "  Running: nvidia-modprobe -u"
            nvidia-modprobe -u
            if [ $? -eq 0 ]; then
                echo "  ✓ nvidia-modprobe returned success."
            else
                echo "  ✗ Failed to load UVM. Please run 'sudo modprobe $UVM_MODULE' manually."
                exit 1
            fi
        else
            echo "  ✗ nvidia-modprobe not found. Please verify your driver installation."
            exit 1
        fi
    fi
fi

if [ ! -c /dev/nvidia-uvm ]; then
    echo "✗ /dev/nvidia-uvm device node is missing."
    echo "  Attempting to create it via nvidia-modprobe..."
    if command -v nvidia-modprobe &> /dev/null; then
        nvidia-modprobe -u
    else
        echo "  ! nvidia-modprobe not found. Falling back to manual mknod."
    fi
    
    # Fallback to manual creation if nvidia-modprobe fails
    if [ ! -c /dev/nvidia-uvm ]; then
        echo "  ! nvidia-modprobe failed to create the device node."
        echo "  Attempting manual creation via mknod..."
        
        # Find the major number in /proc/devices (usually named nvidia-uvm)
        UVM_MAJOR=$(grep "nvidia-uvm" /proc/devices | awk '{print $1}')
        
        if [ -n "$UVM_MAJOR" ]; then
            echo "  Found nvidia-uvm major number: $UVM_MAJOR"
            mknod -m 666 /dev/nvidia-uvm c "$UVM_MAJOR" 0
            if [ $? -eq 0 ]; then
                echo "  ✓ Successfully created /dev/nvidia-uvm manually."
            else
                echo "  ✗ Failed to run mknod."
            fi
        else
            echo "  ✗ Could not find 'nvidia-uvm' in /proc/devices. Is the module really loaded?"
        fi
    fi
fi

if [ -c /dev/nvidia-uvm ]; then
    echo "✓ /dev/nvidia-uvm exists."
    # Check permissions
    if [ -r /dev/nvidia-uvm ] && [ -w /dev/nvidia-uvm ]; then
        echo "✓ Device is readable/writable."
    else
        echo "! Permissions might be restrictive. Fixing permissions..."
        chmod 666 /dev/nvidia-uvm
    fi
else
    echo "✗ Failed to create /dev/nvidia-uvm. CUDA will likely fail."
    exit 1
fi

echo ""
echo "Verifying CUDA environment with Python..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${REPO_ROOT}/.venv/bin/python3"

if [ ! -x "${PYTHON_BIN}" ]; then
    PYTHON_BIN="python3"
fi

SYSTEM_LIBCUDA="$(ldconfig -p | awk '/libcuda\.so\.1 /{print $NF; exit}')"
if [ -n "${SYSTEM_LIBCUDA}" ] && [ -e "${SYSTEM_LIBCUDA}" ]; then
    echo ""
    echo "Hardening pywhispercpp CUDA linkage..."
    SYSTEM_LIBCUDA="${SYSTEM_LIBCUDA}" "${PYTHON_BIN}" - <<'PY'
import os
from pathlib import Path

system_libcuda = Path(os.environ["SYSTEM_LIBCUDA"]).resolve()

try:
    import _pywhispercpp as pywhisper_ext
except Exception as exc:
    print(f"pywhispercpp native extension not available ({exc}); skipping linkage hardening.")
    raise SystemExit(0)

site_packages = Path(pywhisper_ext.__file__).resolve().parent
libs_dir = site_packages / "pywhispercpp.libs"
if not libs_dir.exists():
    print("pywhispercpp.libs directory not found; skipping linkage hardening.")
    raise SystemExit(0)

bundled = sorted(libs_dir.glob("libcuda-*.so.*"))
if not bundled:
    print("No bundled pywhispercpp libcuda detected; no override needed.")
    raise SystemExit(0)

target = bundled[0]
if target.is_symlink() and target.resolve() == system_libcuda:
    print("pywhispercpp libcuda already points to system driver.")
    raise SystemExit(0)

backup = Path(str(target) + ".bak")
if target.exists() and not target.is_symlink() and not backup.exists():
    target.rename(backup)
elif target.exists() and not target.is_symlink() and backup.exists():
    target.unlink()
elif target.is_symlink():
    target.unlink()

target.symlink_to(system_libcuda)
print(f"Linked {target.name} -> {system_libcuda}")
if backup.exists():
    print(f"Backup preserved at {backup.name}")
PY
else
    echo ""
    echo "! Could not locate system libcuda.so.1 via ldconfig; skipping pywhispercpp linkage hardening."
fi

"${PYTHON_BIN}" -c "
try:
    from pywhispercpp.model import Model
    print('pywhispercpp: available')
except ImportError:
    print('pywhispercpp: NOT available')
try:
    from llama_cpp import Llama
    print('llama-cpp-python: available')
except ImportError:
    print('llama-cpp-python: NOT available')
print('CUDA device check requires model load — skipping quick test.')
print('If nvidia-uvm is loaded and /dev/nvidia-uvm exists, GPU inference should work.')
"
