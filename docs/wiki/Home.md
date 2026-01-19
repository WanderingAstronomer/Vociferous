<div align="center">
  <h1 id="vociferous-wiki">Vociferous Wiki</h1>
  <p><strong>Privacy-first, local-first speech-to-text for Linux</strong></p>

  <p>
    <a href="https://github.com/WanderingAstronomer/Vociferous/blob/main/CHANGELOG.md"><img src="https://img.shields.io/badge/version-3.0.0-blue.svg" alt="Version 3.0.0"/></a>
    <img src="https://img.shields.io/badge/platform-Linux-green.svg" alt="Platform Linux"/>
    <img src="https://img.shields.io/badge/license-MIT-yellow.svg" alt="License MIT"/>
  </p>

  <br/>
  <img src="https://raw.githubusercontent.com/WanderingAstronomer/Vociferous/main/docs/images/transcribe_view.png" alt="Vociferous Transcribe View" width="800"/>
  <p><em>The main transcription interface featuring real-time audio capture and Whisper inference.</em></p>
</div>

<hr/>

## Overview

**Vociferous** is a professional, local-first dictation system designed for Linux. It transforms speech into text entirely on your machine using **OpenAI's Whisper** (via `faster-whisper`) and optional SLM-powered text refinement.

### Key Features

| Feature | Description |
| :--- | :--- |
| **Local Processing** | Zero-latency, privacy-focused. Your voice never leaves your device. |
| **Whisper ASR** | State-of-the-art speech recognition with multi-language support. |
| **AI Refinement** | Intelligent punctuation, grammar, and formatting correction. |
| **Wayland Native** | First-class support for global hotkeys on modern Linux desktops. |
| **SQLite History** | Persistent, searchable transcript storage with dual-text safety. |
| **CUDA Acceleration** | Fully optimized for NVIDIA GPUs for near-instant inference. |

---

## Getting Started

Ready to begin using Vociferous? Follow the installation guide to get up and running:

> [!TIP]
> **[Installation & First Run Guide](Getting-Started)**

---

## Documentation

### Core Concepts

| Topic | Description |
| :--- | :--- |
| Architecture | System design, component boundaries, and threading. |
| Design System | Visual tokens, colors, and typography. |
| Data & Persistence | Database schema and the dual-text invariant. |

### View Reference

| View | Purpose |
| :--- | :--- |
| Transcribe | Live recording and real-time transcript display. |
| History | Browse, edit, and manage past transcriptions. |
| Search | Powerful filtering and discovery tools. |
| Refine | AI-powered polishing and text improvement. |
| Settings | Backend, Hotkey, and Model configuration. |
| User | Usage metrics, documentation, and about info. |

### Advanced Topics

| Page | Description |
| :--- | :--- |
| UI Views Overview | Deep dive into the UI capability system. |
| Refinement System | Detailed look at SLM service and provisioning. |
| Testing Philosophy | Our approach to quality and CI. |

---

## Tech Stack

| Layer | Technology |
| :--- | :--- |
| **Language** | Python 3.12+ |
| **UI Framework** | PyQt6 6.7.0+ |
| **Inference Engine** | CTranslate2 (via faster-whisper) |
| **Refinement** | Qwen-based SLMs |
| **Storage** | SQLAlchemy 2.0+ (SQLite) |
| **Input** | `evdev` (Wayland) / `pynput` (X11) |

---

## Additional Screenshots

<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; justify-items: center;">
  <div style="text-align: center;">
    <img src="https://raw.githubusercontent.com/WanderingAstronomer/Vociferous/main/docs/images/history_view.png" alt="History View" style="width: 100%; max-width: 400px; height: auto;">
    <br/><em>History View</em>
  </div>
  <div style="text-align: center;">
    <img src="https://raw.githubusercontent.com/WanderingAstronomer/Vociferous/main/docs/images/search_and_manage_view.png" alt="Search View" style="width: 100%; max-width: 400px; height: auto;">
    <br/><em>Search View</em>
  </div>
  <div style="text-align: center;">
    <img src="https://raw.githubusercontent.com/WanderingAstronomer/Vociferous/main/docs/images/refinement_view.png" alt="Refine View" style="width: 100%; max-width: 400px; height: auto;">
    <br/><em>Refine View</em>
  </div>
  <div style="text-align: center;">
    <img src="https://raw.githubusercontent.com/WanderingAstronomer/Vociferous/main/docs/images/settings_view.png" alt="Settings View" style="width: 100%; max-width: 400px; height: auto;">
    <br/><em>Settings View</em>
  </div>
  <div style="text-align: center;">
    <img src="https://raw.githubusercontent.com/WanderingAstronomer/Vociferous/main/docs/images/user_view.png" alt="User View" style="width: 100%; max-width: 400px; height: auto;">
    <br/><em>User View</em>
  </div>
</div>

---

## External Links

| Resource | Link |
| :--- | :--- |
| **GitHub Repository** | [Vociferous on GitHub](https://github.com/WanderingAstronomer/Vociferous) |
| **Issue Tracker** | [Report Issues & Bugs](https://github.com/WanderingAstronomer/Vociferous/issues) |
| **Changelog** | [Full Version History](https://github.com/WanderingAstronomer/Vociferous/blob/main/CHANGELOG.md) |

<br/>

<div align="center">
  <sub>Built for the Linux Community</sub>
</div>
