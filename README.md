<div align="center">

# Vociferous

### Privacy-First Speech-to-Text for Linux

*Your voice. Your machine. Your data.*

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![Whisper](https://img.shields.io/badge/ASR-OpenAI%20Whisper-orange.svg)](https://github.com/openai/whisper)

<img src="docs/images/transcribe_view.png" width="700" alt="Vociferous Main Interface">

[Features](#-features) • [Installation](#-installation) • [Quick Start](#-quick-start) • [Documentation](#-documentation) • [Architecture](#-architecture)

</div>

---

## 🎯 What is Vociferous?

**Vociferous** is a production-grade, local-first dictation system that transforms speech into text entirely on your machine. Built with architectural rigor and attention to user experience, it leverages **OpenAI's Whisper** for state-of-the-art transcription and offers optional **AI-powered refinement** to polish your text with grammar correction and formatting.

Unlike cloud-based alternatives, Vociferous processes everything locally—**your voice never leaves your computer**. No subscriptions, no usage limits, no privacy compromises.

---

## ✨ Features

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

## 🖼️ Screenshots

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

## 🚀 Installation

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