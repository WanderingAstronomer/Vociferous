# Getting Started

This guide walks you through installing Vociferous and making your first transcription.

---

## Prerequisites

### System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **OS** | Linux (Wayland or X11) | Linux (Wayland) |
| **Python** | 3.12+ | 3.12 |
| **RAM** | 4 GB | 8 GB |
| **GPU** | None (CPU-only mode) | NVIDIA CUDA |
| **VRAM** | N/A | 4+ GB (for refinement) |

### Wayland Users

For global hotkeys on Wayland, add your user to the `input` group:

```bash
sudo usermod -a -G input $USER
# Log out and back in for changes to take effect
```

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/WanderingAstronomer/Vociferous.git
cd Vociferous
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
```

### 3. Install Dependencies

```bash
.venv/bin/pip install -r requirements.txt
```

### 4. Launch Vociferous

```bash
./vociferous
```

> [!WARNING]
> Always use the `./vociferous` script to launch the application. Running `python src/main.py` directly bypasses GPU library configuration and may cause issues.

---

## First Run

### What Happens on First Launch

1. **Configuration directory created:** `~/.config/vociferous/`
2. **Database initialized:** `~/.config/vociferous/vociferous.db`
3. **Default settings applied**

### Model Download

The Whisper model downloads automatically when you make your first transcription:
- **Location:** `~/.cache/vociferous/models/`
- **Default model:** `distil-large-v3` (~1.5 GB)

### Default Settings

| Setting | Default Value |
|---------|---------------|
| Whisper Model | `distil-large-v3` |
| Device | Auto-detect (GPU if available) |
| Language | English (`en`) |
| Recording Mode | Push-to-talk |
| Hotkey | `Right Alt` |
| Refinement | Disabled |

---

## Quick Start Workflow

### Making Your First Recording

1. **Press the hotkey** (default: `Right Alt`) to start recording
2. **Speak clearly** into your microphone
3. **Press the hotkey again** to stop recording
4. **Wait** for transcription to complete
5. **Review** your transcript in the display area

### Available Actions

After transcription completes:
- **Copy** — Copy text to clipboard
- **Edit** — Modify the transcript
- **Delete** — Remove the transcript
- **Refine** — Improve with AI (if enabled)

---

## Configuring Settings

Navigate to the **Settings** view (gear icon) to customize:

### Whisper ASR Settings
- **Architecture** — Select Whisper model variant
- **Device** — Choose CPU, CUDA, or auto-detect
- **Compute Type** — Precision/speed tradeoff
- **Language** — Set transcription language

### Recording Options
- **Activation Key** — Change the recording hotkey
- **Recording Mode** — Push-to-talk or toggle

### Refinement (Optional)
- **Enable AI Refinement** — Toggle the feature
- **SLM Model** — Select refinement model

---

## Enabling Refinement (Optional)

The AI refinement feature improves transcripts by fixing grammar, punctuation, and formatting.

### Enable Refinement

1. Open **Settings** view
2. Toggle **Enable AI Refinement** to ON
3. Select your preferred **SLM Model**
4. Click **Apply**

### First Refinement

On first use, Vociferous will:
1. Download the source model (~4 GB)
2. Convert to CTranslate2 format
3. Load to GPU or CPU

This process takes several minutes and only happens once per model.

### GPU Memory

Refinement models require significant VRAM:
- **Qwen3-4B-Instruct:** ~4 GB
- **Qwen2.5-3B-Instruct:** ~3 GB
- **Qwen2.5-1.5B-Instruct:** ~1.5 GB

If GPU memory is insufficient, Vociferous will prompt you to use CPU instead.

---

## Desktop Entry (Optional)

Add Vociferous to your application launcher:

```bash
./scripts/install-desktop-entry.sh
```

To remove:

```bash
./scripts/uninstall-desktop-entry.sh
```

---

## Troubleshooting

### No Audio Input

- Check microphone permissions in system settings
- Verify the correct audio input device is selected
- Restart Vociferous

### Hotkey Not Working

- **Wayland:** Ensure you're in the `input` group
- Check for conflicts with system keyboard shortcuts
- Try a different hotkey in Settings

### GPU Not Detected

- Verify NVIDIA drivers are installed
- Check CUDA installation: `nvidia-smi`
- Always launch via `./vociferous` script

### Model Download Fails

- Check internet connection
- Verify disk space in `~/.cache/vociferous/`
- Try manual download from HuggingFace

### Application Won't Start

- Check the console for error messages
- Verify Python version: `python --version` (need 3.12+)
- Ensure all dependencies are installed

---

## Next Steps

- **[Architecture](Architecture)** — Understand the system design
- **[View-Transcribe](View-Transcribe)** — Learn about the recording interface
- **[View-Settings](View-Settings)** — Explore all configuration options

---

<img src="https://raw.githubusercontent.com/WanderingAstronomer/Vociferous/main/docs/images/startup_log.png" alt="Startup Log" width="800" />
*Application startup showing model loading and initialization*
