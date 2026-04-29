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

# Install dependencies via uv (CTranslate2/faster-whisper ship pre-built wheels with CUDA support)
cd "$PROJECT_DIR"
uv sync
echo "✓ Dependencies installed"

# Use venv Python explicitly for verification
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

# Verify critical dependencies (use venv Python, not system Python)
echo ""
echo "=========================================="
echo "Verifying critical dependencies"
echo "=========================================="

DEPS_OK=true

for module in ctranslate2 faster_whisper tokenizers webview sounddevice pydantic litestar; do
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

if [[ "$OSTYPE" == "linux-gnu"* ]] && command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
    echo ""
    echo "=========================================="
    echo "Verifying CUDA runtime"
    echo "=========================================="

    CUDA_STATUS_OUTPUT=$("$VENV_PYTHON" - <<'PY'
from src.core.cuda_runtime import detect_cuda_runtime

status = detect_cuda_runtime()
print(f"driver_detected={'1' if status.driver_detected else '0'}")
print(f"cuda_available={'1' if status.cuda_available else '0'}")
print(f"cuda_device_count={status.cuda_device_count}")
print(f"detail={status.detail}")
PY
)

    CUDA_DRIVER_DETECTED=$(printf '%s\n' "$CUDA_STATUS_OUTPUT" | sed -n 's/^driver_detected=//p')
    CUDA_AVAILABLE=$(printf '%s\n' "$CUDA_STATUS_OUTPUT" | sed -n 's/^cuda_available=//p')
    CUDA_DEVICE_COUNT=$(printf '%s\n' "$CUDA_STATUS_OUTPUT" | sed -n 's/^cuda_device_count=//p')
    CUDA_DETAIL=$(printf '%s\n' "$CUDA_STATUS_OUTPUT" | sed -n 's/^detail=//p')

    if [[ "$CUDA_AVAILABLE" == "1" ]]; then
        echo "✓ CUDA runtime ready (${CUDA_DEVICE_COUNT} device(s))"
    elif [[ "$CUDA_DRIVER_DETECTED" == "1" ]]; then
        echo "⚠ NVIDIA GPU detected, but the CUDA runtime is not usable in this venv."
        echo "  $CUDA_DETAIL"
        echo ""
        echo "Vociferous runs fine on CPU."
        echo "If you want GPU acceleration, install the optional vendored CUDA runtime wheels now."

        INSTALL_CUDA_CHOICE="${VOCIFEROUS_INSTALL_CUDA:-auto}"
        if [[ "$INSTALL_CUDA_CHOICE" == "auto" ]]; then
            if [ -t 0 ]; then
                read -r -p "Install optional CUDA runtime packages for this Linux venv? [y/N] " INSTALL_CUDA_CHOICE
                INSTALL_CUDA_CHOICE="${INSTALL_CUDA_CHOICE:-n}"
            else
                INSTALL_CUDA_CHOICE="n"
                echo "Non-interactive terminal detected. Skipping optional CUDA runtime install."
                echo "Set VOCIFEROUS_INSTALL_CUDA=yes to install it automatically."
            fi
        fi

        if [[ "$INSTALL_CUDA_CHOICE" =~ ^[Yy]([Ee][Ss])?$ ]]; then
            echo "Installing optional CUDA runtime packages..."
            uv sync --extra cuda

            CUDA_STATUS_OUTPUT=$("$VENV_PYTHON" - <<'PY'
from src.core.cuda_runtime import detect_cuda_runtime

status = detect_cuda_runtime()
print(f"cuda_available={'1' if status.cuda_available else '0'}")
print(f"cuda_device_count={status.cuda_device_count}")
print(f"detail={status.detail}")
PY
)

            CUDA_AVAILABLE=$(printf '%s\n' "$CUDA_STATUS_OUTPUT" | sed -n 's/^cuda_available=//p')
            CUDA_DEVICE_COUNT=$(printf '%s\n' "$CUDA_STATUS_OUTPUT" | sed -n 's/^cuda_device_count=//p')
            CUDA_DETAIL=$(printf '%s\n' "$CUDA_STATUS_OUTPUT" | sed -n 's/^detail=//p')

            if [[ "$CUDA_AVAILABLE" == "1" ]]; then
                echo "✓ CUDA runtime ready (${CUDA_DEVICE_COUNT} device(s))"
            else
                echo "⚠ Optional CUDA packages installed, but the runtime is still not usable."
                echo "  $CUDA_DETAIL"
                echo "  Vociferous will fall back to CPU until this is fixed."
            fi
        else
            echo "Skipping optional CUDA runtime install. Vociferous will use CPU mode."
        fi
    fi
