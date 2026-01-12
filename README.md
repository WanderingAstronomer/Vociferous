# Vociferous

**Version 2.4.0** — Advanced AI Refinement

Vociferous is a fast, local speech-to-text dictation application for Linux. It transcribes your voice using OpenAI's Whisper model (via faster-whisper) and copies the result directly to your clipboard. No cloud services, no account required—just press a hotkey, speak, and paste.

[![Vociferous Main Window](docs/images/main_window.png)](docs/images/main_window.png)

---

## What Changed in v2.4.0

This release introduces **Refinement Profiles** and **Dynamic VRAM Management**.

- **Control Your Edit**: Choose between `Minimal` (grammar only), `Balanced` (cleanup), or `Strong` (flow) refinement.
- **Smart Loading**: The system automatically detects your GPU's VRAM headroom and optimizes model loading for speed vs. stability.
- **Improved Engine**: Upgraded backend to `Qwen3-4B-Instruct` for professional-grade copy editing.

---

## Features

### Core Transcription
- Fast local transcription using faster-whisper (CTranslate2 backend)
- **AI Grammar Refinement**: Single-click cleanup using local Instruct models (Qwen3-4B) with selectable profiles
- GPU acceleration (NVIDIA CUDA) with automatic CPU fallback
- Voice Activity Detection filters silence automatically
- Clipboard-first workflow—no input injection or typing simulation

### User Interface
- Modern PyQt6 frameless window with dark theme
- Collapsible sidebar with focus groups, recent transcripts, and search
- Real-time waveform visualization during recording
- Metrics showing recording time, words/minute, and time saved

### History & Organization
- SQLite-backed persistent history
- Focus groups for organizing transcripts by topic
- Editable transcriptions (original preserved, edits saved separately)
- Export to TXT, CSV, or Markdown

[![Recording State](docs/images/recording_state.png)](docs/images/recording_state.png)

---

## How It Works

Vociferous follows a simple, predictable interaction model:

1. **You act** — Press a hotkey or click a button
2. **The system validates** — Can this action happen right now?
3. **State changes** — If valid, the workspace transitions (idle → recording → transcribing → viewing)
4. **You see feedback** — Success is silent; problems are explained in the status bar

This model is intentionally rigid. The application will not let you start recording while editing unsaved changes, switch transcripts without saving, or delete content you're actively modifying. These constraints exist to protect your work.

---

## Quick Start

### Installation

```bash
chmod +x scripts/install.sh
./scripts/install.sh
```

### Running

**GPU (recommended):**
```bash
./vociferous.sh
```

**CPU fallback:**
```bash
python scripts/run.py
```

### Basic Usage

1. Press **Right Alt** (default hotkey) or click **Record**
2. Speak naturally—the waveform shows your audio
3. Press **Right Alt** again or click **Stop**
4. Your transcription appears and is copied to the clipboard
5. Paste anywhere with **Ctrl+V**

---

## Scripts and Launchers

### scripts/run.py

**Application entry point with GPU library configuration.**

```bash
python scripts/run.py
```

**What it does**

1. **Configures GPU libraries** - Sets `LD_LIBRARY_PATH` for CUDA/cuDNN in the venv
2. **Re-executes if needed** - Uses `os.execv()` to restart with correct environment
3. **Sets up Python path** - Adds `src/` to module search path
4. **Configures logging** - Initializes logging before any imports
5. **Launches application** - Imports and runs `main.py`

**Why a separate entry point?**

`LD_LIBRARY_PATH` must be set **before** any CUDA libraries are loaded. Python's import system loads shared libraries immediately, so environment changes after import don't work. The re-exec pattern solves this:

```
First run: Check GPU paths → Set LD_LIBRARY_PATH → os.execv() (restart)
Second run: LD_LIBRARY_PATH already set → Import CUDA → Run app
```

**Environment Variables**

