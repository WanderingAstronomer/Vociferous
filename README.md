# ChatterBug

ChatterBug is a cross-platform, Python-based offline dictation assistant. It is hotkey-first (record → transcribe → copy to clipboard) and keeps everything local. Primary ASR is Whisper Large v3 Turbo (loaded via transformers). Faster-Whisper small/int8 provides a lightweight fallback.

## Features (MVP direction)
- Global hotkey workflow: start/stop recording, transcribe, auto-copy to clipboard, minimal overlay/tray UI (current code still uses a Tk stub while the overlay is designed)
- Live microphone level indicator + model readiness badge so you know the app is listening/ready
- Local-only transcription: no remote APIs; you place models yourself
- GPU-aware: defaults to Whisper Large v3 Turbo (transformers) and falls back gracefully
- Modular: audio capture, ASR engine dispatcher, UI shell, and storage kept separate
- Config-driven engines: Whisper Turbo primary with Faster-Whisper fallback

## Architecture (current state)
- **UI (`ui.py`)**: Tkinter stub to drive the loop; will be replaced by a hotkey-first overlay/tray shell
- **Audio (`audio.py`)**: 16 kHz mono capture helper
- **ASR (`asr.py`)**: engine dispatcher; targets Whisper Large v3 Turbo by default with Faster-Whisper fallback
- **Storage (`storage.py`)**: appends transcripts to XML atomically (kept simple for now)

## Setup
1. Create a virtualenv and install deps: `pip install -r requirements.txt` (ensure PortAudio/libsndfile are available).
2. Place models locally (see “Model drop locations” below). No auto-downloads are performed.
3. Optional: copy `config.example.toml` to `~/.chatterbug/config.toml` and adjust engine/model paths.
4. Optional: run the opt-in downloader: `python -m download --model whisper-large-v3-turbo` (will prompt; add `--yes` to skip prompt). Add `--model faster-whisper-small-int8` for the fallback.
5. Run the stub UI: `python3 main.py` (stub TK today; overlay/hotkey shell is being wired in next).

System notes:
- Linux/Windows/macOS supported in design; ensure NVIDIA drivers + CUDA for GPU runs.
- No telemetry or cloud calls are made.

## Model drop locations
This repo does not download weights. Place them under `models/`:

- Whisper Large v3 Turbo (primary, HF): `models/whisper-large-v3-turbo/` (contains safetensors + configs)
- Faster-Whisper small/int8 (fallback): `models/faster_whisper_small/` (converted weights such as `guillaumekln/faster-whisper-small-int8`)

Update `~/.chatterbug/config.toml` (or use defaults) to point at these local dirs.

Notes:
- Whisper Large v3 Turbo via transformers is the default/supported path today. Faster-Whisper small serves as the lightweight fallback.
- Use the opt-in downloader (`python -m download --model whisper-large-v3-turbo`) to fetch the primary model; it asks for confirmation unless `--yes` is provided. Add `--model faster-whisper-small-int8` to fetch the fallback.

## Development
- See `.github/copilot-instructions.md` for AI/contributor guardrails.
- See `DEVDIARY.md` for ongoing notes.
- See `chatterbug_design_doc.md` for the current architecture and constraints.

## Testing
- `pytest` for unit/integration tests (GPU-heavy tests should be marked/opted-in).

## Status
MVP is in active development. Core loop is centered on Whisper Large v3 Turbo with a Faster-Whisper fallback.
