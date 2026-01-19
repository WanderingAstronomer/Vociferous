# Vociferous Wiki

> **Privacy-first speech-to-text for Linux**

![Vociferous Main Interface](images/transcribe_view.png)

---

## What is Vociferous?

**Vociferous** is a modern, local-first dictation system that transforms speech into text entirely on your machine. Built with a sleek PyQt6 interface, it leverages OpenAI's Whisper model for accurate transcription and offers optional AI-powered refinement to polish your text.

### Key Features

| Feature | Description |
|---------|-------------|
| 🔒 **Local Processing** | All transcription happens on-device—your voice never leaves your computer |
| 🎯 **Whisper ASR** | OpenAI's state-of-the-art speech recognition via faster-whisper |
| ✨ **AI Refinement** | Optional SLM-powered text improvement (grammar, formatting) |
| 🐧 **Wayland Support** | Native global hotkeys on modern Linux desktops |
| 📚 **Persistent History** | SQLite-backed transcript storage with search and organization |
| ⚡ **GPU Acceleration** | CUDA support for fast transcription and refinement |

---

## Quick Start

Ready to dictate? Get up and running in minutes:

→ **[Getting Started](Getting-Started)** — Installation and first run guide

---

## Documentation

### Core Concepts

| Page | Description |
|------|-------------|
| [Architecture](Architecture) | System design, component boundaries, threading model |
| [Design System](Design-System) | Colors, typography, spacing tokens |
| [Data and Persistence](Data-and-Persistence) | Database schema, models, dual-text invariant |

### Views

| View | Description |
|------|-------------|
| [Transcribe](View-Transcribe) | Live recording and transcript display |
| [History](View-History) | Browse and manage past transcripts |
| [Search](View-Search) | Filter and find transcripts |
| [Refine](View-Refine) | AI-powered text refinement |
| [Settings](View-Settings) | Configure application options |
| [User](View-User) | Metrics, about, and documentation links |

### Advanced Topics

| Page | Description |
|------|-------------|
| [UI Views Overview](UI-Views-Overview) | View architecture and capabilities system |
| [Refinement System](Refinement-System) | SLM service, model provisioning, prompt engineering |
| [Testing Philosophy](Testing-Philosophy) | Test tiers, fixtures, CI strategy |

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.12+ |
| UI Framework | PyQt6 6.7.0+ |
| Speech Recognition | faster-whisper (CTranslate2 backend) |
| Text Refinement | CTranslate2 + Qwen3-4B-Instruct |
| Database | SQLAlchemy 2.0+ with SQLite |
| Input Handling | evdev (Wayland) / pynput (X11) |

---

## Screenshots

<table>
<tr>
<td><img src="images/transcribe_view.png" alt="Transcribe View" width="300"/><br/><em>Transcribe View</em></td>
<td><img src="images/history_view.png" alt="History View" width="300"/><br/><em>History View</em></td>
</tr>
<tr>
<td><img src="images/search_and_manage_view.png" alt="Search View" width="300"/><br/><em>Search View</em></td>
<td><img src="images/refinement_view.png" alt="Refine View" width="300"/><br/><em>Refine View</em></td>
</tr>
<tr>
<td><img src="images/settings_view.png" alt="Settings View" width="300"/><br/><em>Settings View</em></td>
<td><img src="images/user_view.png" alt="User View" width="300"/><br/><em>User View</em></td>
</tr>
</table>

---

## Links

| Resource | Link |
|----------|------|
| 📦 GitHub Repository | [Vociferous on GitHub](https://github.com/your-username/Vociferous) |
| 🐛 Issue Tracker | [Report Issues](https://github.com/your-username/Vociferous/issues) |
| 📋 Changelog | [CHANGELOG.md](https://github.com/your-username/Vociferous/blob/main/CHANGELOG.md) |

---

**Version:** 3.0.0 | [View Changelog](https://github.com/your-username/Vociferous/blob/main/CHANGELOG.md)
