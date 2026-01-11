# Vociferous

Vociferous is a modern **Python 3.12+** speech‑to‑text dictation application for Linux built on **OpenAI Whisper** via **faster‑whisper (CTranslate2)**.

It is designed for fast, local dictation with a clipboard‑first workflow and minimal friction.

---

## Main Window

The application features a **modern frameless window** with three main areas:

- **Sidebar** (collapsible): Focus groups, recent transcripts, and search
- **Workspace**: Current transcription with real-time waveform visualization during recording
- **Metrics Strip**: Lifetime analytics (total time saved, word count, transcription count)

[![Vociferous Main Window](docs/images/main_window.png)](docs/images/main_window.png)

### Recording State

During recording, the workspace displays a **real-time waveform visualization** with recording controls:

[![Recording State](docs/images/recording_state.png)](docs/images/recording_state.png)

---

## Features

### Core Transcription
- Fast transcription using faster‑whisper (CTranslate2 backend)
- **GPU acceleration (NVIDIA CUDA)** with **CPU‑only fallback**
- Voice Activity Detection (VAD) filters silence
- Clipboard‑first workflow (no input injection)

### User Interface
- **PyQt6** modern frameless window with custom title bar
- **Collapsible sidebar** with smooth animations
- **Focus Groups** for organizing transcripts by topic
- **Full-text search** across all transcripts
- **Real-time waveform** visualization during recording
- **Metrics framework** with per-transcription and lifetime analytics
- Dark‑themed Linux‑native UI with system tray integration

### History & Organization
- SQLite-backed persistent history
- Focus groups for transcript organization
- Recent transcripts view (last 7 days)
- Editable transcriptions with raw/normalized text separation
- Export to TXT / CSV / Markdown
- Day-grouped tree view

### Analytics
- **Per-transcription**: Recording time, speech duration, silence time, words/min, time saved
- **Lifetime**: Total transcriptions, total words, cumulative time saved
- Metrics explanation dialog (Help → Metrics Calculations)

---

## Installation

### Quick Install (Recommended)

```bash
chmod +x scripts/install.sh
./scripts/install.sh
```

### Manual Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### System Dependencies

**Wayland**

```bash
sudo apt install wl-clipboard
sudo usermod -a -G input $USER
```

(Log out and back in after group change)

**X11**

```bash
sudo apt install python3-xlib
```

---

## Dependencies Overview

- `faster-whisper` / `ctranslate2`
- `PyQt6`
- `sounddevice` / `webrtcvad`
- `pynput` / `evdev`
- `PyYAML`
- `numpy>=2.0.0`

See `requirements.txt` for full details.

---

## Running

### GPU (Recommended)

```bash
chmod +x vociferous.sh
./vociferous.sh
```

### CPU

```bash
python scripts/run.py
```

CPU transcription is supported but significantly slower. NVIDIA GPUs are recommended for practical real‑time use.

---

## Usage Workflow

1. Press the activation hotkey (default: **Right Alt**) or click the **Record** button
2. Speak — the waveform visualizer shows your audio in real-time
3. Press the hotkey again or click **Stop** to transcribe
4. Transcription is copied to the clipboard automatically

### Recording Controls

- **Hotkey toggle**: Press Right Alt (default) to start/stop
- **UI buttons**: Record / Stop / Cancel buttons in workspace
- **Cancel**: Abort recording without transcribing

### Status Indicators

| State | Display |
| --- | --- |
| Idle | Greeting message |
| Recording | Waveform visualization, "Recording..." status |
| Transcribing | "Transcribing..." status |
| Complete | Transcript displayed with metrics |

---

## Clipboard Behavior

Vociferous **always outputs to the clipboard**.

- Email composition: paste into client
- Document writing: paste into editor
- Terminal usage: paste manually (Ctrl+Shift+V)

Vociferous **does not inject input** and does not simulate typing.

---

## Configuration

Defined in `src/config_schema.yaml`.

Key options include:

- `model_options.device`: `auto`, `cuda`, `cpu`
- `model_options.compute_type`: `float16`, `float32`, `int8`
- `model_options.language`
- `recording_options.activation_key`

All settings apply immediately via the Settings dialog.

---

## History & Focus Groups

### Storage

SQLite database at:

```
~/.config/vociferous/vociferous.db
```

### Focus Groups

Organize transcripts by topic or project:

- Create groups via sidebar context menu
- Assign transcripts to groups
- Filter view by group
- Ungrouped transcripts shown separately

### Features

- Edit transcriptions (raw text preserved, normalized text editable)
- Delete with persistence
- Auto-reload on external changes
- Export (TXT / CSV / Markdown)

---

## Metrics Framework

### Per-Transcription Metrics

**Row 0 — Human vs Machine Time:**
- Recording Time: Total cognitive time (speaking + thinking)
- Speech Duration: VAD-filtered speech segments
- Silence Time: Thinking/pausing time

**Row 1 — Productivity:**
- Words/Min: Idea throughput
- Time Saved: vs typing at 40 WPM
- Speaking Rate: Pure articulation speed

### Lifetime Analytics (Bottom Bar)

- Total time spent transcribing
- Total time saved (vs typing)
- Total transcription count
- Cumulative word count

---

## Further Reading

Additional documentation available in `docs/wiki/`:

- [Installation Guide](docs/wiki/Installation-Guide.md)
- [Recording](docs/wiki/Recording.md)
- [Backend Architecture](docs/wiki/Backend-Architecture.md)
- [Configuration Schema](docs/wiki/Configuration-Schema.md)
- [Hotkey System](docs/wiki/Hotkey-System.md)
- [Troubleshooting](docs/wiki/Troubleshooting.md)

---

**Version:** 1.4.2