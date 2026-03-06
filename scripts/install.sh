#!/bin/bash
# Installation script for Vociferous
# Requires Python 3.12 or 3.13 and a Linux system with audio support

set -e

echo "=========================================="
echo "Vociferous Installation Script"
echo "=========================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Check Python version
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "Detected Python version: $PYTHON_VERSION"

if [[ "$PYTHON_VERSION" != "3.12" && "$PYTHON_VERSION" != "3.13" ]]; then
    echo "Error: Vociferous requires Python 3.12 or 3.13"
    echo "Your version: $PYTHON_VERSION"
    exit 1
fi
echo "✓ Python version check passed"

# Check for required system packages (before venv creation, as some are needed for building)
echo ""
echo "=========================================="
echo "Checking system dependencies"
echo "=========================================="

# Map Python version to dev package name
PYTHON_DEV_PKG="python${PYTHON_VERSION}-dev"

# System packages required for building dependencies
REQUIRED_SYSTEM_PKGS=(
    "build-essential:gcc|c++ compiler"
    "${PYTHON_DEV_PKG}:Python development headers"
    "libportaudio2:Audio library for sounddevice"
    "xclip:Clipboard access for auto-copy"
)

MISSING_PACKAGES=()

for pkg_spec in "${REQUIRED_SYSTEM_PKGS[@]}"; do
    pkg_name="${pkg_spec%%:*}"
    pkg_desc="${pkg_spec#*:}"
    
    if ! dpkg -l | grep -q "^ii.*${pkg_name}"; then
        echo "✗ ${pkg_name} — ${pkg_desc}"
        MISSING_PACKAGES+=("$pkg_name")
    else
        echo "✓ ${pkg_name}"
    fi
done

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo ""
    echo "Error: Required system packages are missing."
    echo ""
    echo "Install them with:"
    echo "  sudo apt-get update && sudo apt-get install -y ${MISSING_PACKAGES[@]}"
    echo ""
    echo "Then run this script again."
    exit 1
fi

# Create virtual environment if it doesn't exist
echo ""
# Check for uv
echo ""
echo "=========================================="
echo "Checking for uv package manager"
echo "=========================================="
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    echo "✓ uv installed"
else
    echo "✓ uv $(uv --version | cut -d' ' -f2) found"
fi

# Install all dependencies via uv (handles venv creation automatically)
echo ""
echo "=========================================="
echo "Installing dependencies"
echo "=========================================="

# GPU/CUDA Detection for Linux
cd "$PROJECT_DIR"

if [[ "$OSTYPE" == "linux-gnu"* ]] && command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
    echo "NVIDIA GPU detected. Enabling CUDA build flags."
    echo "Building with CUDA support (this may take a few minutes)..."
    # First sync all deps from lockfile
    uv sync
    # Then rebuild CUDA-critical packages from source with CUDA flags
    CMAKE_ARGS="-DGGML_CUDA=on" uv pip install --reinstall --no-binary pywhispercpp,llama-cpp-python pywhispercpp llama-cpp-python
else
    uv sync
fi
echo "✓ Dependencies installed"

# Use venv Python explicitly for verification
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

# Verify critical dependencies (use venv Python, not system Python)
echo ""
echo "=========================================="
echo "Verifying critical dependencies"
echo "=========================================="

DEPS_OK=true

for module in pywhispercpp webview sounddevice pydantic litestar llama_cpp; do
    if "$VENV_PYTHON" -c "import $module" 2>/dev/null; then
        echo "✓ $module is available"
    else
        echo "✗ $module is NOT available (required)"
        DEPS_OK=false
    fi
done

if [ "$DEPS_OK" = false ]; then
    echo ""
    echo "Error: Some critical dependencies are missing."
    echo "This may indicate a build failure. Check the output above for errors."
    echo ""
    echo "If you see 'Python.h: No such file or directory', install:"
    echo "  sudo apt-get install python${PYTHON_VERSION}-dev"
    echo ""
    echo "If you see 'PortAudio library not found', install:"
    echo "  sudo apt-get install libportaudio2"
    echo ""
    echo "Then try again: bash scripts/install.sh"
    exit 1
fi

# Final message
echo ""
echo "=========================================="
echo "Installation complete!"
echo "=========================================="
echo ""
echo "To run the application:"
echo "  cd $PROJECT_DIR"
echo "  ./vociferous"
echo ""