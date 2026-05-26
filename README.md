<div align="center">

<img src="assets/icons/vociferous_icon.png" alt="Vociferous" width="128" height="128"/>

# Vociferous

**Local-first speech-to-text for turning your voice into durable, searchable, refinable records.**

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Python 3.12-3.13](https://img.shields.io/badge/Python-3.12--3.13-blue.svg)](https://python.org)
[![Svelte 5](https://img.shields.io/badge/Svelte-5-orange.svg)](https://svelte.dev)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-green.svg)](#platform-support)

</div>

---

Vociferous is a desktop dictation system for people who think faster than they type. It records one human voice at a time, turns that speech into a persistent transcript, and gives the user tools to refine, edit, tag, search, export, recover, and understand that record afterward.

The default path is local: microphone audio stays on the machine, transcription runs through faster-whisper/CTranslate2, refinement runs through a bundled CTranslate2 language model, and the database lives on disk. Version 7 expands that without throwing away the privacy model: users who do not own high-end inference hardware can opt into external providers such as LM Studio and Groq for larger models or faster inference, while keeping the same transcript, tag, refinement, and recovery workflows.

Vociferous is not a meeting bot, not a team transcription service, not a cloud sync platform, and not a chat product with a microphone glued to it. It is an emitter of structured speech records.

## Screenshots

<table>
  <tr>
    <td align="center"><strong>Transcribe</strong></td>
    <td align="center"><strong>Transcriptions</strong></td>
  </tr>
  <tr>
    <td><img src="assets/screenshots/transcribe_view-recording.png" alt="Transcribe view while recording" width="100%"/></td>
    <td><img src="assets/screenshots/transcriptions_view.png" alt="Transcriptions library with search, tags, and actions" width="100%"/></td>
  </tr>
  <tr>
    <td align="center"><strong>Refine</strong></td>
    <td align="center"><strong>Edit</strong></td>
  </tr>
  <tr>
    <td><img src="assets/screenshots/refinement_view.png" alt="Refine view with original and refined text" width="100%"/></td>
    <td><img src="assets/screenshots/edit_view.png" alt="Edit view with Markdown rendering" width="100%"/></td>
  </tr>
  <tr>
    <td align="center"><strong>Fresh Install</strong></td>
    <td align="center"><strong>User Dashboard</strong></td>
  </tr>
  <tr>
    <td><img src="assets/screenshots/transcribe_view-idle.png" alt="Transcribe view on a fresh install" width="100%"/></td>
    <td><img src="assets/screenshots/user_view-dashboard.png" alt="User analytics dashboard" width="100%"/></td>
  </tr>
</table>

## What Vociferous Does

- Records from the microphone with a button or global hotkey.
- Imports existing audio files for transcription.
- Transcribes through local faster-whisper/CTranslate2 or optional Groq ASR.
- Refines text through local CTranslate2, LM Studio, or Groq.
- Supports custom prompt transcripts and prompt changes during a session.
- Stores raw transcripts immutably and keeps edits/refinements as variants.
- Recovers durable audio after crashes or power loss where possible.
- Caches audio for re-transcription and configurable recovery windows.
- Renders Markdown by default and provides a TipTap editing surface.
- Tags, searches, filters, sorts, exports, retitles, and bulk-refines transcripts.
- Tracks usage analytics, activity heatmaps, time saved, filler reduction, readability, and processing metrics.

## Why v7 Matters

Vociferous began as a local tool for getting words out of one person's head faster than typing allowed. That remains the core. The problem is hardware: good local inference is expensive, and not every user has the GPU needed to run larger local models comfortably.

The v7 line makes Vociferous provider-flexible. Local inference remains the private baseline, but LM Studio and Groq let users route refinement or transcription through larger models when that tradeoff makes sense. The output is still the user's voice. The prompt system and refinement workflow simply let the user decide how that voice should land: cleaned verbatim, deeply edited, rewritten as Markdown, or shaped by a saved prompt.

This release is also a ruggedization release. Recording recovery, audio vault handling, transcript provenance, provider diagnostics, settings safety, frontend race guards, contract tests, and install scripts all received hardening because a dictation tool that loses words is worse than useless. It is betrayal with a UI.

## Platform Support

| Platform | Shell | Status |
| --- | --- | --- |
| Linux | GTK + WebKitGTK through pywebview | Primary development platform |
| macOS | Cocoa + WebKit through pywebview | Supported |
| Windows | EdgeChromium through pywebview | Supported |

Docker support is Linux-only because desktop audio, display, and input devices have to be passed through from the host.

## Stack

| Layer | Technology |
| --- | --- |
| Window shell | pywebview |
| Frontend | Svelte 5, Tailwind CSS v4, Vite, TipTap |
| Backend API | Litestar REST + WebSocket |
| Local ASR | faster-whisper on CTranslate2 |
| Local refinement | CTranslate2 Generator + tokenizers |
| External ASR | Groq OpenAI-compatible audio transcription |
| External refinement | LM Studio or Groq OpenAI-compatible chat completions |
| Storage | SQLite WAL + FTS5 |
| Settings | Pydantic settings persisted as JSON |
| VAD | Silero VAD through ONNX Runtime |

## Installation

### Requirements

- Python 3.12 or 3.13.
- Node.js 18+ and npm.
- Git.
- On Linux: PortAudio, xclip, libsecret tooling, and a Secret Service backend if you want stored provider keys or encrypted audio vault keys.
- On Windows: Microsoft Edge WebView2 Runtime and Visual C++ Build Tools if native wheels are unavailable.
- Optional NVIDIA GPU acceleration requires a usable CUDA 12 runtime, not merely an installed driver.

### Linux

```bash
git clone https://github.com/WanderingAstronomer/Vociferous.git
cd Vociferous
bash scripts/install.sh
./vociferous.sh
```

The Linux installer checks system packages, selects Python 3.12/3.13, creates the virtual environment, installs dependencies, builds the frontend, and offers model provisioning.

### macOS

```bash
git clone https://github.com/WanderingAstronomer/Vociferous.git
cd Vociferous
bash scripts/install_mac.sh
./vociferous.sh
```

The macOS installer validates the virtual environment Python version and recreates unsupported environments instead of quietly reusing them.

### Windows

Install Python 3.12 or 3.13 and Node.js 18+. With `winget`:

```powershell
winget install --id Python.Python.3.12 --accept-package-agreements
winget install --id OpenJS.NodeJS.LTS --accept-package-agreements
```

Then install Vociferous:

```powershell
git clone https://github.com/WanderingAstronomer/Vociferous.git
cd Vociferous
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
.\scripts\install_windows.ps1
.\vociferous.bat
```

The Windows installer searches for real Python installs, ignores the Microsoft Store stub, builds the frontend, verifies critical imports, checks WebView2, probes CUDA usability, offers pinned CUDA runtime wheels when needed, provisions models, and can create Start Menu/Desktop shortcuts.

### Docker on Linux

```bash
docker compose build
docker compose run --rm --entrypoint python3 vociferous scripts/provision_models.py install silero_vad
docker compose run --rm --entrypoint python3 vociferous scripts/provision_models.py install large-v3-turbo-int8
docker compose run --rm --entrypoint python3 vociferous scripts/provision_models.py install qwen4b

# CPU
docker compose up

# NVIDIA GPU
docker compose --profile gpu up vociferous-gpu
```

Docker requires host display, audio, and input-device plumbing. If that sounds annoying, good instincts. Native installs are simpler.

## Model Provisioning

Default local models:

| Role | ID | Model | Approx size |
| --- | --- | --- | --- |
| VAD | `silero_vad` | Silero VAD v5 ONNX | 2 MB |
| ASR | `large-v3-turbo-int8` | Whisper Large v3 Turbo INT8 CT2 | 780 MB |
| SLM | `qwen4b` | Qwen3 4B CT2 INT8 | 3.8 GB |

Provision defaults manually:

```bash
make provision
```

Or use the Settings view after first launch.

## External Providers

External providers are opt-in. When enabled, the selected transcript text or audio is sent to that provider. Local mode remains available and remains the default privacy boundary.

### LM Studio

LM Studio is supported for refinement. Start the LM Studio local server, load a chat/instruct model, then configure Vociferous:

```text
Provider: LM Studio
Base URL: http://localhost:1234/v1
Model: the ID returned by LM Studio's /v1/models endpoint
```

If the base URL points at `localhost`, refinement stays on your machine. If it points elsewhere, transcript text goes there. The app cannot make that decision morally correct for you.

### Groq

Groq is supported for ASR and refinement through OpenAI-compatible endpoints.

```text
Base URL: https://api.groq.com/openai/v1
API key env var: GROQ_API_KEY
```

Stored provider keys use the platform secret backend and are not written into `settings.json`.

## Core Workflows

### Record

Open Transcribe, click the mic button or use the configured hotkey, speak, and stop. Vociferous runs VAD, transcribes audio, stores the result, optionally copies it to the clipboard, and schedules derived work such as title generation or auto-refinement.

### Recover

Recording sessions are tracked with durable audio assets. If the program crashes or power dies mid-session, Vociferous can surface recoverable recordings so the user can restore or discard them deliberately.

### Refine

Use built-in prompts, saved prompt transcripts, or custom instructions. Refinement can run locally or through LM Studio/Groq. The raw transcript remains immutable; accepted output becomes a variant.

### Edit

Edit transcripts in a Markdown-capable TipTap surface. Markdown rendering is the default display mode, because plain text pretending it has no structure is just markdown with commitment issues.

### Organize

Use tags, search, sort, pagination, bulk actions, exports, retitles, and analytics exclusion to keep the corpus usable.

## Data and Privacy

Vociferous is single-user and local-first.

- The SQLite database lives on the user's disk.
- Raw transcript text is immutable.
- Edits and refinements are stored as variants.
- Audio assets can be cached for recovery and re-transcription.
- Provider/model/runtime provenance is stored with transcripts and refinements.
- External providers receive data only when explicitly selected.

Platform data paths follow OS conventions through `platformdirs`. They can be overridden with `VOCIFEROUS_CONFIG_DIR`, `VOCIFEROUS_DATA_DIR`, `VOCIFEROUS_CACHE_DIR`, and `VOCIFEROUS_LOG_DIR`.

## Architecture

Vociferous uses the H-pattern:

```text
Frontend UI -> POST /api/intents -> CommandBus -> Handler/Service logic -> EventBus -> WebSocket -> Frontend state
```

API handlers dispatch intents. They do not call services directly. `src/core/application_coordinator.py` is the composition root and owns service construction, bus wiring, API lifecycle, and the pywebview window.

Long-running work runs off the UI thread. ASR and SLM inference happen in background execution contexts. SQLite writes are serialized. Provider quirks stay inside provider implementations instead of leaking into handlers.

Read [ARCHITECTURE.md](ARCHITECTURE.md) before changing shared infrastructure.

## Development

```bash
make sync       # Sync Python environment from uv.lock
make build      # Build frontend
make test       # Run pytest
make lint       # Ruff + mypy + frontend type check
make format     # Ruff format + frontend format
```

Frontend-only commands:

```bash
cd frontend
npm run check
npm run build
npm run dev
```

Current validation baseline: 776 Python tests plus frontend Svelte/TypeScript checks and production build.

## Troubleshooting

Common failure points:

- Python 3.14 is not supported yet. Use Python 3.12 or 3.13.
- On Windows, the Microsoft Store `python.exe` stub is not a Python install.
- NVIDIA drivers alone do not provide a usable CUDA runtime for CTranslate2.
- On Linux, global hotkeys may require input-device permissions.
- Stored provider keys on Linux require an unlocked Secret Service backend.
- LM Studio must have a model loaded and the local server running.
- Groq requests need a valid API key and a model supported by the endpoint being used.

More detailed troubleshooting belongs in the wiki rebuild for v7.

## License

[AGPL-3.0-or-later](LICENSE)

## Changelog

See [CHANGELOG.md](CHANGELOG.md). The v7 changelog entry will land with the final v7 release commit.