# Configuration

## Overview

Vociferous uses **Pydantic Settings** for typed, validated configuration. The root class is `VociferousSettings` in `src/core/settings.py`.

## Settings File Location

Settings persist to a JSON file at the platform-appropriate config directory:

| Platform | Path |
|----------|------|
| Linux | `~/.config/vociferous/settings.json` |
| macOS | `~/Library/Application Support/vociferous/settings.json` |
| Windows | `%APPDATA%\vociferous\settings.json` |

## Settings Sections

### `model` — ASR Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | `str` | `"large-v3-turbo-q5_0"` | whisper.cpp GGML model identifier |
| `device` | `str` | `"auto"` | Legacy field (GPU is compile-time for whisper.cpp) |
| `language` | `str` | `"en"` | Transcription language |
| `n_threads` | `int` | `4` | CPU threads for inference |

### `recording` — Audio Input

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `activation_key` | `str` | `"alt_right"` | Global hotkey to start/stop recording |
| `input_backend` | `str` | `"auto"` | Key listener backend (auto-detected per platform) |
| `recording_mode` | `str` | `"press_to_toggle"` | `press_to_toggle` or `hold_to_record` |
| `sample_rate` | `int` | `16000` | Audio sample rate (Hz) |
| `min_duration_ms` | `int` | `100` | Minimum recording duration |

### `user` — User Identity

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | `""` | User display name |
| `active_project_id` | `int \| null` | `null` | Currently active project for new transcripts |

### `output` — Text Output

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `add_trailing_space` | `bool` | `true` | Append space after typed text |
| `auto_copy_to_clipboard` | `bool` | `true` | Copy transcript to clipboard automatically |

### `display` — UI Scaling

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ui_scale` | `int` | `100` | UI scale percentage |

### `visualizer` — Audio Visualizer

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | `str` | `"bars"` | Visualizer type |
| `style` | `str` | `"interstellar"` | Color theme |
| `quality` | `str` | `"medium"` | Render quality |
| `intensity` | `float` | `1.0` | Visual intensity multiplier |
| `num_bars` | `int` | `64` | Bar count |
| `decay_rate` | `float` | `0.1` | Animation decay |
| `peak_hold_ms` | `int` | `800` | Peak hold duration |
| `monstercat` | `float` | `0.8` | Smoothing factor |
| `noise_reduction` | `float` | `0.77` | Noise gate threshold |
| `gate_aggression` | `float` | `0.0` | Noise gate aggressiveness |

### `refinement` — SLM Text Refinement

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `true` | Enable SLM refinement |
| `model_id` | `str` | `"qwen14b"` | SLM model identifier |
| `n_gpu_layers` | `int` | `-1` | GPU offload layers (-1 = all, 0 = CPU only) |
| `n_ctx` | `int` | `32768` | Context window size |
| `system_prompt` | `str` | *(built-in)* | Base system prompt for refinement |
| `invariants` | `list[str]` | *(5 built-in rules)* | Cross-level invariants always injected into prompts |
| `levels` | `dict` | *(5 levels)* | Refinement intensity levels (see below) |
| `motd_system_prompt` | `str` | *(built-in)* | System prompt for message-of-the-day generation |

### `voice_calibration` — Voice Calibration (Computed)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `fundamental_freq` | `float` | `0.0` | Computed fundamental frequency |
| `freq_mean` | `float` | `0.0` | Mean frequency from calibration |
| `energy_95th` | `float` | `0.0` | 95th-percentile energy level |

This section is written by the voice calibration system, not user-configured directly.

### `logging` — Log Output

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `level` | `str` | `"INFO"` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `console_echo` | `bool` | `true` | Echo logs to stdout |
| `structured_output` | `bool` | `false` | JSON-structured log output |

## Refinement Levels

The refinement system has 5 intensity levels, each with specific permitted and prohibited edits:

| Level | Name | Description |
|-------|------|-------------|
| 0 | **Literal** | Spelling, grammar, punctuation only. No structural changes. |
| 1 | **Structural** | Remove fillers/stutters, fix run-ons. Preserve vocabulary. |
| 2 | **Neutral** | Smooth phrasing, standardize terminology. Professional clarity. |
| 3 | **Intent** | Rewrite to best communicate inferred intent. Preserve facts. |
| 4 | **Overkill** | Aggressive restructuring for maximum rhetorical impact. No fluff. |

Each level includes a `role`, `permitted` actions, `prohibited` actions, and a `directive`. These are injected into the SLM prompt at inference time.

## Environment Variable Overrides

Settings can be overridden via environment variables with the `VOCIFEROUS_` prefix:

```bash
VOCIFEROUS_LOGGING__LEVEL=DEBUG python -m src.main
VOCIFEROUS_MODEL__N_THREADS=8 python -m src.main
```

Nested settings use `__` as the delimiter (standard Pydantic Settings convention).

## Atomic Persistence

Settings are saved atomically to prevent corruption:

1. Write to a temporary file in the same directory
2. `os.replace()` the temp file over the target (atomic on all platforms)
3. Read-back verification on next load

This prevents half-written JSON files if the process is killed mid-write.
