# Vociferous

A modern Python 3.12+ speech-to-text dictation application for Linux using OpenAI's Whisper via faster-whisper.

## Quick Start

1. **Install**: `./scripts/install.sh`
2. **Run**: `./vociferous.sh` (GPU) or `python scripts/run.py` (CPU)
3. **Record**: Press Right Alt (default hotkey) or click Record button
4. **Speak**: VAD captures your speech and filters silence
5. **Stop**: Press Right Alt again or click Stop button
6. **Paste**: Text auto-copies to clipboard → Ctrl+V

## Features

- **Fast transcription** with faster-whisper (CTranslate2 backend)
- **GPU acceleration** with CUDA/cuDNN (CPU fallback supported)
- **PyQt6 frameless window** with custom title bar and dark theme
- **Collapsible sidebar** with focus groups, recent transcripts, and search
- **Real-time waveform** visualization during recording
- **Metrics framework** with per-transcription and lifetime analytics
- **System tray** integration for background operation
- **Voice Activity Detection** filters silence during recording
- **SQLite-backed history** with focus groups and export
- **Editable transcriptions** with raw/normalized text separation
- **Live settings** that take effect immediately

## Documentation

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
- [History Storage](History-Storage) - SQLite persistence and focus groups

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
├── docs/
│   ├── images/
│   │   ├── main_window.png
│   │   └── recording_state.png
│   └── wiki/
│       ├── Audio-Recording.md
│       ├── Backend-Architecture.md
│       ├── Config-Options.md
│       ├── Configuration-Schema.md
│       ├── History-Storage.md
│       ├── Home.md
│       ├── Hotkey-System.md
│       ├── Installation-Guide.md
│       ├── Recording.md
│       ├── Text-Output.md
│       ├── Threading-Model.md
│       └── Troubleshooting.md
├── .github/
│   └── copilot-instructions.md
├── icons/
│   ├── 192x192.png
│   ├── 512x512.png
│   └── favicon.ico
├── LICENSE
├── pyproject.toml
├── pytest.ini
├── README.md
├── requirements.txt
├── scripts/
│   ├── check_deps.py
│   ├── install-desktop-entry.sh
│   ├── install.sh
│   ├── run.py
│   └── uninstall-desktop-entry.sh
├── src/
│   ├── config_schema.yaml
│   ├── history_manager.py
│   ├── key_listener.py
│   ├── main.py
│   ├── result_thread.py
│   ├── transcription.py
│   ├── utils.py
│   └── ui/
│       ├── components/
│       │   ├── main_window/
│       │   ├── settings/
│       │   ├── sidebar/
│       │   ├── title_bar/
│       │   └── workspace/
│       ├── constants/
│       │   ├── audio.py
│       │   ├── colors.py
│       │   ├── dimensions.py
│       │   ├── enums.py
│       │   ├── spacing.py
│       │   ├── timing.py
│       │   └── typography.py
│       ├── models/
│       ├── styles/
│       │   └── unified_stylesheet.py
│       ├── utils/
│       │   ├── clipboard_utils.py
│       │   ├── error_handler.py
│       │   ├── history_utils.py
│       │   └── keycode_mapping.py
│       └── widgets/
│           ├── collapsible_section/
│           ├── content_panel/
│           ├── dialogs/
│           ├── focus_group/
│           ├── history_tree/
│           ├── hotkey_widget/
│           ├── metrics_strip/
│           ├── styled_button/
│           ├── transcript_item/
│           └── waveform_visualizer/
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_error_handling.py
│   ├── test_history_manager.py
│   ├── test_history_utils.py
│   ├── test_key_listener.py
│   ├── test_settings.py
│   ├── test_single_instance.py
│   ├── test_transcription.py
│   ├── test_ui_components.py
│   ├── test_ui_integration.py
│   └── test_wayland_compat.py
└── vociferous.sh
```