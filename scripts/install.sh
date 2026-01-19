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

# Check for required system packages
echo ""
echo "Checking system dependencies..."

for cmd in git; do
    if ! command -v $cmd &> /dev/null; then
        echo "Warning: $cmd is not installed. Some features may not work."
    fi
done

# Create virtual environment if it doesn't exist
echo ""
if [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$PROJECT_DIR/.venv"
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$PROJECT_DIR/.venv/bin/activate"

# Upgrade pip and build tools
echo ""
echo "=========================================="
echo "Upgrading build tools"
echo "=========================================="
pip install --upgrade pip setuptools wheel
echo "✓ Build tools upgraded"

# Install all requirements
echo ""
echo "=========================================="
echo "Installing dependencies from requirements.txt"
echo "=========================================="
cd "$PROJECT_DIR"
pip install -r requirements.txt
echo "✓ Dependencies installed"

# Verify critical dependencies
echo ""
echo "=========================================="
echo "Verifying critical dependencies"
echo "=========================================="

DEPS_OK=true

for module in faster_whisper PyQt6 sounddevice sqlalchemy transformers; do
    if python3 -c "import $module" 2>/dev/null; then
        echo "✓ $module is available"
    else
        echo "✗ $module is NOT available (required)"
        DEPS_OK=false
    fi
done

if [ "$DEPS_OK" = false ]; then
    echo ""
    echo "Error: Some critical dependencies are missing."
    echo "Please run: pip install -r requirements.txt"
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
echo "To install desktop entry:"
echo "  ./scripts/install-desktop-entry.sh"
echo ""