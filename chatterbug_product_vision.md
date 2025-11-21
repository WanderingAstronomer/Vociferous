# ChatterBug — Finished Product Vision

This document paints a picture of what ChatterBug should become once the MVP grows into a polished desktop application. It uses the current code base (hotkey-first workflow, Whisper Large v3 Turbo ASR, Tk-based shell, audio/storage modules, opt-in downloader) as the launchpad and extrapolates toward a complete user-facing product.

---

## 1. Core Promise

**ChatterBug is the always-on, local dictation companion for power users.** It listens instantly when invoked, transcribes accurately using state-of-the-art on-device models, and hands polished text to the clipboard or target apps with minimal friction. The finished product emphasizes four pillars:

1. **Instant readiness** — A tray icon indicates engine readiness; models are verified at launch and prefetched into memory so the first transcription is fast.
2. **Hotkey-first operation** — One global shortcut toggles recording; another opens history/settings. No heavy windows unless necessary.
3. **On-device privacy** — All processing remains local. Model downloads require opt-in confirmation and can target a per-user cache.
4. **Fluid UX** — Live mic levels, animated states, clipboard confirmations, and subtle notifications make the experience reassuring without being intrusive.

---

## 2. User Experience

### 2.1 Entry Points
- **Global Hotkey (default: Ctrl+Alt+Space)**  
  - Press once → ChatterBug animates into “Listening” state, showing a live waveform/meter.  
  - Press again → recording stops, transcription begins.  
  - Result is shown in an overlay and copied to clipboard automatically.
- **Tray/menubar icon**  
  - Indicates status (Ready, Downloading, Recording, Transcribing, Error).  
  - Right-click → Settings, History, Model Manager, Quit.  
  - Left-click → open overlay window (status + last transcript).

### 2.2 Visual Language
- **Overlay** (inspired by modern dictation HUDs)  
  - Transparent background, rounded corners.  
  - Sections: mic meter, live clock, engine badge, transcript preview, copy/export buttons.  
  - Adaptive layout: small bar near top of screen while idle; expands downward while recording/transcribing.
