# Vociferous

**Linux-native speech-to-text with offline transcription and local AI refinement.**

Vociferous captures audio from your microphone, transcribes it locally using [whisper.cpp](https://github.com/ggerganov/whisper.cpp), and optionally refines the text with a Small Language Model running via [llama.cpp](https://github.com/ggerganov/llama.cpp). Everything runs on your machine — no cloud APIs, no data leaves your system.

## Features

- **Offline transcription** — whisper.cpp GGML models, GPU-accelerated when available
- **AI text refinement** — 5 refinement levels from literal cleanup to full rewrite
- **Global hotkey** — press-to-toggle or push-to-talk recording modes
- **Transcript history** — searchable database with project organization
- **Variant tracking** — original transcriptions are immutable; edits and refinements stored as linked variants
- **Mini widget** — compact floating recording indicator

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

## Requirements

- Linux (X11 or Wayland)
- Python 3.12+
- Node.js 18+ (for frontend build)
- System packages: `build-essential`, `python3-dev`, `libportaudio2`

## Installation

```bash
# Install system dependencies (Debian/Ubuntu)
sudo apt-get install build-essential python3.13-dev libportaudio2

# Run the install script
bash scripts/install.sh

# Download ASR model
python3 scripts/provision_models.py
```

## Usage

```bash
./vociferous
```

Press the activation key (default: Right Alt) to start/stop recording. Transcriptions appear in the main window and are saved to the local database.

## Development

```bash
# Create venv and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Build frontend
cd frontend && npm install && npx vite build && cd ..

# Run tests
bash scripts/run_tests.sh
```

## License

[GNU Affero General Public License v3.0](LICENSE)
