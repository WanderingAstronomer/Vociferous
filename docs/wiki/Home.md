# Vociferous

A modern Python 3.12+ speech-to-text dictation application for Linux using OpenAI's Whisper via faster-whisper.

## Quick Start

1. **Install**: `./scripts/install.sh`
2. **Run**: `./vociferous.sh` (GPU) or `python scripts/run.py` (CPU)
3. **Record**: Press Alt (default hotkey) to start
4. **Speak**: VAD captures your speech and filters silence
5. **Stop**: Press Alt again to transcribe
6. **Paste**: Text auto-copies to clipboard → Ctrl+V

## Features

- **Fast transcription** with faster-whisper (CTranslate2 backend)
- **GPU acceleration** with CUDA/cuDNN (CPU fallback supported)
- **Custom frameless window** with dark theme, Wayland-native drag support
- **System tray** integration for background operation
- **Voice Activity Detection** filters silence during recording
- **Transcription history** with JSONL storage, day grouping, and export
- **Editable transcriptions** with persistence
- **Live settings** that take effect immediately

## Documentation

[Architecture — Deep-Dive Systems Guide](ARCHITECTURE) - The master document detailing Vociferous's architecture, design patterns, and components. This wiki should be sufficient to understand and contribute to the codebase without looking here. It's pretty much just a legacy doc.

### Getting Started

- [Installation Guide](Installation-Guide) - Complete setup instructions
- [Recording](Recording) - How recording works
- [Troubleshooting](Troubleshooting) - Common issues and solutions

### Architecture

- [Backend Architecture](Backend-Architecture) - Module structure and design patterns
- [Threading Model](Threading-Model) - Qt signals/slots and worker threads
- [Configuration Schema](Configuration-Schema) - YAML-based settings system

### Components

- [Audio Recording](Audio-Recording) - Microphone capture and VAD filtering
- [Hotkey System](Hotkey-System) - evdev/pynput backends and key detection
- [Text Output](Text-Output) - Clipboard workflow
- [History Storage](History-Storage) - JSONL persistence and rotation

### Reference

- [Config Options](Config-Options) - All configuration values explained

## Requirements

- **Python**: 3.12+
- **OS**: Linux (Wayland or X11)
- **Audio**: Working microphone
- **GPU** (optional): CUDA-compatible NVIDIA GPU for fast transcription

## Project Structure

```
.
├── CHANGELOG.md
├── docs
│   ├── images
│   │   └── main_window.png
│   └── wiki
│       ├── ARCHITECTURE.md
│       ├── Audio-Recording.md
│       ├── Backend-Architecture.md
│       ├── Config-Options.md
│       ├── Configuration-Schema.md
│       ├── History-Storage.md
│       ├── Home.md
│       ├── Hotkey-System.md
│       ├── Installation-Guide.md
│       ├── Keycodes-Reference.md
│       ├── Recording.md
│       ├── Text-Output.md
│       ├── Threading-Model.md
│       └── Troubleshooting.md
├── .github
│   └── copilot-instructions.md
├── .gitignore
├── icons
│   ├── 192x192.png
│   ├── 512x512.png
│   └── favicon.ico
├── LICENSE
├── pyproject.toml
├── pytest.ini
├── README.md
├── requirements.txt
├── scripts
│   ├── check_deps.py
│   ├── install-desktop-entry.sh
│   ├── install.sh
│   ├── README.md
│   ├── run.py
│   └── uninstall-desktop-entry.sh
├── src
│   ├── config_schema.yaml
│   ├── history_manager.py
│   ├── input_simulation.py
│   ├── key_listener.py
│   ├── main.py
│   ├── result_thread.py
│   ├── transcription.py
│   ├── ui
│   │   ├── history_widget.py
│   │   ├── hotkey_widget.py
│   │   ├── keycode_mapping.py
│   │   ├── main_window.py
│   │   ├── output_options_widget.py
│   │   └── settings_dialog.py
│   └── utils.py
├── tests
│   ├── conftest.py
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_input_simulation.py
│   ├── test_key_listener.py
│   ├── test_settings.py
│   ├── test_transcription.py
│   └── test_wayland_compat.py
└── vociferous.sh

10 directories, 55 files
```