# Vociferous

![Python](https://img.shields.io/badge/python-3.12%2B-blue?style=flat)
![Platform](https://img.shields.io/badge/platform-Linux-lightgrey?style=flat)
![License](https://img.shields.io/badge/license-AGPL--3.0-green?style=flat)
![Docker](https://img.shields.io/badge/docker-ready-blue?style=flat&logo=docker&logoColor=white)

**Linux-native speech-to-text with offline transcription and local AI refinement.**

Vociferous captures audio from your microphone, transcribes it locally using [whisper.cpp](https://github.com/ggerganov/whisper.cpp), and optionally refines the text with a Small Language Model running via [llama.cpp](https://github.com/ggerganov/llama.cpp). Everything runs on your machine — no cloud APIs, no data leaves your system.

---

## Features

- **Offline transcription** — whisper.cpp GGML models, GPU-accelerated when available
- **AI text refinement** — 5 refinement levels from literal cleanup to full rewrite
- **Global hotkey** — press-to-toggle or push-to-talk recording modes
- **Transcript history** — searchable database with project organization
- **Variant tracking** — original transcriptions are immutable; edits and refinements stored as linked variants
- **Mini widget** — compact floating recording indicator
- **Docker support** — containerized deployment with Wayland/X11 and optional GPU acceleration

---

## Stack

| Layer | Technology |
| ----- | ---------- |
| Window shell | [pywebview](https://pywebview.flowrl.com/) (GTK) |
| Frontend | [Svelte 5](https://svelte.dev/) + [Tailwind CSS v4](https://tailwindcss.com/) + [Vite 6](https://vite.dev/) |
| API | [Litestar](https://litestar.dev/) REST + WebSocket |
| ASR | [pywhispercpp](https://github.com/abdeladim-s/pywhispercpp) |
| SLM | [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) |
| Config | [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) |
| Database | SQLite 3 (WAL mode) |

---

## Quick Start

### Prerequisites

- Linux (Wayland or X11)
- Python 3.12+
- Node.js 18+
- System packages: `build-essential`, `python3-dev`, `libportaudio2`

### Install

```bash
# Install system dependencies (Debian/Ubuntu)
sudo apt-get install build-essential python3.13-dev libportaudio2

# Run the install script
make install

# Download ASR model
make provision
```

### Run

```bash
./vociferous
```

Press the activation key (default: **Right Alt**) to start/stop recording. Transcriptions appear in the main window and are saved to the local database.

> **Tip:** `make run` does the same thing — it's just a wrapper around `./vociferous`.

---

## Alternative: Docker

Run in a container if you don't want to install GTK/WebKitGTK system dependencies locally.

### Wayland (default)

```bash
docker compose up --build
```

### With NVIDIA GPU

```bash
docker compose --profile gpu up --build
```

Application data (config, database, model cache) is stored in named Docker volumes and persists across restarts.

<details>
<summary><strong>Docker notes</strong></summary>

- **Wayland** is the default display protocol. X11 fallback is available automatically.
- **Audio** uses PulseAudio socket passthrough. Ensure PulseAudio or PipeWire (with PulseAudio compat) is running.
- **GPU** requires the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
- **Global hotkeys** require input device access — the container gets `audio` and `input` group membership.
- The image uses a **multi-stage build**: Node.js builds the frontend, only the Python runtime ships in the final image.

</details>

---

## Development

```bash
# Create venv and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Build frontend
make build

# Run tests
make test

# Lint and format
make lint
make format
```

### Available Make Targets

| Target | Description |
| ----- | ---------- |
| `make install` | Install all dependencies (system check + venv + frontend) |
| `make run` | Run the application |
| `make test` | Run the test suite |
| `make lint` | Run linters (Ruff + frontend type check) |
| `make format` | Auto-format all code (Python + frontend) |
| `make build` | Build the frontend |
| `make provision` | Download ASR and SLM models |
| `make docker` | Build and run in Docker (CPU) |
| `make docker-gpu` | Build and run in Docker (NVIDIA GPU) |
| `make fix-gpu` | Fix NVIDIA UVM module for GPU acceleration |
| `make clean` | Remove build artifacts and caches |

---

## Project Structure

```text
src/
  core/             Application plumbing (Coordinator, CommandBus, Config, State)
  core_runtime/     Isolated subprocess for transcription (IPC transport)
  database/         Persistence layer (repositories, models, DTOs)
  services/         Business logic and background workers
  api/              Litestar REST + WebSocket server
  input_handler/    Global hotkey and input listening
  provisioning/     Model download and management
  refinement/       Text-processing engines
  ui/               Interaction intents and contracts
frontend/           Svelte 5 SPA (Tailwind CSS v4, Vite 6)
tests/              Unit, integration, and contract tests
docs/               Architecture and design documentation
```

---

## License

[GNU Affero General Public License v3.0](LICENSE)
