# Vociferous

A modern Python 3.12+ speech-to-text dictation application using OpenAI's Whisper model via faster-whisper.

## Installation

### Quick Install (Recommended)

```bash
chmod +x install.sh
./install.sh
```

### Manual Installation

1. Create and activate virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

### System Dependencies (Linux)

For Wayland support:
```bash
# Ubuntu/Debian
sudo apt install wl-clipboard

# Add user to input group for evdev backend
sudo usermod -a -G input $USER
# Log out and back in for group changes to take effect
```

For X11 support:
```bash
sudo apt install python3-xlib
```

### Dependencies Overview

**Core Dependencies:**
- `faster-whisper` - CTranslate2-based Whisper (4x faster)
- `ctranslate2` - Optimized transformer inference
- `PyQt5` - GUI framework
- `sounddevice` - Audio capture
- `webrtcvad` - Voice activity detection
- `pynput` / `evdev` - Keyboard/mouse input handling
- `PyYAML` - Configuration management

**Development:**
- `pytest` - Testing framework
- `ruff` - Linter and formatter

See [requirements.txt](requirements.txt) for complete list and version constraints.

## Running

There are two ways to launch:

- Fast path (GPU, recommended):

```
chmod +x vociferous.sh
./vociferous.sh
```

This wrapper exports `LD_LIBRARY_PATH` so `ctranslate2` can load cuDNN/cuBLAS from the venv.

- Standard path (CPU or if your system libraries already resolve correctly):

```
python run.py
```

If you see a warning in the console about CUDA libraries not being discoverable, use `./vociferous.sh`.

## Configuration

Settings are defined in `src/config_schema.yaml`.

- `model_options.device`: `cuda` for GPU, `cpu` for CPU.
- `model_options.compute_type`: `float16` (fast, recommended) or `float32`.
- `output_options.input_method`: `clipboard` (default), `pynput`, `ydotool`, or `dotool`.

## Clipboard

By default, completed transcriptions are copied to the clipboard. Paste with Ctrl+V wherever your cursor is.

On Wayland, `wl-clipboard` enables a secondary fallback:

```
sudo apt install -y wl-clipboard
```