- **History window**  
  - Paginated list with timestamps, engine, confidence metrics, tags.  
  - Search/filter (e.g., “today”, “#meeting”).  
  - Export selected entries to text/Markdown.
- **Settings**  
  - **General**: hotkey remapping, max recording duration, auto-copy toggle, notifications.  
  - **ASR**: choose engine (Whisper Turbo default, Faster-Whisper fallback), compute precision, GPU/CPU preference.  
  - **Models**: show installed models, disk usage, update/fetch button, download history, advanced path override.  
  - **Audio**: input device selection, sensitivity calibration, noise suppression toggle.  
  - **Storage**: choose where transcripts are saved (local SQLite/JSON), retention policy, export location.

### 2.3 Workflow Enhancements
- **Context-aware paste**: optional integration to paste directly into the active application after transcription (with per-app allowlist).  
- **Snippets/Commands**: user-defined voice commands (e.g., “insert signature”) that output templated text.  
- **Language switching**: quick menu to set target language or translation mode.  
- **Confidence cues**: transcripts display underlines for low-confidence words; clicking reveals alternative suggestions.  
- **Notifications**: desktop notification when transcription completes (configurable).

---

## 3. Audio & ASR Architecture

### 3.1 Engines
- **Primary**: Whisper Large v3 Turbo (transformers, FP16 on GPU / FP32 on CPU).  
  - Preloaded at app startup (optional).  
  - Tweakable parameters: temperature fallback, beam width, chunked/sequential long-form.  
  - Transparent metadata (latency, tokens/sec, VRAM usage) surfaced via debug panel.
- **Fallback**: Faster-Whisper small/int8.  
  - Auto-selected if GPU unavailable or memory constrained.  
  - Option to run solely on CPU for portability.
- **Future slots**: ability to add alternative models (Phi-4 multimodal, Canary-Qwen, etc.) via plugin interface once they have stable local runtimes.

### 3.2 Audio Pipeline
- Always-on meter monitors input levels even when idle (muted until hotkey triggers).  
- Adjustable noise gate and optional RNNoise/filter.  
- Max duration enforcement with countdown overlay and warning beep.  
- Buffering strategy: ring buffer feeding the active engine; chunked mode for long recordings.  
- Device management: automatic fallback to default mic, but user can choose from list; detection of disconnects with subtle prompts.

### 3.3 Storage
- **Primary storage**: SQLite database in `~/.chatterbug/logs.db`.  
  - Tables: `transcripts`, `metadata`, `snippets`, `settings`.  
  - Each transcript row includes text, timestamps, engine info, confidence, tags.  
  - Exports available (JSON, Markdown, CSV).  
  - Optional encryption for stored history.
- **Clipboard integration**: pipeline ensures cleaned text, trailing newline control, optional Markdown formatting.

---

## 4. Model Lifecycle & Updates

### 4.1 Downloader UX
- GUI pane lists available models with size, version, release date, changelog.  
- Each download requires explicit confirmation (size + disk path).  
- Background download with progress bar; `Pause/Resume/Cancel` controls.  
- Integrity checks (SHA256) and partial download resume.  
- Option to keep models in a shared global cache (e.g., `~/.cache/chatterbug/models`).

### 4.2 Updates & Maintenance
- Notify when a newer model revision is available; user can inspect release notes before updating.  
- Support multiple installed versions with ability to roll back.  
- Automatic detection of corrupted/missing files with guided fix (e.g., “Re-download Whisper Large v3 Turbo” button).

---

## 5. Advanced Features & Integrations

1. **Command Palette** — type “/translate French” or “/summarize last” to post-process transcripts.
2. **App-specific profiles** — e.g., “when typing into VS Code, remove trailing punctuation and wrap selection”.
3. **Dictation macros** — simple DSL to convert phrases into formatting directives (lists, headings, bullet points).
4. **API/Automation hooks** — local HTTP/WebSocket endpoint for other apps to trigger recordings or receive transcripts.
5. **Metrics dashboard** — daily usage, words transcribed, average latency, GPU utilization.
6. **Accessibility** — screen reader support, high contrast theme, adjustable font sizes, optional “click-to-record” button for users who can’t easily press hotkeys.

---

## 6. Quality, Testing, and Telemetry

### 6.1 Reliability
- Automated regression tests cover audio capture, ASR dispatcher, clipboard, storage, downloader, and UI state transitions (with headless Tk/Qt harness).  
- Stress tests simulate 100+ consecutive dictations, long recordings, GPU OOM events.  
- Structured logging with log levels, rotating files, redaction of transcript content unless user opts into diagnostic sharing (off by default).

### 6.2 Performance Targets
- **Cold start model load**: <6 seconds on 24 GB GPU; <10 seconds on CPU.  
- **Stop→text latency**: <5 seconds for 30-second clip on GPU; <10 seconds on CPU fallback.  
- **Memory**: Whisper Turbo <8 GB VRAM; Faster-Whisper <2 GB system RAM.

### 6.3 Telemetry Policy
- Default: no telemetry.  
- Optional diagnostics toggle uploads anonymized performance metrics (engine load time, latency, errors) to help improve the app, never transcripts.  
- Clear privacy statement and one-click “export my data” capability.

---

## 7. Packaging & Distribution

- **Installers** for Windows (MSI), macOS (.app with notarization), Linux (AppImage/Flatpak).  
- Bundled Python runtime (via PyInstaller/Briefcase) to avoid manual env setup.  
- On first run, wizard walks through: choose hotkey, verify microphone, select model(s) to download, run test transcription.  
- Autostart toggle (disabled by default).  
- Automatic update mechanism (with release notes and rollback).

---

## 8. Roadmap Snapshot

1. **MVP Hardened**  
   - Replace Tk stub with cross-platform overlay (Qt/PySide).  
   - Implement history storage + settings UI.  
   - Bundle downloader UI + background model load.
2. **Experience Pass**  
   - Tray icon, notifications, live meter polish.  
   - Device selection, audio calibration, error toasts.  
   - Command palette, formatting macros.
3. **Scaling & Integrations**  
   - Plugin API for additional ASR models.  
   - Local HTTP/WebSocket interface.  
   - Dictation-to-app workflows (e.g., “send to Notion”).
4. **Distribution & Compliance**  
   - Installers, auto-update, notarization.  
   - Optional encryption, better logging, diagnostics toggle.  
   - Accessibility review, localization.

---

## 9. Closing Vision

A “finished” ChatterBug feels invisible until you need it. You tap the shortcut, the overlay glows, you speak, and the words appear where you expect them—reliably, privately, and fast. It respects your hardware limits, keeps you in control of downloads and data, and gives you professional polish (history, snippets, formatting, integrations) without ever leaving your machine.

This document should guide design and engineering decisions beyond the MVP, ensuring every addition reinforces the original promise: **local, elegant, trustworthy dictation for people who rely on their computers all day.**
