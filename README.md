<div align="center">

# Vociferous

### Privacy-First Speech-to-Text for Linux

*Your voice. Your machine. Your data.*

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![Whisper](https://img.shields.io/badge/ASR-OpenAI%20Whisper-orange.svg)](https://github.com/openai/whisper)

<img src="docs/images/transcribe_view.png" width="700" alt="Vociferous Main Interface">

[Features](#features) • [Installation](#installation) • [Quick Start](#quick-start) • [Documentation](#documentation) • [Architecture](#architecture)

</div>

---

## What is Vociferous?

**Vociferous** is a production-grade, local-first dictation system that transforms speech into text entirely on your machine. Built with architectural rigor and attention to user experience, it leverages **OpenAI's Whisper** for state-of-the-art transcription and offers optional **AI-powered refinement** to polish your text with grammar correction and formatting.

Unlike cloud-based alternatives, Vociferous processes everything locally—**your voice never leaves your computer**. No subscriptions, no usage limits, no privacy compromises.

---

## Features

### Core Capabilities

- **Complete Privacy** — All transcription and refinement happens on-device using local models
- **Whisper ASR** — OpenAI's state-of-the-art speech recognition via [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- **AI Refinement** — Optional SLM-powered text improvement (grammar, punctuation, formatting)
- **Native Linux Support** — First-class Wayland integration with global hotkey support
- **Persistent History** — SQLite-backed transcript storage with full-text search and organization
- **GPU Acceleration** — CUDA support for real-time transcription and refinement
- **Modern UI** — Sleek PyQt6 interface with polished design system

### Technical Highlights

- **Intent-Driven Architecture** — Clean separation between user intent and execution logic
- **Dual-Text Model** — Preserves raw Whisper output while allowing user edits
- **Pluggable Backends** — Modular input handling (evdev/pynput), model selection, and audio processing
- **Production-Ready** — Comprehensive test suite, type safety, and architectural guardrails
- **Fully Offline** — No internet connection required after initial model download

---

## Screenshots

<details>
<summary><b>View Gallery (Click to expand)</b></summary>

<table>
<tr>
<td align="center">
<img src="docs/images/transcribe_view.png" width="400" alt="Transcribe View"><br>
<em>Transcribe View — Live dictation and recording</em>
</td>
<td align="center">
<img src="docs/images/history_view.png" width="400" alt="History View"><br>
<em>History View — Browse and manage transcripts</em>
</td>
</tr>
<tr>
<td align="center">
<img src="docs/images/search_and_manage_view.png" width="400" alt="Search View"><br>
<em>Search & Manage — Filter and organize</em>
</td>
<td align="center">
<img src="docs/images/refinement_view.png" width="400" alt="Refine View"><br>
<em>Refine View — AI-powered text improvement</em>
</td>
</tr>
<tr>
<td align="center">
<img src="docs/images/settings_view.png" width="400" alt="Settings View"><br>
<em>Settings View — Configure transcription and refinement</em>
</td>
<td align="center">
<img src="docs/images/user_view.png" width="400" alt="User View"><br>
<em>User View — Metrics and documentation</em>
</td>
</tr>
</table>

### Onboarding Experience

<table>
<tr>
<td align="center">
<img src="docs/images/onboarding_welcome.png" width="300" alt="Onboarding Welcome"><br>
<em>Welcome screen</em>
</td>
<td align="center">
<img src="docs/images/onboarding_transcription_model_choice.png" width="300" alt="Model Selection"><br>
<em>Model selection</em>
</td>
<td align="center">
<img src="docs/images/onboarding_choose_hotkey.png" width="300" alt="Hotkey Setup"><br>
<em>Hotkey configuration</em>
</td>
</tr>
</table>

</details>

---

## Installation

### Prerequisites

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **OS** | Linux (X11/Wayland) | Linux (Wayland) |
| **Python** | 3.12+ | 3.12 |
| **RAM** | 4 GB | 8 GB |
| **GPU** | None (CPU mode) | NVIDIA CUDA |
| **VRAM** | N/A | 4+ GB (for refinement) |

### Wayland Setup

For global hotkeys on Wayland, add your user to the `input` group:

```bash
sudo usermod -a -G input $USER
# Log out and back in for changes to take effect
```

### Install Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/Vociferous.git
   cd Vociferous
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv .venv
   ```

3. **Install dependencies**
   ```bash
   .venv/bin/pip install -r requirements.txt
   ```

4. **Launch Vociferous**
   ```bash
   ./vociferous
   ```

> **Important:** Always use the `./vociferous` launcher script. Running `python src/main.py` directly bypasses GPU library configuration.

---

## Quick Start

### Your First Recording

1. **Launch** the application with `./vociferous`
2. **Press Right Alt** (default hotkey) to start recording
3. **Speak clearly** into your microphone
4. **Press Right Alt again** to stop recording
5. **Wait** for Whisper to transcribe your speech
6. **Review** your transcript in the main panel

### Default Configuration

| Setting | Default Value |
|---------|---------------|
| Whisper Model | `distil-large-v3` (~1.5 GB) |
| Device | Auto-detect (GPU if available) |
| Language | English (`en`) |
| Recording Mode | Push-to-talk |
| Hotkey | `Right Alt` |
| Refinement | Disabled (optional) |

### Available Actions

After transcription completes:
- **Copy** — Copy text to clipboard
- **Edit** — Modify the transcript
- **Delete** — Remove the transcript
- **Refine** — Polish with AI (if enabled)
- **Save** — Persist to history database

---

## Optional AI Refinement

Vociferous includes an optional **text refinement system** powered by local language models.

### What Does Refinement Do?

- Fixes grammar and punctuation errors
- Improves sentence structure and flow
- Applies consistent formatting
- Preserves original intent and meaning

### Enabling Refinement

1. Open **Settings**
2. Toggle **Enable AI Refinement** to ON
3. Select your preferred **SLM Model** (e.g., Qwen3-4B-Instruct)
4. Click **Apply**

On first use, Vociferous will download and convert the model (~4 GB). This happens once per model and takes several minutes.

### GPU Requirements

Refinement models require:
- **CUDA-capable NVIDIA GPU** with 4+ GB VRAM (recommended)
- **CPU fallback** supported (slower, ~8+ GB RAM recommended)

---

## Documentation

Comprehensive documentation is available in the [**project wiki**](docs/wiki):

### Core Concepts
- [**Architecture**](docs/wiki/Architecture.md) — System design, threading model, component boundaries
- [**Design System**](docs/wiki/Design-System.md) — Colors, typography, spacing tokens
- [**Data & Persistence**](docs/wiki/Data-and-Persistence.md) — Database schema, dual-text invariant

### User Guides
- [**Getting Started**](docs/wiki/Getting-Started.md) — Installation and first-run guide
- [**UI Views Overview**](docs/wiki/UI-Views-Overview.md) — View architecture and capabilities

### View Documentation
- [**Transcribe View**](docs/wiki/View-Transcribe.md) — Live recording and dictation
- [**History View**](docs/wiki/View-History.md) — Browse and manage past transcripts
- [**Search View**](docs/wiki/View-Search.md) — Filter and find transcripts
- [**Refine View**](docs/wiki/View-Refine.md) — AI-powered text refinement
- [**Settings View**](docs/wiki/View-Settings.md) — Configure application options
- [**User View**](docs/wiki/View-User.md) — Metrics, about, and documentation

### Advanced Topics
- [**Refinement System**](docs/wiki/Refinement-System.md) — SLM service, model provisioning, prompt engineering
- [**Testing Philosophy**](docs/wiki/Testing-Philosophy.md) — Test tiers, fixtures, CI strategy

---

## Architecture

Vociferous is built with **architectural rigor** and follows strict design principles to ensure maintainability and extensibility.

### Intent-Driven Design

All user interactions follow a strict **Intent Pattern**:

```
User Action → Intent (immutable dataclass) → Signal → Controller → Execution
```

This ensures:
- Clean separation between UI and business logic
- Testable and predictable behavior
- No spaghetti code or hidden side effects

### Technology Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.12+ |
| UI Framework | PyQt6 6.7.0+ |
| Speech Recognition | faster-whisper (CTranslate2) |
| Text Refinement | CTranslate2 + Qwen3-4B-Instruct |
| Database | SQLAlchemy 2.0+ (SQLite) |
| Input Handling | evdev (Wayland) / pynput (X11) |
| GPU Acceleration | CUDA (optional) |

### Component Overview

```
┌─────────────────────────────────────────────────────┐
│                    UI Layer (PyQt6)                 │
├─────────────────────────────────────────────────────┤
│              Application Coordinator                │
│    (Composition root, signal wiring, lifecycle)     │
├─────────────────────────────────────────────────────┤
│  Services Layer                                     │
│  • TranscriptionService    • SLMService             │
│  • AudioService           • VoiceCalibration        │
├─────────────────────────────────────────────────────┤
│  Core Runtime (Background Engine)                   │
│  • Whisper Inference      • Audio Capture           │
│  • State Management       • IPC Protocol            │
├─────────────────────────────────────────────────────┤
│  Database Layer (SQLAlchemy + SQLite)               │
│  • HistoryManager         • Models & DTOs           │
│  • Repositories           • Signal Bridge           │
└─────────────────────────────────────────────────────┘
```

---

## Development

### Requirements

- Python 3.12+
- Virtual environment (`.venv/`)
- Development tools: `ruff`, `mypy`, `pytest`

### Running Tests

```bash
# Full test suite
VOCIFEROUS_TEST_IGNORE_RUNNING=1 ./scripts/check.sh

# Individual test categories
.venv/bin/pytest tests/unit/
.venv/bin/pytest tests/integration/
.venv/bin/pytest tests/contracts/
```

### Code Quality

```bash
# Linting
.venv/bin/ruff check .

# Type checking
.venv/bin/mypy .

# Auto-formatting
.venv/bin/ruff format .
```

### Project Structure

```
vociferous/
├── src/
│   ├── core/              # Application coordination, config, exceptions
│   ├── core_runtime/      # Background engine and IPC
│   ├── database/          # SQLAlchemy models and persistence
│   ├── services/          # Business logic (transcription, SLM, audio)
│   ├── ui/                # PyQt6 views, components, styles
│   └── input_handler/     # Keyboard/input backends
├── tests/                 # Comprehensive test suite
├── docs/wiki/             # User and developer documentation
└── assets/                # Icons, sounds, resources
```

---

## Contributing

Vociferous is built with high standards for code quality and architectural integrity. Before contributing:

1. Read the [Architecture documentation](docs/wiki/Architecture.md)
2. Review the [Testing Philosophy](docs/wiki/Testing-Philosophy.md)
3. Ensure all tests pass: `./scripts/check.sh`
4. Follow the intent-driven design pattern
5. Update documentation for any behavioral changes

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- **[OpenAI Whisper](https://github.com/openai/whisper)** — Foundation of the transcription engine
- **[faster-whisper](https://github.com/SYSTRAN/faster-whisper)** — CTranslate2-based Whisper inference
- **[PyQt6](https://www.riverbankcomputing.com/software/pyqt/)** — Powerful cross-platform GUI framework
- **[SQLAlchemy](https://www.sqlalchemy.org/)** — The Python SQL toolkit
- **[Qwen Team](https://huggingface.co/Qwen)** — High-quality open-source language models

---

<div align="center">

**Built with love for the Linux community**

[Back to Top](#vociferous)

</div>
