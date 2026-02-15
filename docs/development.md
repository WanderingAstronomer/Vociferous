# Development Guide

## Prerequisites

- Linux (Wayland or X11)
- Python 3.12+
- Node.js 18+
- System packages: `build-essential`, `python3-dev`, `libportaudio2`

## Setup

```bash
# System dependencies (Debian/Ubuntu)
sudo apt-get install build-essential python3.13-dev libportaudio2

# Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend && npm install && npx vite build && cd ..

# Download ASR model
python3 scripts/provision_models.py
```

Or use `make install` followed by `make provision`.

## Running

```bash
./vociferous          # Uses venv Python, builds frontend if needed
# or
make run
```

## Testing

```bash
make test             # Runs pytest with pyproject.toml config
make lint             # Ruff check + svelte-check + tsc
make format           # Ruff format + Prettier
```

Tests are in `tests/` and configured in `pyproject.toml`. The test suite uses pytest with markers for `slow` and `integration` tests.

## Code Style

- **Python:** Ruff (line-length 120, target py312). Format-on-save configured in VS Code.
- **Frontend:** Prettier with `prettier-plugin-svelte` (4-space indent, double quotes, 120 width).
- **Markdown:** markdownlint with `siblings_only` for duplicate headings (changelog convention).

All formatting is enforced via `make format` and VS Code format-on-save.

## Adding a New User Interaction

1. Define the intent in `src/core/intents/definitions.py`
2. Register the handler in `ApplicationCoordinator._register_handlers()`
3. Add a REST endpoint in `src/api/app.py` (or use the generic `/api/intents` POST)
4. Wire the frontend call in `frontend/src/lib/api.ts`

## Adding a New Backend Event

1. Emit from the service: `self.event_bus.emit("event_name", {"key": "value"})`
2. The event bridge auto-forwards to WebSocket clients
3. Subscribe in the frontend: `ws.on("event_name", handler)`

## Project Layout

```text
src/
  main.py                 Entry point (thin)
  core/
    application_coordinator.py   Composition root — all wiring
    command_bus.py               Intent dispatch (sync, dict-based)
    event_bus.py                 Pub/sub notifications (thread-safe)
    settings.py                  Pydantic Settings (JSON persistence)
    intents/                     Intent dataclass definitions
  core_runtime/
    server.py                    ASR subprocess (stdin/stdout IPC)
    client.py                    IPC client for UI process
    engine.py                    whisper.cpp wrapper
  api/
    app.py                       Litestar REST + WebSocket
  database/
    db.py                        SQLite WAL (transcripts, variants, projects)
  services/
    audio_service.py             sounddevice capture + FFT visualization
    slm_runtime.py               llama.cpp lifecycle + inference
    transcription_service.py     Audio → text pipeline (runs in subprocess)
  input_handler/
    listener.py                  Global hotkey (evdev / pynput)
  provisioning/
    core.py                      HuggingFace Hub model downloads
  refinement/
    engine.py                    Prompt construction + llama.cpp inference

frontend/
  src/
    App.svelte                   Main application shell
    views/                       TranscribeView, HistoryView, SearchView, SettingsView
    lib/
      api.ts                     REST client
      ws.ts                      WebSocket client
```
