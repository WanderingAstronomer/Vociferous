# Vociferous

![Python](https://img.shields.io/badge/python-3.12%2B-blue?style=flat)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey?style=flat)
![License](https://img.shields.io/badge/license-AGPL--3.0-green?style=flat)
![Docker](https://img.shields.io/badge/docker-ready-blue?style=flat&logo=docker&logoColor=white)

**Cross-platform speech-to-text with offline transcription and local AI refinement.**

Vociferous captures audio from your microphone, transcribes it locally using [whisper.cpp](https://github.com/ggerganov/whisper.cpp), and optionally refines the text with a Small Language Model running via [llama.cpp](https://github.com/ggerganov/llama.cpp). Everything runs on your machine — no cloud APIs, no data leaves your system.

---

## Features

- **Offline transcription** — whisper.cpp GGML models, GPU-accelerated when available
- **AI text refinement** — 5 refinement levels from literal cleanup to full rewrite
- **Global hotkey** — press-to-toggle or push-to-talk recording modes
- **Transcript history** — searchable database with project organization
- **Variant tracking** — original transcriptions are immutable; edits and refinements stored as linked variants
- **Mini widget** — compact floating recording indicator
- **Docker support** — containerized deployment with Wayland/X11 and optional GPU acceleration (Linux)

---

## Stack

| Layer | Technology |
| ----- | ---------- |
| Window shell | [pywebview](https://pywebview.flowrl.com/) — GTK (Linux), Cocoa/WebKit (macOS), EdgeChromium (Windows) |
| Frontend | [Svelte 5](https://svelte.dev/) + [Tailwind CSS v4](https://tailwindcss.com/) + [Vite 6](https://vite.dev/) |
| API | [Litestar](https://litestar.dev/) REST + WebSocket |
| ASR | [pywhispercpp](https://github.com/abdeladim-s/pywhispercpp) |
| SLM | [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) |
| Config | [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) |
| Database | SQLite 3 (WAL mode) |

---

## Quick Start

### Prerequisites

| | Linux | macOS | Windows |
| - | - | - | - |
| **Python** | 3.12+ | 3.12+ (via Homebrew) | 3.12+ (python.org) |
| **Node.js** | 18+ | 18+ | 18+ |
| **System deps** | `build-essential`, `libportaudio2` | `portaudio` (Homebrew) | Visual C++ Build Tools, WebView2 Runtime |
| **GPU** | NVIDIA CUDA (via `nvidia-smi`) | Apple Metal (Apple Silicon auto-detected) | NVIDIA CUDA (via `nvidia-smi`) |

### Install

Each platform has a dedicated install script that checks prerequisites, creates a virtual environment, installs dependencies, and verifies the setup.

<details>
<summary><strong>Linux</strong></summary>

```bash
# Install system dependencies (Debian/Ubuntu)
sudo apt-get install build-essential python3.13-dev libportaudio2

# Run the install script
bash scripts/install.sh
# — or —
make install

# Download ASR model
make provision
```

</details>

<details>
<summary><strong>macOS</strong></summary>

```bash
# Requires Homebrew (https://brew.sh)
bash scripts/install_mac.sh

# Download ASR model
.venv/bin/python scripts/provision_models.py
```

> **Note:** On first run, macOS will prompt for **Microphone** and **Accessibility** permissions. Accessibility access is required for global hotkeys via `pynput`.

</details>

<details>
<summary><strong>Windows</strong></summary>

```powershell
# Run from PowerShell (as Administrator if needed)
powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1

# Download ASR model
.venv\Scripts\python.exe scripts\provision_models.py
```

> **Note:** [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) is required for the application window. It is pre-installed on Windows 11 and most updated Windows 10 systems.

</details>

### Run

```bash
# Linux / macOS
./vociferous

# Windows
vociferous.bat
```

Press the activation key (default: **Right Alt**) to start/stop recording. Transcriptions appear in the main window and are saved to the local database.

> **Tip (Linux):** `make run` does the same thing — it's just a wrapper around `./vociferous`.

---

## Alternative: Docker (Linux only)

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

## Scripts

The `scripts/` directory contains platform-specific install and maintenance utilities. Not all scripts apply to every OS.

| Script | Platforms | Description |
| ------ | --------- | ----------- |
| `install.sh` | Linux | Full install: system package check, venv, pip deps, frontend build, GPU detection. |
| `install_mac.sh` | macOS | Homebrew deps, venv, pip deps, Apple Silicon / Metal detection. |
| `install_windows.ps1` | Windows | Python/VC++ checks, venv, pip deps, CUDA detection, WebView2 check. |
| `provision_models.py` | All | Downloads ASR and SLM model files to the local cache. Python — runs everywhere. |
| `run_tests.sh` | Linux, macOS | Wrapper around `pytest`. On Windows use `make test` or run pytest directly. |
| `fix_gpu.sh` | Linux | Fixes NVIDIA UVM (Unified Virtual Memory) issues. Loads the `nvidia_uvm` kernel module, creates `/dev/nvidia-uvm` if missing, and sets permissions. Needed when CUDA fails because the UVM device node wasn't created at boot (common on Debian with `nvidia-current` packages). |
| `purge_old_data.sh` | Linux | Removes all pre-v4 data (old configs, databases, CTranslate2 models, HuggingFace cache, venv). Destructive — type `PURGE` to confirm. |

> **Makefile note:** The `Makefile` uses Unix-style paths (`$(VENV)/bin/python`) and is designed for Linux. On macOS it works as-is. On Windows, use the scripts directly or run commands manually — the Makefile is not Windows-compatible.

---

## Development

```bash
# Create venv and install dependencies
python3 -m venv .venv
source .venv/bin/activate    # Linux/macOS
# .venv\Scripts\activate     # Windows
pip install -r requirements.txt

# Build frontend
cd frontend && npm install && npx vite build

# Run tests
pytest                       # or: make test (Linux/macOS)

# Lint and format
make lint
make format
```

### Available Make Targets (Linux / macOS)

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

## Platform Notes & Caveats

### GPU Acceleration

| Platform | Backend | Detection | Notes |
| -------- | ------- | --------- | ----- |
| Linux | NVIDIA CUDA | `nvidia-smi` | Requires proprietary drivers. Run `make fix-gpu` if `/dev/nvidia-uvm` is missing. |
| macOS | Apple Metal | Automatic (Apple Silicon) | Metal is the default for `llama.cpp` and `whisper.cpp` on arm64 Macs. Intel Macs fall back to CPU. |
| Windows | NVIDIA CUDA | `nvidia-smi` | Requires NVIDIA drivers. CUDA toolkit optional (wheels bundle runtime). |

### Global Hotkeys

- **Linux**: Uses `evdev` (direct device events) — requires read access to `/dev/input/` devices. Most desktop environments grant this automatically.
- **macOS**: Uses `pynput` — requires **Accessibility** permission in System Settings > Privacy & Security. The OS will prompt on first run.
- **Windows**: Uses `pynput` — works out of the box.

### Data Locations

Vociferous uses [`platformdirs`](https://github.com/tox-dev/platformdirs) for OS-appropriate paths:

| Directory | Linux | macOS | Windows |
| --------- | ----- | ----- | ------- |
| Config | `~/.config/vociferous` | `~/Library/Application Support/vociferous` | `%APPDATA%\vociferous` |
| Data | `~/.local/share/vociferous` | `~/Library/Application Support/vociferous` | `%LOCALAPPDATA%\vociferous` |
| Cache/Models | `~/.cache/vociferous` | `~/Library/Caches/vociferous` | `%LOCALAPPDATA%\vociferous\Cache` |
| Logs | `~/.local/state/vociferous/log` | `~/Library/Logs/vociferous` | `%LOCALAPPDATA%\vociferous\Logs` |

All paths can be overridden with environment variables: `VOCIFEROUS_CONFIG_DIR`, `VOCIFEROUS_DATA_DIR`, `VOCIFEROUS_CACHE_DIR`, `VOCIFEROUS_LOG_DIR`.

### Window Rendering

pywebview auto-selects the native rendering engine per platform:

- **Linux**: GTK + WebKitGTK (requires `libwebkitgtk` / PyGObject)
- **macOS**: Cocoa + WebKit (built into the OS)
- **Windows**: EdgeChromium via WebView2 Runtime (pre-installed on Windows 11)

---

## Troubleshooting

### Installation fails on `pywebview` / `PyGObject` (Linux)

If you encounter build errors when installing requirements on Linux (especially with Python 3.13+), you likely need additional system libraries for building GTK bindings from source.

**Error:**

```text
Collecting PyGObject...
Building wheel for PyGObject (pyproject.toml) ... error
...
Dependency lookup for cairo with method 'pkgconfig' failed: Pkg-config for machine host machine not found.
```

**Solution:**
Install the missing build dependencies:

```bash
# Debian / Ubuntu
sudo apt install pkg-config libcairo2-dev libgirepository1.0-dev

# Fedora
sudo dnf install pkgconf cairo-devel gobject-introspection-devel

# Arch
sudo pacman -S pkgconf cairo gobject-introspection
```

### CUDA / GPU not detected

- **Linux**: Verify `nvidia-smi` is on your PATH and the driver is loaded (`lsmod | grep nvidia`). If `/dev/nvidia-uvm` is missing, run `bash scripts/fix_gpu.sh`.
- **Windows**: Ensure NVIDIA drivers are installed from [nvidia.com/drivers](https://www.nvidia.com/download/index.aspx). `nvidia-smi` should be in `C:\Windows\System32\`.
- **macOS (Intel)**: No GPU acceleration available. Apple Silicon Macs use Metal automatically.

### WebView2 not found (Windows)

pywebview on Windows requires the [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/). It ships with Windows 11 and most updated Windows 10 installations. If missing, download and install the Evergreen Standalone Installer.

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
scripts/            Platform-specific install, GPU fix, model provisioning
tests/              Unit, integration, and contract tests
docs/               Architecture and design documentation
```

---

## License

[GNU Affero General Public License v3.0](LICENSE)
