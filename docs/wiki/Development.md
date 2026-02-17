# Development

## Environment Setup

```bash
git clone https://github.com/drewpyun/Vociferous.git
cd Vociferous

# Python backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
npm run build
cd ..
```

## Running

```bash
# Production (serves pre-built frontend)
./vociferous.sh

# Development with hot-reload frontend
cd frontend && npm run dev &    # Vite dev server on :5173
cd .. && python -m src.main     # Backend on :18900
```

## Project Structure

```
src/
├── main.py                     # Entry point — creates ApplicationCoordinator
├── api/                        # Litestar REST + WebSocket server
│   ├── app.py                  # Litestar app factory, route registration
│   ├── deps.py                 # Dependency injection helpers
│   ├── system.py               # System routes (models, health, GPU status)
│   ├── transcripts.py          # Transcript CRUD routes
│   └── projects.py             # Project CRUD routes
├── core/                       # Application plumbing
│   ├── application_coordinator.py  # Composition Root (THE wiring point)
│   ├── command_bus.py          # Intent → Handler dispatch
│   ├── event_bus.py            # Pub/sub event system
│   ├── settings.py             # Pydantic Settings (typed config)
│   ├── constants.py            # Magic strings, paths
│   ├── exceptions.py           # Custom exception hierarchy
│   ├── log_manager.py          # Structured logging setup
│   ├── model_registry.py       # ASR/SLM model metadata
│   ├── resource_manager.py     # XDG paths, data directory management
│   └── intents/                # Intent dataclass definitions
├── database/
│   └── db.py                   # TranscriptDB — SQLite WAL mode
├── services/                   # Business logic (isolated from API)
│   ├── audio_service.py        # Recording pipeline (sounddevice → WAV → ASR)
│   ├── transcription_service.py # ASR inference wrapper
│   ├── slm_runtime.py          # SLM lifecycle management
│   ├── slm_types.py            # SLM data types
│   └── voice_calibration.py    # Voice frequency analysis
├── refinement/
│   └── engine.py               # SLM text refinement (llama-cpp-python)
├── input_handler/              # Global hotkey detection
│   ├── listener.py             # Key listener abstraction
│   ├── chord.py                # Key chord parsing
│   └── backends/               # Platform-specific backends
└── provisioning/               # Model download from Hugging Face
    ├── cli.py                  # CLI interface (Typer)
    ├── core.py                 # Download logic
    └── requirements.py         # Model registry + checksums

frontend/
├── src/
│   ├── App.svelte              # Root component, view routing
│   ├── main.ts                 # Mount point
│   ├── app.css                 # Tailwind CSS v4 entry
│   ├── lib/                    # Shared utilities
│   │   ├── api.ts              # Backend HTTP/WS client
│   │   ├── types.ts            # TypeScript interfaces
│   │   ├── stores.svelte.ts    # Reactive state (Svelte 5 runes)
│   │   ├── selection.svelte.ts # Multi-selection manager
│   │   ├── navigation.svelte.ts # Route/view state
│   │   └── utils.ts            # Formatting, helpers
│   └── views/                  # Page-level components
│       ├── HistoryView.svelte  # Transcript browser + multi-select
│       ├── SearchView.svelte   # Full-text search + multi-select
│       ├── SettingsView.svelte # Config UI
│       ├── UserView.svelte     # User profile + name
│       └── ProjectsView.svelte # Project tree + batch operations
└── public/                     # Static assets
```

## Testing

```bash
# Run all tests
make test
# or
pytest

# Run specific test file
pytest tests/unit/test_database.py

# Run with verbose output
pytest -v

# Run only unit tests
pytest tests/unit/

# Run integration tests
pytest tests/integration/
```

### Test Categories

- **`tests/unit/`** — Pure function and class tests, fully mocked
- **`tests/integration/`** — API route tests, coordinator lifecycle, WebSocket tests
- **`tests/contracts/`** — Resource contract validation
- **`tests/code_quality/`** — Import and structure checks

### Current Stats

- **374 tests**, all passing
- Average run time: ~3 seconds

## Linting & Type Checking

```bash
# Ruff (linting + formatting)
make lint
# or
ruff check src/ tests/

# MyPy (type checking)
make types
# or
mypy src/

# Fix auto-fixable issues
ruff check --fix src/ tests/
```

### Configuration

All tool configuration lives in `pyproject.toml`:

- **Ruff**: Target Python 3.12, line length 120, selected rules (F, E, W, I, UP, B, SIM, RUF)
- **MyPy**: `strict_optional = false`, `ignore_missing_imports = true` (for native extensions without stubs)
- **Pytest**: Test paths `["tests"]`, asyncio mode `auto`

## Makefile Targets

```bash
make dev       # Start Vite dev server + Python backend
make build     # Build frontend for production
make test      # Run pytest
make lint      # Run ruff check
make types     # Run mypy
make clean     # Remove build artifacts
make install   # Run the Linux install script
```

## Common Development Tasks

### Adding a New API Endpoint

1. Define the Intent dataclass in `src/core/intents/`
2. Add the handler in `ApplicationCoordinator._register_handlers()`
3. Add the API route in `src/api/` (thin wrapper that dispatches to CommandBus)
4. Add the TypeScript interface in `frontend/src/lib/types.ts`
5. Wire the frontend call in the appropriate view

### Adding a New Setting

1. Add the field to the appropriate sub-model in `src/core/settings.py`
2. The frontend reads settings via `GET /api/config` and updates via `PATCH /api/config`
3. Settings persist automatically to JSON via atomic write

### Modifying Database Schema

1. Edit `TranscriptDB._init_schema()` in `src/database/db.py`
2. Add migration logic in `_run_migrations()` if changing existing tables
3. Update tests in `tests/unit/test_database.py`
