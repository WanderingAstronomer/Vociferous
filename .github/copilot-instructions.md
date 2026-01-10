# Vociferous - AI Agent Instructions

## Project Overview
Vociferous is a modern Python 3.12+ speech-to-text dictation application for Linux using OpenAI's Whisper via **faster-whisper**. It features a **PyQt6** GUI with system tray integration, global hotkey support (Wayland/X11), and pluggable input/output backends.

## Architecture

### Core Components
- **Orchestrator**: `src/main.py` initializes components (`KeyListener`, `ResultThread`, `MainWindow`) and coordinates via Qt signals.
- **Threading**: `src/result_thread.py` runs audio recording and transcription in a background `QThread`.
    - **Critical**: Never block the main thread. All heavy lifting (Whisper inference) must be off-thread.
    - **Communication**: Use `pyqtSignal` for all cross-thread updates.
- **UI Layer**: Located in `src/ui/`.
    - Component-based architecture (`src/ui/components/`).
    - `MainWindow` integrates `Sidebar`, `Workspace`, and `MetricsStrip`.
    - Styles are often defined inline or in widgets.
    - **Note**: The UI supports both mouse interaction and keyboard shortcuts.
- **Configuration**: Singleton `ConfigManager` in `src/utils.py` driven by `src/config_schema.yaml`.
    - **Pattern**: `ConfigManager.get_config_value("section", "key")`.
    - **Hot-reload**: Components subscribe to `configChanged` signal.

### Input/Output Backends
- **Input (`src/key_listener.py`)**:
    - **Protocol**: `InputBackend` (start, stop, on_input_event).
    - **Impls**: `EvdevBackend` (Wayland/Raw), `PynputBackend` (X11).
- **Output (`src/input_simulation.py`)**:
    - **Strategies**: `pynput` (X11), `dotool`/`ydotool` (Wayland), `clipboard` (Fallback).
    - **Injection**: Copies text to clipboard -> triggers Ctrl+V -> restores clipboard (optional).

## Development Workflows

### Running the App
**ALWAYS** use the wrapper script to ensure GPU libraries are loaded correctly:
```bash
python scripts/run.py
```
*Note: `scripts/run.py` sets `LD_LIBRARY_PATH` and re-execs the process before loading CUDA. Do not run `src/main.py` directly if you need GPU acceleration.*

### Testing
- Run all tests: `pytest`
- Run specific file: `pytest tests/test_ui_integration.py`
- **Fixtures**: `tests/conftest.py` provides `config_manager`, `key_listener`.
- **UI Tests**: specific UI tests in `tests/test_ui_components.py`.

### Environment
- **Python**: 3.12+ (Required for type hint features).
- **Dependencies**: `requirements.txt`.
    - **Numpy**: `>=2.0.0`
    - **Whisper**: `faster-whisper` + `ctranslate2`

## Code Conventions

### Modern Python (3.12+)
- **Type Hints**: Use native unions `str | int`, generic collections `list[str]`, `dict[str, Any]`.
- **Pattern Matching**: Use `match/case` for state machines and event handling (especially in `ResultThread` state and `KeyListener` events).
- **Dataclasses**: Use `@dataclass(slots=True)` for value objects (e.g. `ThreadResult`).

### Qt / UI Patterns
- **Signals**: Define signals at class level: `mySignal = pyqtSignal(str)`.
- **Cleanup**: Implement `cleanup()` methods for threads/listeners. Connect `finished` signals to `deleteLater`.
- **Imports**: Use `if TYPE_CHECKING:` for heavy imports (like `faster_whisper`) to keep startup fast.
- **Environment**: `os.environ.setdefault("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1")` is set in `main.py` for Wayland/Hyprland compatibility.

### GPU & Wayland Specifics
- **GPU**: CUDA libraries are loaded dynamically. The `scripts/run.py` re-exec pattern is VITAL. Do not bypass it for production/GPU runs.
- **Wayland**:
    - Cannot bind global hotkeys via Qt/X11 methods. Must use `evdev` (requires `input` group permissions).
    - Cannot inject text via standard Qt methods reliably. Must use `dotool`/`ydotool` or clipboard.

## Configuration
- **Schema**: Add new options to `src/config_schema.yaml` first.
- **Access**: `ConfigManager` is the source of truth. Do not hardcode values.
