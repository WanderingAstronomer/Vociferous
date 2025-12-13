#!/bin/bash
# Installation script for Vociferous

set -e

echo "=========================================="
echo "Vociferous Installation Script"
echo "=========================================="
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "Detected Python version: $PYTHON_VERSION"

if [[ "$PYTHON_VERSION" != "3.12" && "$PYTHON_VERSION" != "3.13" ]]; then
    echo "Warning: This script is optimized for Python 3.12/3.13"
    echo "Your version may work, but you might encounter issues."
    echo ""
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
else
    echo "Virtual environment already exists."
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install all requirements
echo ""
echo "=========================================="
echo "Installing dependencies"
echo "=========================================="
pip install -r requirements.txt

# Verify installation
echo ""
echo "=========================================="
echo "Verifying installation"
echo "=========================================="
python3 -c "import faster_whisper; print('✓ faster-whisper imported successfully')"
python3 -c "import onnxruntime; print('✓ onnxruntime imported successfully')"
python3 -c "import PyQt5; print('✓ PyQt5 imported successfully')"
python3 -c "import sounddevice; print('✓ sounddevice imported successfully')"
python3 -c "import pynput; print('✓ pynput imported successfully')"

echo ""
echo "=========================================="
echo "Installation complete!"
echo "=========================================="
echo ""
echo "To run the application:"
echo "  source .venv/bin/activate"
echo "  python run.py"
echo ""