- `_VOCIFEROUS_ENV_READY` - Sentinel to prevent infinite re-exec loops
- `CUDA_VISIBLE_DEVICES` - Defaults to `0` if not set
- `LD_LIBRARY_PATH` - Prepended with NVIDIA library paths from venv

---

### scripts/check_deps.py

**Dependency verification script.**

```bash
python scripts/check_deps.py
```

**Output**

```
==============================================================
Vociferous Dependency Check
==============================================================

Required Packages:
--------------------------------------------------------------
  ✓ faster-whisper
  ✓ ctranslate2
  ✓ numpy
  ...

Optional Packages:
--------------------------------------------------------------
  ⚠ some-optional-pkg - not installed (optional)

Development Packages:
--------------------------------------------------------------
  ✓ pytest
  ✓ ruff

==============================================================
```

**Package Categories**

| Category | Purpose |
| --- | --- |
| **Required** | Must be installed for app to run |
| **Optional** | Enhance functionality but not required |
| **Development** | Testing and code quality tools |

**Exit Code**

- `0` - All required packages present
- `1` - One or more required packages missing

---

### scripts/install.sh

**Automated installation script.**

```bash
chmod +x scripts/install.sh
./scripts/install.sh
```

**What it does**

1. **Checks Python version** - Warns if not 3.12/3.13
2. **Creates virtual environment** - `.venv/` in project root
3. **Upgrades pip** - Ensures latest pip, setuptools, wheel
4. **Installs dependencies** - `pip install -r requirements.txt`
5. **Verifies installation** - Imports key packages to confirm success

**Output**

```
==========================================
Vociferous Installation Script
==========================================

Detected Python version: 3.12
Creating virtual environment...
Activating virtual environment...
Upgrading pip...

==========================================
Installing dependencies
==========================================
...

==========================================
Verifying installation
==========================================
✓ faster-whisper imported successfully
✓ onnxruntime imported successfully
✓ PyQt6 imported successfully
...

==========================================
Installation complete!
==========================================

To run the application:
  source .venv/bin/activate
  python scripts/run.py
```

---

### vociferous.sh (project root)

**GPU-optimized launcher wrapper.**

```bash
./vociferous.sh
```

Sets environment variables and activates venv before running:
- `LD_LIBRARY_PATH` for CUDA libraries
- `RUST_LOG=error` to suppress Vulkan warnings
- Activates `.venv` automatically

---

## System Requirements

- **Python**: 3.12+
- **OS**: Linux (Wayland or X11)
- **Audio**: Working microphone
- **GPU** (optional): CUDA-compatible NVIDIA GPU for fast transcription

### Dependencies

See `requirements.txt` for the full list. Key dependencies:

- `faster-whisper` / `ctranslate2` — Whisper inference
- `PyQt6` — User interface
- `sounddevice` / `webrtcvad` — Audio capture and VAD
- `pynput` / `evdev` — Hotkey detection

---

## Configuration

Settings are managed through the Settings dialog (accessible via the menu).

Key options include:
- **Device**: `auto`, `cuda`, or `cpu`
- **Compute type**: `float16`, `float32`, or `int8`
- **Language**: Transcription language (default: English)
- **Activation key**: Hotkey to start/stop recording

All settings take effect immediately.

---

## Documentation

### User Documentation

- [Installation Guide](docs/wiki/Installation-Guide.md) — Complete setup instructions
- [Recording](docs/wiki/Recording.md) — How recording and transcription work
- [Hotkey System](docs/wiki/Hotkey-System.md) — evdev/pynput backends
- [Troubleshooting](docs/wiki/Troubleshooting.md) — Common issues and solutions

### Developer Documentation

- [Backend Architecture](docs/wiki/Backend-Architecture.md) — Module structure and design patterns
- [Threading Model](docs/wiki/Threading-Model.md) — Qt signals/slots and worker threads
- [Configuration Schema](docs/wiki/Configuration-Schema.md) — YAML-based settings

---

## For Developers

### Architecture Overview