fi

# Build frontend if not already built and npm is available
echo ""
echo "=========================================="
echo "Building frontend"
echo "=========================================="

if [ -d "$PROJECT_DIR/frontend/dist" ]; then
    echo "✓ Frontend already built (frontend/dist/ exists)"
else
    if command -v npm &> /dev/null; then
        cd "$PROJECT_DIR/frontend"
        npm install --silent
        npx vite build
        cd "$PROJECT_DIR"
        echo "✓ Frontend built"
    else
        echo "⚠ npm not found — skipping frontend build."
        echo "  Install Node.js, then run: cd frontend && npm install && npx vite build"
        echo "  (The launcher will also auto-build on first run if npm is available.)"
    fi
fi

# Install desktop icon into XDG icon theme so GTK can resolve it by name
echo ""
echo "=========================================="
echo "Installing desktop integration"
echo "=========================================="

ICON_SRC="$PROJECT_DIR/assets/icons/vociferous_icon.png"
DESKTOP_DEST="$HOME/.local/share/applications/vociferous.desktop"

if [ -f "$ICON_SRC" ] && command -v xdg-icon-resource &> /dev/null; then
    xdg-icon-resource install --novendor --size 512 "$ICON_SRC" vociferous 2>/dev/null || true
    echo "✓ Icon installed to XDG icon theme"
else
    echo "⚠ Could not install icon (xdg-icon-resource not found or icon missing)"
fi

# Install .desktop entry
sed "s|{{INSTALL_DIR}}|${PROJECT_DIR}|g" "$PROJECT_DIR/vociferous.desktop.template" > "$PROJECT_DIR/vociferous.desktop"
mkdir -p "$(dirname "$DESKTOP_DEST")"
cp "$PROJECT_DIR/vociferous.desktop" "$DESKTOP_DEST"
update-desktop-database "$(dirname "$DESKTOP_DEST")" 2>/dev/null || true
echo "✓ Desktop entry installed to $DESKTOP_DEST"

# Model provisioning (interactive)
echo ""
echo "=========================================="
echo "Model provisioning"
echo "=========================================="

PROVISION_SCRIPT="$PROJECT_DIR/scripts/provision_models.py"

# Check if default models are already installed
MODELS_NEEDED=false
"$VENV_PYTHON" "$PROVISION_SCRIPT" list 2>/dev/null | grep -q "MISSING" && MODELS_NEEDED=true

if [ "$MODELS_NEEDED" = true ]; then
    echo ""
    "$VENV_PYTHON" "$PROVISION_SCRIPT" list
    echo ""
    echo "Vociferous needs at least the ASR model and VAD model to function."
    echo "The default set (VAD + ASR + SLM) is ~10 GB total."
    echo ""

    # Support non-interactive mode (e.g. CI) via VOCIFEROUS_PROVISION=yes
    if [ "${VOCIFEROUS_PROVISION:-}" = "yes" ]; then
        DO_PROVISION="y"
    elif [ -t 0 ]; then
        read -r -p "Download default models now? [Y/n] " DO_PROVISION
        DO_PROVISION="${DO_PROVISION:-y}"
    else
        echo "Non-interactive terminal detected. Skipping model download."
        echo "Run later:  make provision"
        DO_PROVISION="n"
    fi

    if [[ "$DO_PROVISION" =~ ^[Yy]$ ]]; then
        echo ""
        echo "Downloading VAD model (~2 MB)..."
        "$VENV_PYTHON" "$PROVISION_SCRIPT" install silero_vad
        echo ""
        echo "Downloading ASR model (~780 MB)..."
        "$VENV_PYTHON" "$PROVISION_SCRIPT" install large-v3-turbo-int8
        echo ""
        echo "Downloading SLM model (~9.5 GB)..."
        "$VENV_PYTHON" "$PROVISION_SCRIPT" install qwen4b
        echo ""
        echo "✓ All default models installed"
    else
        echo "Skipped. Download models later with:  make provision"
    fi
else
    echo "✓ Default models already installed"
fi

# Final message
echo ""
echo "=========================================="
echo "Installation complete!"
echo "=========================================="
echo ""
echo "To run the application:"
echo "  cd $PROJECT_DIR"
echo "  ./vociferous.sh"
echo ""