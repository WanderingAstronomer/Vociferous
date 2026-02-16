#!/bin/bash
# Installation script for Vociferous on macOS
# Requires Python 3.12+ and Homebrew

set -e

echo "=========================================="
echo "Vociferous Installation Script (macOS)"
echo "=========================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Check for Homebrew
if ! command -v brew &>/dev/null; then
    echo "Error: Homebrew is not installed."
    echo "Install it from: https://brew.sh"
    echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    exit 1
fi
echo "✓ Homebrew found"

# Check Python version
PYTHON_CMD=""
for cmd in python3.13 python3.12 python3; do
    if command -v "$cmd" &>/dev/null; then
        PY_VER=$("$cmd" --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
        if [[ "$PY_VER" == "3.12" || "$PY_VER" == "3.13" ]]; then
            PYTHON_CMD="$cmd"
            break
        fi
    fi
done

if [[ -z "$PYTHON_CMD" ]]; then
    echo "Error: Python 3.12 or 3.13 is required."
    echo "Install via Homebrew:"
    echo "  brew install python@3.12"
    exit 1
fi

PYTHON_VERSION=$("$PYTHON_CMD" --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✓ Python $PYTHON_VERSION ($PYTHON_CMD)"

# Check/install system dependencies
echo ""
echo "=========================================="
echo "Checking system dependencies"
echo "=========================================="

BREW_DEPS=(portaudio)
MISSING_BREW=()

for dep in "${BREW_DEPS[@]}"; do
    if brew list "$dep" &>/dev/null; then
        echo "✓ $dep"
    else
        echo "✗ $dep (missing)"
        MISSING_BREW+=("$dep")
    fi
done

if [ ${#MISSING_BREW[@]} -gt 0 ]; then
    echo ""
    echo "Installing missing dependencies..."
    brew install "${MISSING_BREW[@]}"
    echo "✓ Dependencies installed"
fi

# Create virtual environment
echo ""
echo "=========================================="
echo "Creating virtual environment"
echo "=========================================="
if [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "Creating virtual environment..."
    "$PYTHON_CMD" -m venv "$PROJECT_DIR/.venv"
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate and install
source "$PROJECT_DIR/.venv/bin/activate"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

echo ""
echo "=========================================="
echo "Upgrading build tools"
echo "=========================================="
pip install --upgrade pip setuptools wheel
echo "✓ Build tools upgraded"

echo ""
echo "=========================================="
echo "Installing dependencies"
echo "=========================================="
cd "$PROJECT_DIR"
pip install -r requirements.txt
echo "✓ Dependencies installed"

# Verify critical deps
echo ""
echo "=========================================="
echo "Verifying critical dependencies"
echo "=========================================="

DEPS_OK=true
for module in pywhispercpp webview sounddevice pydantic litestar llama_cpp; do
    if "$VENV_PYTHON" -c "import $module" 2>/dev/null; then
        echo "✓ $module"
    else
        echo "✗ $module (MISSING)"
        DEPS_OK=false
    fi
done

if [ "$DEPS_OK" = false ]; then
    echo ""
    echo "Error: Some critical dependencies failed to install."
    echo "Check the output above for build errors."
    echo ""
    echo "Common fix: ensure Xcode Command Line Tools are installed:"
    echo "  xcode-select --install"
    exit 1
fi

# GPU detection
echo ""
echo "=========================================="
echo "GPU Detection"
echo "=========================================="
ARCH=$(uname -m)
if [[ "$ARCH" == "arm64" ]]; then
    echo "✓ Apple Silicon detected — Metal acceleration available"
    echo "  llama.cpp and whisper.cpp will use Metal by default"
else
    echo "ℹ Intel Mac detected — CPU inference only"
    echo "  (NVIDIA eGPU with CUDA is not supported on macOS)"
fi

echo ""
echo "=========================================="
echo "Installation complete!"
echo "=========================================="
echo ""
echo "To run the application:"
echo "  cd $PROJECT_DIR"
echo "  ./vociferous"
echo ""
echo "Note: On first run, macOS may prompt for:"
echo "  - Microphone access (required for transcription)"
echo "  - Accessibility access (required for global hotkeys)"
echo ""
