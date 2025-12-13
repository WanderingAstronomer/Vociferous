# Vociferous Architecture Guide

> A comprehensive guide to the design, patterns, and implementation of Vociferous - a modern Python speech-to-text dictation application.

## Table of Contents

1. [Overview](#overview)
2. [User Experience](#user-experience)
3. [High-Level Architecture](#high-level-architecture)
4. [Module Reference](#module-reference)
5. [Design Patterns](#design-patterns)
6. [Data Flow](#data-flow)
7. [Threading Model](#threading-model)
8. [Platform Compatibility](#platform-compatibility)
9. [Dependencies](#dependencies)
10. [Configuration System](#configuration-system)
11. [Python 3.12+ Features](#python-312-features)

---

## Overview

Vociferous is a speech-to-text dictation tool for Linux. Press a hotkey to start recording, press again to transcribe your speech and inject the text into any application.

### Key Characteristics

- **Wayland-first**: Works on modern Linux (Wayland and X11)
- **GPU-accelerated**: Uses faster-whisper with CUDA for real-time transcription
- **Minimal UI**: System tray icon + floating status window
- **Modern Python**: Leverages Python 3.12+ features throughout

---

## User Experience

### Typical Usage Flow

```mermaid
sequenceDiagram
    participant User
    participant Vociferous
    participant Whisper
    participant TargetApp as Target Application

    Note over User,TargetApp: Application is running in background
    User->>Vociferous: Press activation key (Right Alt)
    Vociferous->>Vociferous: Start recording
    Note over Vociferous: Status window appears:<br/>🎤 "Recording..."
    
    User->>Vociferous: Speaks into microphone
    Note over Vociferous: Audio buffered with VAD filtering
    
    User->>Vociferous: Press activation key again
    Vociferous->>Vociferous: Stop recording
    Note over Vociferous: Status window updates:<br/>✏️ "Transcribing..."
    
    Vociferous->>Whisper: Process audio buffer
    Whisper-->>Vociferous: Return transcribed text
    
    Vociferous->>TargetApp: Inject text via input simulation
    Note over TargetApp: Text appears as if typed
    
    Vociferous->>Vociferous: Return to idle
    Note over Vociferous: Status window disappears
```

### Step-by-Step Workflow

#### 1. Launch & Initialization

```bash
./vociferous.sh  # or python run.py
```

**What happens:**
- GPU libraries configured (if CUDA available)
- Whisper model loaded into memory (~1-2GB VRAM for distil-large-v3)
- System tray icon appears (no main window)
- Hotkey listener starts monitoring keyboard
- Status: **Idle** (waiting for activation)

#### 2. Start Recording

**User action:** Press activation key (default: Right Alt)

**What happens:**
- Status window appears at bottom-center of screen
- Shows microphone icon 🎤 and "Recording..." text
- Audio capture begins (16kHz mono, buffered in queue)
- VAD (Voice Activity Detection) monitors for speech
- Status: **Recording**

**Visual feedback:**
```
╔═══════════════════════════════╗
║  🎤  Recording...             ║
╚═══════════════════════════════╝
```

#### 3. Speaking

**User action:** Speak naturally into microphone

**What happens:**
- Audio frames continuously captured by sounddevice
- WebRTC VAD analyzes each 30ms frame for speech
- Speech frames added to buffer, silence trimmed
- Recording continues until user stops (or VAD timeout in voice_activity_detection mode)

**Alternative modes:**
- **press_to_toggle** (default): Press once to start, again to stop
- **hold_to_record**: Hold key down, release to stop
- **voice_activity_detection**: Auto-stops after 900ms silence

#### 4. Stop Recording

**User action:** Press activation key again

**What happens:**
- Audio capture stops
- Status window updates to pencil icon ✏️
- Text changes to "Transcribing..."
- Audio buffer sent to Whisper model
- Status: **Transcribing**

**Visual feedback:**
```
╔═══════════════════════════════╗
║  ✏️  Transcribing...          ║
╚═══════════════════════════════╝
```

#### 5. Transcription Processing

**What happens behind the scenes:**
- Audio converted from int16 → float32
- VAD filter applied (removes silence)
- Whisper processes audio in segments
- Text segments combined and post-processed
- Trailing space added (if configured)

**Timing:**
- Short phrase (5 seconds): ~0.5-1 second
- Long recording (30 seconds): ~2-4 seconds
- GPU (float16) is ~4x faster than CPU

#### 6. Text Injection

**What happens:**
- Focus remains on the application you were using
- Transcribed text injected via configured method:
  - **pynput** (X11): Simulated keystrokes via XTEST
  - **dotool/ydotool** (Wayland): Virtual uinput device
  - **clipboard** (fallback): Text copied for manual paste
- Text appears as if you typed it character-by-character

**Example:**
```
You said: "Hello world, this is a test."
Result:   Hello world, this is a test. ← appears in focused app
```

#### 7. Return to Idle

**What happens:**
- Status window fades out and closes
- System tray icon remains active
- Hotkey listener continues monitoring
- Ready for next dictation
- Status: **Idle**

### Configuration Options

Users can customize behavior via `~/.config/vociferous/config.yaml`:

```yaml
recording_options:
  activation_key: alt_right        # Default: Right Alt
  recording_mode: press_to_toggle  # or hold_to_record, voice_activity_detection
  silence_duration: 900            # Auto-stop after 900ms silence (VAD mode)
  input_backend: evdev             # or pynput, auto

model_options:
  model: distil-large-v3           # Fast, accurate distilled model
  device: cuda                     # or cpu, auto
  compute_type: float16            # or float32, int8

output_options:
  input_method: pynput             # or ydotool, dotool, clipboard
  add_trailing_space: true         # Space after transcription
```

### Common Usage Patterns

#### Email Composition
1. Open email client, click in message body
2. Press activation key
3. Dictate: "Hi team, I wanted to follow up on yesterday's meeting..."
4. Press activation key
5. Text appears in email

#### Terminal Commands
1. Open terminal
2. Press activation key
3. Dictate: "git commit dash m fix bug in authentication module"
4. Press activation key
5. Edit the injected text as needed

#### Document Writing
1. Open text editor
2. Press activation key repeatedly for paragraphs
3. Dictate each paragraph, pause between
4. Minimal editing needed due to Whisper's accuracy

### Error Handling

**No microphone detected:**
- Error logged to terminal
- Status window shows error state briefly
- Returns to idle

**CUDA libraries missing:**
- App falls back to CPU automatically
- Warning logged, but continues working

**Input simulation fails (Wayland permission issue):**
- Falls back to clipboard method
- User pastes with Ctrl+V manually
- Logs suggest running with input group or using dotool

**Model download needed:**
- First run downloads model from Hugging Face
- Progress bar shown in terminal
- Cached in `~/.cache/huggingface/` for subsequent runs

### Performance Characteristics

| Scenario | GPU (float16) | CPU (float32) |
|----------|---------------|---------------|
| 5-second clip | ~0.5 sec | ~2 sec |
| 30-second clip | ~2 sec | ~8 sec |
| Memory usage | 2GB VRAM | 4GB RAM |
| First-time load | 3-5 sec | 5-10 sec |

### Background Operation

Vociferous runs continuously in the background:

- **System Resources**: ~200MB RAM idle, 1-2GB during transcription
- **CPU Usage**: Near-zero when idle, spikes during transcription
- **GPU Usage**: 0% idle, 20-40% during transcription
- **No Polling**: Event-driven architecture (no CPU wasted checking for keys)

---

## High-Level Architecture

```mermaid
graph TB
    subgraph Entry["Entry Point"]
        run[run.py]
    end

    subgraph Core["Core Application"]
        main[main.py<br/>VociferousApp]
        config[utils.py<br/>ConfigManager]
    end

    subgraph Input["Input Handling"]
        listener[key_listener.py<br/>KeyListener]
        evdev[EvdevBackend<br/>Wayland]
        pynput_in[PynputBackend<br/>X11]
    end

    subgraph Audio["Audio Pipeline"]
        result[result_thread.py<br/>ResultThread]
        transcribe[transcription.py<br/>Whisper]
    end

    subgraph Output["Text Output"]
        simulator[input_simulation.py<br/>InputSimulator]
        dotool[dotool/ydotool<br/>Wayland]
        pynput_out[pynput<br/>X11]
    end

    subgraph UI["User Interface"]
        status[StatusWindow]
        base[BaseWindow]
        tray[System Tray]
    end

    run --> main
    main --> config
    main --> listener
    main --> result
    main --> simulator
    main --> status
    main --> tray

    listener --> evdev
    listener --> pynput_in

    result --> transcribe

    simulator --> dotool
    simulator --> pynput_out

    status --> base
```

---

## Module Reference

### `run.py` - Application Entry Point

**Purpose**: Bootstrap the application with correct environment setup.

**Key Responsibilities**:
- Configure LD_LIBRARY_PATH for CUDA libraries (re-exec pattern)
- Set up Python path for `src/` imports
- Configure logging
- Launch main application

**Why it exists**: LD_LIBRARY_PATH must be set *before* Python loads CUDA libraries. This requires process re-execution.

---

### `src/main.py` - Application Orchestrator

**Purpose**: Wire all components together and manage lifecycle.

**Key Classes**:
- `VociferousApp(QObject)` - Main application coordinator

**Responsibilities**:
- Create and manage all components
- Handle hotkey callbacks
- Route signals between components
- System tray management

```mermaid
classDiagram
    class VociferousApp {
        +QApplication app
        +KeyListener key_listener
        +WhisperModel local_model
        +ResultThread result_thread
        +StatusWindow status_window
        +InputSimulator input_simulator
        +QSystemTrayIcon tray_icon
        +initialize_components()
        +on_activation()
        +on_deactivation()
        +cleanup()
        +run()
    }
```

---

### `src/utils.py` - Configuration Management

**Purpose**: Thread-safe, singleton configuration manager with schema validation.

**Key Classes**:
- `ConfigManager` - Singleton configuration manager

**Design Patterns**:
- **Singleton**: One global configuration instance
- **Double-Checked Locking**: Thread-safe initialization
- **Schema-Driven**: YAML schema defines valid configuration

```mermaid
classDiagram
    class ConfigManager {
        -_instance: ConfigManager$
        -_lock: threading.Lock$
        -_initialized: bool$
        +_config: dict
        +_schema: dict
        +initialize()$
        +get_config_value(section, key)$
        +set_config_value(section, key, value)$
        +load_default_config()
        +load_user_config()
    }
```

---

### `src/key_listener.py` - Hotkey Detection

**Purpose**: Monitor keyboard for activation hotkey across display servers.

**Key Classes**:
- `InputBackend(Protocol)` - Interface for input backends
- `KeyChord` - Represents key combination
- `KeyListener` - Manages backends and chord detection
- `EvdevBackend` - Linux evdev implementation (Wayland)
- `PynputBackend` - pynput implementation (X11)

**Design Patterns**:
- **Strategy Pattern**: Swappable input backends
- **Protocol (Structural Typing)**: Duck-typed backend interface
- **Observer Pattern**: Callback-based activation notification

```mermaid
classDiagram
    class InputBackend {
        <<Protocol>>
        +is_available() bool
        +start()
        +stop()
        +on_input_event(event)
    }

    class EvdevBackend {
        +devices: list
        +thread: Thread
        +stop_event: Event
        +start()
        +stop()
        -_listen_loop()
    }

    class PynputBackend {
        +keyboard_listener
        +mouse_listener
        +start()
        +stop()
    }

    class KeyListener {
        +backends: list
        +active_backend: InputBackend
        +key_chord: KeyChord
        +callbacks: dict
        +start()
        +stop()
        +add_callback()
    }

    InputBackend <|.. EvdevBackend
    InputBackend <|.. PynputBackend
    KeyListener o-- InputBackend
    KeyListener o-- KeyChord
```

---

### `src/result_thread.py` - Audio Recording & Transcription

**Purpose**: Handle audio capture and transcription in background thread.

**Key Classes**:
- `ResultThread(QThread)` - Background worker for audio pipeline

**Key Features**:
- WebRTC VAD for voice activity detection
- Queue-based audio buffering
- Qt signals for cross-thread communication

```mermaid
sequenceDiagram
    participant Main as Main Thread
    participant RT as ResultThread
    participant SD as sounddevice
    participant VAD as WebRTC VAD
    participant Whisper as faster-whisper

    Main->>RT: start()
    RT->>RT: emit('recording')
    RT->>SD: InputStream(callback)

    loop Audio Capture
        SD-->>RT: audio frames (via Queue)
        RT->>VAD: is_speech(frame)?
        alt Speech detected
            RT->>RT: Continue recording
        else Silence threshold
            RT->>RT: Stop recording
        end
    end

    RT->>RT: emit('transcribing')
    RT->>Whisper: transcribe(audio)
    Whisper-->>RT: text result

    RT->>RT: emit('idle')
    RT->>Main: resultSignal(text)
```

---

### `src/transcription.py` - Whisper Integration

**Purpose**: Interface with faster-whisper for speech-to-text.

**Key Functions**:
- `create_local_model()` - Factory for WhisperModel
- `transcribe()` - Convert audio to text
- `post_process_transcription()` - Clean up output

**Features**:
- GPU/CPU auto-selection
- VAD filtering in Whisper
- Configurable model size and compute type

---

### `src/input_simulation.py` - Text Injection

**Purpose**: Type transcribed text into the focused application.

**Key Classes**:
- `InputSimulator` - Multi-backend text injector

**Supported Backends**:
| Backend | Protocol | How It Works |
|---------|----------|--------------|
| pynput | X11 | XTEST extension |
| ydotool | Wayland | Virtual uinput device |
| dotool | Wayland | Persistent uinput process |
| clipboard | Any | Copy for manual paste |

---

### `src/ui/base_window.py` - Custom Window Base

**Purpose**: Frameless, draggable window with rounded corners.

**Key Classes**:
- `BaseWindow(QMainWindow)` - Custom window base class

**Features**:
- Translucent background with custom painting
- Drag-to-move from anywhere
- Custom title bar with close button

---

### `src/ui/status_window.py` - Status Display

**Purpose**: Floating indicator showing recording/transcribing state.

**Key Classes**:
- `StatusWindow(BaseWindow)` - Status indicator window

**Features**:
- Auto-positioning at screen bottom
- Icon changes based on state
- Stays on top of other windows

---

## Design Patterns

### 1. Singleton Pattern (ConfigManager)

```python
class ConfigManager:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def initialize(cls):
        if cls._instance is None:
            with cls._lock:  # Double-checked locking
                if cls._instance is None:
                    cls._instance = cls()
```

**Why**: Configuration should be consistent across the entire application. A singleton ensures all modules see the same config.

---

### 2. Strategy Pattern (Input Backends)

```python
class KeyListener:
    def __init__(self):
        self.backends = [cls() for cls in [EvdevBackend, PynputBackend]
                        if cls.is_available()]
        self.active_backend = self.backends[0]
```

**Why**: Different display servers (X11, Wayland) require different input methods. Strategy pattern lets us swap implementations without changing the KeyListener.

---

### 3. Protocol (Structural Typing)

```python
@runtime_checkable
class InputBackend(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
```

**Why**: More Pythonic than ABC. Classes don't need to inherit from Protocol - they just need matching methods. Enables easy mocking in tests.

---

### 4. Observer Pattern (Callbacks)

```python
class KeyListener:
    def add_callback(self, event: str, callback: Callable):
        self.callbacks[event].append(callback)

    def _trigger_callbacks(self, event: str):
        for callback in self.callbacks.get(event, []):
            callback()
```

**Why**: Decouples the key listener from the main app. KeyListener doesn't know about VociferousApp - it just calls callbacks when events occur.

---

### 5. Mediator Pattern (VociferousApp)

```python
class VociferousApp:
    def __init__(self):
        self.key_listener.add_callback("on_activate", self.on_activation)
        self.result_thread.resultSignal.connect(self.on_transcription_complete)
```

**Why**: VociferousApp coordinates communication between components. KeyListener, ResultThread, StatusWindow don't know about each other - they communicate through VociferousApp.

---

## Data Flow

```mermaid
flowchart LR
    subgraph Input
        KB[Keyboard]
    end

    subgraph Detection
        EV[evdev/pynput]
        KL[KeyListener]
        KC[KeyChord]
    end

    subgraph Recording
        SD[sounddevice]
        Q[Queue]
        VAD[WebRTC VAD]
    end

    subgraph Transcription
        RT[ResultThread]
        WH[faster-whisper]
    end

    subgraph Output
        IS[InputSimulator]
        APP[Target App]
    end

    KB --> EV --> KL --> KC
    KC -->|activate| RT
    SD --> Q --> VAD --> RT
    RT --> WH --> IS --> APP
```

---

## Threading Model

```mermaid
graph TB
    subgraph MainThread["Main Thread (Qt Event Loop)"]
        App[VociferousApp]
        UI[StatusWindow]
        Tray[System Tray]
        Signals[Signal Handlers]
    end

    subgraph EvdevThread["Evdev Listener Thread (daemon)"]
        Listen[_listen_loop]
        Select[select() on devices]
    end

    subgraph AudioThread["OS Audio Thread"]
        Callback[audio_callback]
    end

    subgraph ResultThread["QThread"]
        Record[_record_audio]
        Transcribe[transcribe]
    end

    EvdevThread -->|callbacks| MainThread
    AudioThread -->|Queue| ResultThread
    ResultThread -->|Qt Signals| MainThread
```

### Thread Safety Mechanisms

| Mechanism | Used By | Purpose |
|-----------|---------|---------|
| `threading.Lock` | ConfigManager | Protect singleton init |
| `QMutex` | ResultThread | Protect is_running/is_recording |
| `Queue` | ResultThread | Thread-safe audio buffer |
| `threading.Event` | EvdevBackend | Graceful shutdown signal |
| Qt Signals | All | Cross-thread communication |

---

## Platform Compatibility

### Display Server Support

```mermaid
graph LR
    subgraph Wayland
        evdev[evdev backend]
        dotool[dotool output]
        ydotool[ydotool output]
    end

    subgraph X11
        pynput_in[pynput input]
        pynput_out[pynput output]
    end

    subgraph Both
        clipboard[Clipboard fallback]
    end
```

### Why Two Input Backends?

| Feature | evdev | pynput |
|---------|-------|--------|
| Works on Wayland | ✅ | ❌ (limited) |
| Requires `input` group | ✅ | ❌ |
| Works on X11 | ✅ | ✅ |
| Complexity | Higher | Lower |

**Decision**: Use evdev by default (Wayland support), fall back to pynput.

---

## Dependencies

### Core Dependencies

```mermaid
graph TD
    subgraph ML["Machine Learning"]
        FW[faster-whisper 1.2.1]
        CT[ctranslate2 4.6.2]
        AV[av 16.0.0]
    end

    subgraph Audio["Audio Processing"]
        SD[sounddevice 0.5.3]
        VAD[webrtcvad]
    end

    subgraph UI["User Interface"]
        Qt[PyQt5 5.15.11]
    end

    subgraph Input["Input/Output"]
        ED[evdev 1.9.2]
        PN[pynput 1.8.1]
    end

    FW --> CT
    FW --> AV
```

### Dependency Purposes

| Package | Purpose |
|---------|---------|
| **faster-whisper** | CTranslate2-based Whisper, 4x faster than original |
| **ctranslate2** | Optimized inference engine for transformers |
| **av** (PyAV) | Audio decoding (required by faster-whisper) |
| **sounddevice** | Cross-platform audio I/O |
| **webrtcvad** | Google's Voice Activity Detection |
| **PyQt5** | Cross-platform GUI framework |
| **evdev** | Linux input device interface |
| **pynput** | Cross-platform keyboard/mouse control |

---

## Configuration System

### Schema-Driven Configuration

The configuration is defined in `config_schema.yaml`:

```yaml
recording_options:
  activation_key:
    type: str
    default: "ctrl+shift+space"
  input_backend:
    type: str
    default: "auto"
    options: ["auto", "evdev", "pynput"]
```

### Configuration Flow

```mermaid
flowchart LR
    Schema[config_schema.yaml] --> Default[Default Config]
    User[~/.config/vociferous/config.yaml] --> Merge
    Default --> Merge[Merged Config]
    Merge --> Runtime[Runtime Config]
```

### Why Schema-Driven?

1. **Validation**: Invalid values caught at load time
2. **Defaults**: New settings get sensible defaults
3. **Documentation**: Schema serves as config reference
4. **Type Safety**: Schema defines expected types

---

## Python 3.12+ Features

Vociferous uses modern Python features throughout:

### Match/Case Statements

```python
# Status handling
match status:
    case 'recording':
        self.show()
    case 'transcribing':
        self.icon_label.setPixmap(self.pencil_pixmap)
    case 'idle' | 'error':  # Pattern union
        self.close()

# Error handling with type matching
match error:
    case BlockingIOError() if error.errno == errno.EAGAIN:
        return True
    case OSError() if error.errno in (errno.EBADF, errno.ENODEV):
        return False
```

### Modern Type Hints

```python
# Union syntax (no Optional import needed)
local_model: WhisperModel | None = None

# Generic collections (no typing import needed)
backends: list[InputBackend] = []
callbacks: dict[str, list[Callable[[], None]]] = {}

# Complex unions
keys: set[KeyCode | frozenset[KeyCode]]
```

### Dataclasses with Slots

```python
@dataclass(slots=True)
class KeyChord:
    keys: set[KeyCode | frozenset[KeyCode]]
    pressed_keys: set[KeyCode] = field(default_factory=set)
```

### Protocol for Structural Typing

```python
@runtime_checkable
class InputBackend(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
```

### Pathlib for Path Operations

```python
# Modern
venv_path = Path(__file__).parent / '.venv'
cudnn_lib = site_packages / 'nvidia' / 'cudnn' / 'lib'

# Instead of
venv_path = os.path.join(os.path.dirname(__file__), '.venv')
```

### contextlib.suppress

```python
# Clean exception suppression
from contextlib import suppress

with suppress(ProcessLookupError, OSError):
    proc.terminate()

# Instead of
try:
    proc.terminate()
except (ProcessLookupError, OSError):
    pass
```

---

## Directory Structure

```
vociferous/
├── run.py                 # Entry point (GPU setup)
├── src/
│   ├── main.py           # Application orchestrator
│   ├── utils.py          # ConfigManager singleton
│   ├── key_listener.py   # Hotkey detection
│   ├── result_thread.py  # Audio recording & transcription
│   ├── transcription.py  # Whisper integration
│   ├── input_simulation.py # Text injection
│   ├── config_schema.yaml # Configuration schema
│   └── ui/
│       ├── base_window.py   # Custom frameless window
│       └── status_window.py # Status indicator
├── assets/
│   ├── ww-logo.png
│   ├── microphone.png
│   └── pencil.png
├── tests/
│   └── ...
└── docs/
    └── ARCHITECTURE.md   # This file
```

---

## Further Reading

- [faster-whisper documentation](https://github.com/guillaumekln/faster-whisper)
- [PyQt5 documentation](https://www.riverbankcomputing.com/static/Docs/PyQt5/)
- [evdev documentation](https://python-evdev.readthedocs.io/)
- [Python 3.12 release notes](https://docs.python.org/3.12/whatsnew/3.12.html)
