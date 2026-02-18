# Installation

## Prerequisites

| Platform | Python | System Deps |
|----------|--------|-------------|
| Linux (Debian/Ubuntu) | 3.12 or 3.13 | `build-essential`, `python3.x-dev`, `libportaudio2`, `xclip` |
| macOS | 3.12+ via Homebrew | `portaudio` (via Homebrew) |
| Windows | 3.12+ | Visual C++ Build Tools (Desktop development with C++ workload) |

## Quick Start

### Linux

```bash
git clone https://github.com/drewpyun/Vociferous.git
cd Vociferous
bash scripts/install.sh
python scripts/provision_models.py     # downloads ASR + SLM models from Hugging Face
./vociferous.sh
```

The install script checks for required system packages and will tell you exactly what's missing:

```bash
sudo apt-get update && sudo apt-get install -y \
  build-essential python3.13-dev libportaudio2 xclip
```

### macOS

```bash
git clone https://github.com/drewpyun/Vociferous.git
cd Vociferous
bash scripts/install_mac.sh
python scripts/provision_models.py
./vociferous.sh
```

Requires [Homebrew](https://brew.sh). The script auto-installs `portaudio` if missing.

### Windows

```powershell
git clone https://github.com/drewpyun/Vociferous.git
cd Vociferous
powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
python scripts\provision_models.py
.\vociferous.bat
```

Visual C++ Build Tools are required for native extensions. Download from [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) — select the "Desktop development with C++" workload.

### Docker (Linux only)

```bash
docker compose build
docker compose up
# Open http://localhost:18900 in your browser
```

Docker requires X11 forwarding (Wayland via `XWayland`). See `docker-compose.yml` for volume mounts and device passthrough.

## What the Install Scripts Do

All platform scripts follow the same sequence:

1. **Validate Python version** — requires 3.12 or 3.13
2. **Check system dependencies** — platform-specific native libraries
3. **Create virtual environment** — `.venv/` in project root
4. **Upgrade pip/setuptools/wheel** — ensures native builds succeed
5. **Install requirements.txt** — all Python dependencies
6. **Verify critical imports** — `pywhispercpp`, `webview`, `sounddevice`, `pydantic`, `litestar`, `llama_cpp`

## Model Provisioning

After installation, you must download at least the ASR model:

```bash
# Activate venv first
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

python scripts/provision_models.py
```

This downloads models from Hugging Face Hub into the data directory. The provisioning system supports:

- **ASR models**: whisper.cpp GGML format (default: `large-v3-turbo-q5_0`)
- **SLM models**: llama.cpp GGUF format (default: `qwen14b` — Qwen3 14B Q4_K_M)

Models are stored in `~/.local/share/vociferous/models/` (Linux) or the platform-appropriate data directory.

## NVIDIA GPU Users

If you have an NVIDIA GPU and want GPU-accelerated inference, see the [GPU Setup](GPU-Setup.md) guide. The short version:

```bash
sudo bash scripts/fix_gpu.sh
```

This fixes the most common CUDA issues on Linux (missing UVM kernel module, device node permissions, pywhispercpp libcuda linkage).

## Verifying Installation

After install and model provisioning:

```bash
# Should launch the application window
./vociferous.sh

# Or manually
source .venv/bin/activate
python -m src.main
```

The application starts a native window (via pywebview) and loads the Svelte frontend from the bundled build in `frontend/dist/`.
