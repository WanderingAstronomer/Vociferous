# Model Drop Locations

Place local-only model weights here. Nothing auto-downloads.

- Whisper Large v3 Turbo (default primary): HF/transformers layout under `models/whisper-large-v3-turbo/` (contains `.safetensors`).
- Faster-Whisper Small (fallback): converted weights under `models/faster_whisper_small/` (contains `.bin`).

Notes:
- Keep transformer-style files intact (config.json, tokenizer, model shards) inside the named folder.
- Converted Faster-Whisper models must include `.bin` weights.
- If you locate models elsewhere, point `models_root` in `~/.chatterbug/config.toml` to that path.
- Avoid committing weight files; only the placeholders in this folder are tracked.
- Opt-in downloader: `python -m download --model whisper-large-v3-turbo` (prompts before download; `--yes` to skip). Add `--model faster-whisper-small-int8` for the fallback.