Vociferous uses an **intent-driven interaction model**. User actions are represented as explicit intent objects, validated against the current application state, and either accepted or rejected with a clear reason. This architecture is documented and frozen as of Beta 2.0.

### Frozen Architecture Documents

The interaction core is semantically sealed. These documents define how the system works:

- [Interaction Core Freeze Declaration](docs/dev/interaction-core-frozen.md) — What is frozen and why
- [Intent Catalog](docs/dev/intent-catalog.md) — Complete vocabulary of user intents
- [Authority Invariants](docs/dev/authority-invariants.md) — Who owns state transitions
- [Edit Invariants](docs/dev/edit-invariants.md) — Transactional editing guarantees

### Contributing

Changes that violate the architectural guardrail tests are invalid and will not be accepted. Before contributing:

1. Read the [Interaction Core Freeze Declaration](docs/dev/interaction-core-frozen.md)
2. Run `pytest tests/test_architecture_guardrails.py` to verify compliance
3. Follow the extension pattern documented in the freeze declaration

### Quality Checks

Run all checks before committing:

```bash
./scripts/check.sh
```

#### Tools Configured

##### 1. **Ruff** (Linting & Formatting)
Fast Python linter and formatter, replaces flake8, black, isort, and more.

**Usage:**
```bash
# Check for issues
python -m ruff check .

# Auto-fix issues
python -m ruff check --fix .

# Format code
python -m ruff format .
```

**Config:** [pyproject.toml](pyproject.toml)

##### 2. **MyPy** (Static Type Checking)
Validates Python 3.12+ type hints to catch type-related bugs.

**Usage:**
```bash
python -m mypy src/
```

**Config:** [mypy.ini](mypy.ini)

**Note:** ~331 errors are Qt6-related false positives (union-attr, override issues) and are acceptable.

##### 3. **Bandit** (Security Scanner)
Finds common security issues in Python code.

**Usage:**
```bash
# Basic scan
python -m bandit -r src/

# JSON output
python -m bandit -r src/ -f json
```

**Findings:** 10 LOW severity issues (subprocess usage in `input_simulation.py` and `clipboard_utils.py` - all intentional for Linux keyboard/clipboard control).

##### 4. **Pytest** (Unit Testing)
Comprehensive test suite with 125+ tests covering core functionality.

**Usage:**
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_ui_components.py

# Run with coverage
pytest --cov=src --cov-report=html
```

**Config:** [pytest.ini](pytest.ini)

#### CI/CD Integration

The `scripts/check.sh` script is designed for CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run quality checks
  run: ./scripts/check.sh
```

Exit codes:
- `0` - All checks passed
- `1` - One or more checks failed

#### Manual Fixes

**Fix all auto-fixable issues:**
```bash
python -m ruff check --fix .
python -m ruff format .
```

**View detailed errors:**
```bash
# Ruff errors
python -m ruff check .

# Type errors
python -m mypy src/

# Security issues
python -m bandit -r src/ -f screen
```

#### Installing Tools

All tools are in [requirements.txt](requirements.txt):

```bash
pip install -r requirements.txt
```

Or install individually:
```bash
pip install ruff mypy bandit pytest types-PyYAML
```

#### Baseline Quality Metrics

As of January 9, 2026:

| Tool | Status | Details |
|------|--------|---------|
| **Ruff Linting** | ✅ Pass | 0 errors |
| **Ruff Formatting** | ✅ Pass | All files formatted |
| **MyPy** | ✅ Pass | 331 Qt false positives (acceptable) |
| **Bandit** | ✅ Pass | 10 LOW severity (expected) |
| **Pytest** | ✅ Pass | 125 passed, 1 skipped |

#### Pre-commit Hooks (Optional)

Install pre-commit hooks to run checks automatically:

```bash
pip install pre-commit
pre-commit install
```

Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

### Versioning Policy

- **2.0.x** — Stabilization releases (no new features, bug fixes only)
- **2.1.x** — Feature development resumes (local SLM integration planned)

---

## License

See [LICENSE](LICENSE) for details.
