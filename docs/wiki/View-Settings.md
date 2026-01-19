# Settings View

The Settings View is the sole surface for mutating persistent application configuration.

---

## Overview

The Settings View allows users to:
- Configure the Whisper ASR engine (Model, Device, Compute Type)
- Set up Recording behaviors (Hotkeys, Toggle vs Push-to-Talk)
- Customize Visualization feedback
- Enable and configure AI Grammar Refinement
- Calibrate the voice visualizer
- Manage History and Application state

<img src="https://raw.githubusercontent.com/WanderingAstronomer/Vociferous/main/docs/images/settings_view.png" alt="Settings View" width="800" />

---

## Location

`src/ui/views/settings_view.py`

**View ID:** `VIEW_SETTINGS` = `"settings"`

---

## Configuration Sections

The view is organized into card-based sections:

### 1. Whisper ASR Settings
Configuration for the core transcription engine.

| Setting | Type | Options |
|---------|------|---------|
| **Whisper Architecture** | Dropdown | `tiny`, `base`, `small`, `medium`, `large-v3` (Shows estimated VRAM usage) |
| **Device** | Dropdown | `cuda` (if available), `cpu` |
| **Compute Type** | Dropdown | `float16`, `int8_float16`, `int8` (Filtered by device) |
| **Language** | Text Field | ISO-639-1 Code (e.g., `en`, `fr`) or auto |

### 2. Recording
Controls how audio is captured.

| Setting | Type | Description |
|---------|------|-------------|
| **Activation Key** | HotkeyWidget | Global hotkey to start/stop recording (e.g., `Super+Shift+V`) |
| **Recording Mode** | Dropdown | `Toggle` (Press to start/stop) or `Talk` (Hold to Record) |

### 3. Visualization
Customizes the real-time audio visualizer in the Transcribe View.

| Setting | Type | Options |
|---------|------|---------|
| **Spectrum Type** | Dropdown | `Bar`, `Line`, `Wave` |

### 4. Output & Processing
Post-transcription text handling.

| Setting | Type | Description |
|---------|------|-------------|
| **Add Trailing Space** | ToggleSwitch | Appends a space after transcription for seamless dictation flow. |
| **Grammar Refinement** | ToggleSwitch | Enables SLM-based text post-processing. |
| **Refinement Model** | Dropdown | Selects the SLM to use (e.g., `Qwen2.5-1.5B`, `Qwen3-4B`). *Visible only when enabled.* |

### 5. Voice Calibration
A dedicated tool to tune the visualizer's sensitivity to your specific voice pitch and volume.

**Features:**
- **Calibration Run:** Records a sample of your speech while reading a prompt.
- **Analysis:** Calculates Fundamental Frequency and Mean Frequency.
- **Persistence:** Save calibration data to `voice_calibration` config section.

---

## Controls

### History Controls
*Located below main settings.*

*   **Export History:** Export all transcriptions to a JSON file.
*   **Clear All History:** Permanently delete all local database records.

### Application Controls
*   **Restart Application:** Reloads the entire application state.
*   **Exit:** Quits Vociferous.

---

## Capabilities

The Settings View is **configuration-only** and does not support standard item actions (Edit, Delete, Refine).

| Capability | Supported |
|------------|-----------|
| `can_edit` | No |
| `can_delete` | No |
| `can_refine` | No |
| `can_copy` | No |

---

## Custom Widgets

### HotkeyWidget
Captures global key combinations.
*   **Interaction:** Click to focus, press keys to bind.
*   **Validation:** Requires a modifier key (Ctrl, Alt, Super/Meta).

### ToggleSwitch
A modern, animated boolean toggle used for "Enable Refinement" and "Trailing Space".

---

## Validation Logic

The view implements real-time validation:
*   **Device Checks:** Checks for CUDA availability (`ctranslate2.get_cuda_device_count()`).
*   **Compute Type Filtering:** Hides `float16` if running on CPU (as it's slow/unsupported).
*   **Model VRAM Estimates:** Displays required memory next to model names.

---

## See Also

- [Architecture](Architecture) — ConfigManager details
- [Refinement System](Refinement-System) — SLM details
- [View-Transcribe](View-Transcribe) — Visualizer usage
