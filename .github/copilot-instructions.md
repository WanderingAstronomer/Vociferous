# Vociferous - AI Agent Instructions

## Project Overview
Vociferous is a modern Python 3.12+ speech-to-text dictation application for Linux using OpenAI's Whisper via **faster-whisper**. It features a **PyQt6** GUI with system tray integration, global hotkey support (Wayland/X11), and pluggable input/output backends.

## Architecture

### 1. UI Interaction Model (Intent Pattern)
The UI employs a strict **Intent Pattern** (`src/ui/interaction/`) to decouple user desires from execution.
-   **Definition**: User actions (button clicks, hotkeys) MUST fail-over to instantiating an `InteractionIntent` dataclass (e.g., `BeginRecordingIntent`, `ViewTranscriptIntent`).
-   **Propagation**: Intents are passed up the visual hierarchy (Child Widget → Component → MainWindow/Controller).
-   **Execution**: Only core controllers (like `MainWindow`, `MainWorkspace`) may execute state changes based on intents.
-   **Invariant**: Do not allow sibling widgets to communicate directly. Always route through the parent via Signal->Intent->Slot.

### 2. Data Layer (SQLAlchemy ORM)
Persistence is handled by **SQLAlchemy 2.0+** (`src/history_manager.py`, `src/models.py`).
-   **Engine**: SQLite (`~/.config/vociferous/vociferous.db`).
-   **Dual-Text Architecture**:
    -   `raw_text`: Immutable. Original Whisper output. **NEVER EDIT THIS**.
    -   `normalized_text`: Mutable. The user-visible, editable content.
-   **Access**: Use `HistoryManager` methods where possible. If expanding functionality, write new query methods in `HistoryManager` rather than executing raw SQL in UI code.
-   **Performance**: Use `slots=True` on all Data Transfer Objects (DTOs) like `HistoryEntry` to minimize overhead for large lists.

### 3. Core Components
-   **Orchestrator**: `src/main.py` initializes components and coordinates via Qt signals. It enforces **Invariant 8**: It is the *only* entity allowed to push background engine state (Recording/Transcribing) to the UI.
-   **Threading**: `src/result_thread.py` manages audio/inference on a background `QThread`.
    -   **Critical**: Never block the main thread.
    -   **Communication**: Use `pyqtSignal` for all cross-thread updates.
-   **Input (`src/key_listener.py`)**: Pluggable backend protocol (`InputBackend`) supporting `evdev` (Wayland) and `pynput` (X11).

## Development Workflows

### Version Control & Documentation rules
1.  **Changelog Discipline**: Every modification MUST have an entry in `CHANGELOG.md`.
    -   Categorize changes: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.
    -   Be honest about versioning (Major.Minor.Patch).
2.  **Documentation Sync**:
    -   Update `README.md` and relevant `docs/wiki/` files if behavior changes.
    -   Treat documentation divergence as a critical defect.
3.  **Research Journals**: For complex tasks, create a markdown journal in `docs/agent_resources/agent_reports/` before coding.
4.  **Auto-Commit Policy**:
    -   **Safe State**: If a task is completed and the system is stable (tests pass), you MAY automatically commit changes (no push) with a conventional commit message.
    -   **Unsafe/Partial**: If stability is unverified, DO NOT commit. Instead, explicitly recommend a manual commit in the Post-Task Recommendation.
5.  **Risk Management (Branching)**:
    -   **Stop Protocol**: If a user request implies significant architectural changes or high-risk refactoring, **STOP** and ask if they wish to create a new feature branch before proceeding.
6.  **Definition of Done (Quality Assurance)**:
    -   A task is ONLY "complete" if:
        1.  **Ruff**: Passes with no errors (`ruff check .`).
        2.  **MyPy**: Passes with no errors (`mypy .`).
        3.  **Tests**: ALL unit tests pass (`pytest`), not just the ones related to your changes.

### Virtual Environment
**CRITICAL**: You MUST use the project's virtual environment for ALL operations.
-   Access: `.venv/bin/python`, `.venv/bin/pip`, `.venv/bin/ruff`, etc.
-   Do not rely on system python or global packages.

### Running the App
**ALWAYS** use the wrapper script to handle GPU/LD_LIBRARY_PATH:
```bash
python scripts/run.py
```

### Environment
-   **Python**: 3.12+ (Type hints required).
-   **Dependencies**: `faster-whisper`, `ctranslate2`, `PyQt6`, `SQLAlchemy`.

## Code Conventions

### Modern Python (3.12+)
-   **Type Hints**: Use native unions `str | int`, generic collections `list[str]`, `dict[str, Any]`.
-   **Pattern Matching**: Use `match/case` for state machines and intent handling.
-   **Dataclasses**: Use `@dataclass(slots=True, frozen=True)` for Intents and value objects.

### Qt / UI Patterns
-   **Styling**: use `src/ui/styles/unified_stylesheet.py`. NO ad-hoc `setStyleSheet()`.
-   **Cleanup**: Implement `cleanup()` on all long-lived objects.
-   **Imports**: Use `if TYPE_CHECKING:` for heavy imports (AI libraries) to optimize startup time.

### GPU & Wayland
-   **Wayland**: Requires `evdev` for global hotkeys (needs `input` group). `QT_WAYLAND_DISABLE_WINDOWDECORATION=1` is default.
-   **GPU**: Handled via `scripts/run.py`.

## Configuration
-   **Source of Truth**: `src/config_schema.yaml` defines structure; `ConfigManager` provides access.
