<div align="center">

Vociferous  Privacy-First Speech-to-Text for Linux

Your voice. Your machine. Your data.

<img src="docs/images/transcribe_view.png" width="700" alt="Vociferous Main Interface">  Features • Installation • Quick Start • Documentation • Architecture

</div>    
---  🎯 What is Vociferous?

Vociferous is a production-grade, local-first dictation system that transforms speech into text entirely on your machine. Built with architectural rigor and attention to user experience, it leverages OpenAI's Whisper for state-of-the-art transcription and offers optional AI-powered refinement to polish your text with grammar correction and formatting.

Unlike cloud-based alternatives, Vociferous processes everything locally—your voice never leaves your computer. No subscriptions, no usage limits, no privacy compromises.


---

✨ Features

Core Capabilities

🔒 Complete Privacy — All transcription and refinement happens on-device using local models

🎯 Whisper ASR — OpenAI's state-of-the-art speech recognition via faster-whisper

✨ AI Refinement — Optional SLM-powered text improvement (grammar, punctuation, formatting)

🐧 Native Linux Support — First-class Wayland integration with global hotkey support

📚 Persistent History — SQLite-backed transcript storage with full-text search and organization

⚡ GPU Acceleration — CUDA support for real-time transcription and refinement

🎨 Modern UI — Sleek PyQt6 interface with polished design system

Technical Highlights

Intent-Driven Architecture — Clean separation between user intent and execution logic

Dual-Text Model — Preserves raw Whisper output while allowing user edits

Pluggable Backends — Modular input handling (evdev/pynput), model selection, and audio processing

Production-Ready — Comprehensive test suite, type safety, and architectural guardrails

Fully Offline — No internet connection required after initial model download


---

🖼️ Screenshots

<details>    
<summary><b>📸 View Gallery (Click to expand)</b></summary>  <table>    
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
</table>  Onboarding Experience  <table>    
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
</table>  </details>    
---  🚀 Installation

Prerequisites

Requirement	Minimum	Recommended

OS	Linux (X11/Wayland)	Linux (Wayland)
Python	3.12+	3.12
RAM	4 GB	8 GB
GPU	None (CPU mode)	NVIDIA CUDA
VRAM	N/A	4+ GB (for refinement)

Wayland Setup

For global hotkeys on Wayland, add your user to the input group:

sudo usermod -a -G input $USER

Log out and back in for changes to take effect

Install Steps

1. Clone the repository



git clone https://github.com/yourusername/Vociferous.git
cd Vociferous

2. Create virtual environment



python3 -m venv .venv

3. Install dependencies



.venv/bin/pip install -r requirements.txt

4. Launch Vociferous



./vociferous

> ⚠️ Important: Always use the ./vociferous launcher script. Running python src/main.py directly bypasses GPU library configuration.




---

🎬 Quick Start

Your First Recording

1. Launch the application with ./vociferous


2. Press Right Alt (default hotkey) to start recording


3. Speak clearly into your microphone


4. Press Right Alt again to stop recording


5. Wait for Whisper to transcribe your speech


6. Review your transcript in the main panel



Default Configuration

Setting	Default Value

Whisper Model	distil-large-v3 (~1.5 GB)
Device	Auto-detect (GPU if available)
Language	English (en)
Recording Mode	Push-to-talk
Hotkey	Right Alt
Refinement	Disabled (optional)

Available Actions

After transcription completes:

Copy — Copy text to clipboard

Edit — Modify the transcript

Delete — Remove the transcript

Refine — Polish with AI (if enabled)

Save — Persist to history database


---

🧠 Optional AI Refinement

Vociferous includes an optional text refinement system powered by local language models.

What Does Refinement Do?

Fixes grammar and punctuation errors

Improves sentence structure and flow

Applies consistent formatting

Preserves original intent and meaning

Enabling Refinement

1. Open Settings (⚙️ icon)


2. Toggle Enable AI Refinement to ON


3. Select your preferred SLM Model (e.g., Qwen3-4B-Instruct)


4. Click Apply



On first use, Vociferous will download and convert the model (~4 GB). This happens once per model and takes several minutes.

GPU Requirements

Refinement models require:

CUDA-capable NVIDIA GPU with 4+ GB VRAM (recommended)

CPU fallback supported (slower, ~8+ GB RAM recommended)


---

📚 Documentation

Comprehensive documentation is available in the project wiki:

Core Concepts

Architecture — System design, threading model, component boundaries

Design System — Colors, typography, spacing tokens

Data & Persistence — Database schema, dual-text invariant

User Guides

Getting Started — Installation and first-run guide

UI Views Overview — View architecture and capabilities

View Documentation

Transcribe View — Live recording and dictation

History View — Browse and manage past transcripts

Search View — Filter and find transcripts

Refine View — AI-powered text refinement

Settings View — Configure application options

User View — Metrics, about, and documentation

Advanced Topics

Refinement System — SLM service, model provisioning, prompt engineering

Testing Philosophy — Test tiers, fixtures, CI strategy


---

🏗️ Architecture

Vociferous is built with architectural rigor and follows strict design principles to ensure maintainability and extensibility.

Intent-Driven Design

All user interactions follow a strict Intent Pattern:

User Action → Intent (immutable dataclass) → Signal → Controller → Execution

This ensures:

Clean separation between UI and business logic

Testable and predictable behavior

No spaghetti code or hidden side effects

Technology Stack

Layer	Technology

Language	Python 3.12+
UI Framework	PyQt6 6.7.0+
Speech Recognition	faster-whisper (CTranslate2)
Text Refinement	CTranslate2 + Qwen3-4B-Instruct
Database	SQLAlchemy 2.0+ (SQLite)
Input Handling	evdev (Wayland) / pynput (X11)
GPU Acceleration	CUDA (optional)

Component Overview

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


---

🔧 Development

Requirements

Python 3.12+

Virtual environment (.venv/)

Development tools: ruff, mypy, pytest

Running Tests

Full test suite

VOCIFEROUS_TEST_IGNORE_RUNNING=1 ./scripts/check.sh

Individual test categories

.venv/bin/pytest tests/unit/
.venv/bin/pytest tests/integration/
.venv/bin/pytest tests/contracts/

Code Quality

Linting

.venv/bin/ruff check .

Type checking

.venv/bin/mypy .

Auto-formatting

.venv/bin/ruff format .

Project Structure

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


---

🤝 Contributing

Vociferous is built with high standards for code quality and architectural integrity. Before contributing:

1. Read the Architecture documentation


2. Review the Testing Philosophy


3. Ensure all tests pass: ./scripts/check.sh


4. Follow the intent-driven design pattern


5. Update documentation for any behavioral changes




---

📜 License

This project is licensed under the MIT License — see the LICENSE file for details.


---

🙏 Acknowledgments

OpenAI Whisper — Foundation of the transcription engine

faster-whisper — CTranslate2-based Whisper inference

PyQt6 — Powerful cross-platform GUI framework

SQLAlchemy — The Python SQL toolkit

Qwen Team — High-quality open-source language models


---

<div align="center">  Built with ❤️ for the Linux community  ⬆ Back to Top

</div>