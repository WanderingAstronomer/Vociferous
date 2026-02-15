#!/bin/bash
# Script to fix NVIDIA UVM (Unified Virtual Memory) for CUDA
# Usage: ./scripts/fix_gpu.sh

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
    if sudo modprobe "$UVM_MODULE"; then
        echo "  ✓ Successfully loaded $UVM_MODULE via modprobe."
    else
        echo "  ! modprobe failed. Trying nvidia-modprobe..."
        if command -v nvidia-modprobe &> /dev/null; then
            echo "  Running: sudo nvidia-modprobe -u"
            sudo nvidia-modprobe -u
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
    sudo nvidia-modprobe -u
    
    # Fallback to manual creation if nvidia-modprobe fails
    if [ ! -c /dev/nvidia-uvm ]; then
        echo "  ! nvidia-modprobe failed to create the device node."
        echo "  Attempting manual creation via mknod..."
        
        # Find the major number in /proc/devices (usually named nvidia-uvm)
        UVM_MAJOR=$(grep "nvidia-uvm" /proc/devices | awk '{print $1}')
        
        if [ -n "$UVM_MAJOR" ]; then
            echo "  Found nvidia-uvm major number: $UVM_MAJOR"
            sudo mknod -m 666 /dev/nvidia-uvm c "$UVM_MAJOR" 0
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
        sudo chmod 666 /dev/nvidia-uvm
    fi
else
    echo "✗ Failed to create /dev/nvidia-uvm. CUDA will likely fail."
    exit 1
fi

echo ""
echo "Verifying CUDA environment with Python..."
./.venv/bin/python3 -c "
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
