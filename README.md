# Vociferous

A modern Python 3.12+ speech-to-text dictation application for Linux using OpenAI's Whisper model via faster-whisper.

## Features

- **Fast transcription** using faster-whisper (CTranslate2 backend)
- **Hotkey activation** with press-to-toggle recording mode
- **Voice Activity Detection** automatically stops when you stop speaking
- **Transcription history** with JSONL storage and export (txt, csv, markdown)
- **Collapsible day grouping** with auto-collapse for past days
- **Editable transcriptions** - single-click to load, edit, and save
- **Dark theme UI** with system tray integration
- **Live settings** with immediate effect (no restart needed)
- **Clipboard workflow** - transcriptions auto-copy for easy paste

## Installation

### Quick Install (Recommended)

```bash
chmod +x scripts/install.sh
./scripts/install.sh
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

```bash
chmod +x vociferous.sh
./vociferous.sh
```

This wrapper exports `LD_LIBRARY_PATH` so `ctranslate2` can load cuDNN/cuBLAS from the venv.

- Standard path (CPU or if your system libraries already resolve correctly):

```bash
python scripts/run.py
```

If you see a warning in the console about CUDA libraries not being discoverable, use `./vociferous.sh`.

## Usage

1. **Start recording**: Press the activation key (default: Right Alt)
2. **Speak**: Voice Activity Detection captures your speech
3. **Stop recording**: Press the key again (or VAD auto-stops after silence)
4. **Paste**: Transcription is copied to clipboard - paste with Ctrl+V

## Configuration

Settings are defined in `src/config_schema.yaml`.

- `model_options.device`: `auto` (auto-detect), `cuda` (GPU), or `cpu`
- `model_options.compute_type`: `float16` (GPU, fastest), `float32` (any), or `int8` (CPU, quantized)
- `model_options.language`: ISO-639-1 language code (e.g., `en`, `es`, `de`)
- `recording_options.activation_key`: Key to trigger recording

### Graphical Settings

Open the settings dialog from:

- **System tray**: Right-click → Settings...
- **Main window**: Settings menu → Preferences

All options are editable, including the activation hotkey. Changes apply immediately.

### Hotkey Rebinding

1. Open Settings
2. Click **Change...** next to Activation Key
3. Press the new key combination
4. Click **OK** or **Apply**

The new hotkey is active instantly – no restart required.

## History Management

Transcription history is stored at `~/.config/vociferous/history.jsonl`.

### Features

- **Collapsible day groups**: Click headers to expand/collapse (past days auto-collapse)
- **Single-click to edit**: Load any entry into the editor panel
- **Double-click to copy**: Quick copy to clipboard
- **Context menu**: Right-click entries to Copy or Delete
- **Export**: Save history to txt, csv, or markdown format
- **Clear All**: Remove all history with confirmation dialog
- **Auto-rotation**: Oldest entries removed when exceeding limit (default 1000)

### Export Formats

| Format | Description |
|--------|-------------|
| `.txt` | Timestamped entries, one per block |
| `.csv` | Columns: Timestamp, Text, Duration (ms) |
| `.md` | Day headers (##), time headers (###), text content |

## Clipboard

Completed transcriptions are automatically copied to the clipboard. Paste with Ctrl+V wherever needed.

On Wayland, `wl-clipboard` provides the clipboard backend:

```bash
sudo apt install -y wl-clipboard
```

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed technical documentation.

## License

MIT License - see [LICENSE](LICENSE) for details.

