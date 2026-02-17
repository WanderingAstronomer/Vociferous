# Architecture

## Overview

Vociferous is a desktop application that runs a web-based frontend inside a native window shell. The Python backend provides REST and WebSocket APIs; the Svelte frontend communicates exclusively through these APIs, treating the backend as a remote server even though everything runs locally.

## Threading Model

```
┌──────────────────┐
│   Main Thread     │  pywebview (GTK/Cocoa/EdgeChromium)
│   UI Event Loop   │  ZERO blocking operations allowed
└──────────────────┘
         │
         │ localhost:18900
         ▼
┌──────────────────┐
│   API Thread      │  Litestar (async) + uvicorn
│   REST + WS       │  Handles HTTP requests and WebSocket connections
└──────────────────┘
         │
         ├─── CommandBus dispatch ──▶ Handler logic
         │
         ▼
┌──────────────────┐     ┌──────────────────┐
│  Recording Thread │     │   SLM Thread      │
│  Audio + ASR      │     │   Text Refinement  │
│  pywhispercpp     │     │   llama-cpp-python  │
│  (background)     │     │   (mutex-locked)    │
└──────────────────┘     └──────────────────┘
```

### Rules

- **Main thread**: Only `pywebview` window management. No I/O, no computation.
- **API thread**: Async handlers only. Never call blocking functions in `async def`.
- **Recording thread**: Audio capture via `sounddevice` + ASR inference. Runs in a background `Thread`.
- **SLM thread**: Refinement inference with a `threading.Lock()` to prevent concurrent model access.

## Composition Root

`src/core/application_coordinator.py` is the single Composition Root. It:

1. Creates and owns `CommandBus`, `EventBus`, `TranscriptDB`
2. Loads ASR model (`pywhispercpp`)
3. Initializes `SLMRuntime` (refinement engine)
4. Creates `AudioService` (recording pipeline)
5. Creates `KeyListener` (global hotkey detection)
6. Starts `Litestar` API server in a background thread
7. Creates and runs the `pywebview` window (blocks on main thread)
8. Orchestrates graceful shutdown in reverse order

## H-Pattern (Intent-Driven Interaction)

All state mutations follow this path:

```
Frontend UI
    │
    ▼ POST /api/intents { type: "...", payload: {...} }
    │
API Controller
    │
    ▼ CommandBus.dispatch(intent)
    │
Handler (in ApplicationCoordinator)
    │
    ▼ Service logic (database, audio, SLM)
    │
EventBus.emit("event_name", data)
    │
    ▼ WebSocket broadcast
    │
Frontend store update (reactive)
```

### Why This Pattern

- **Decoupling**: API handlers don't touch services directly. They dispatch an Intent and return.
- **Traceability**: Every mutation goes through the CommandBus — easy to log, audit, or replay.
- **Thread safety**: The EventBus → WebSocket bridge uses `call_soon_threadsafe` for sync-to-async crossing.
- **Testability**: Integration tests can dispatch Intents directly without HTTP.

## Data Model

### Database Schema (3 tables)

```sql
transcripts
    id INTEGER PRIMARY KEY
    raw_text TEXT NOT NULL           -- immutable original capture
    normalized_text TEXT             -- post-processed text
    timestamp TEXT                   -- ISO-8601 UTC
    duration_ms INTEGER
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL
    current_variant_id INTEGER REFERENCES transcript_variants(id)

transcript_variants
    id INTEGER PRIMARY KEY
    transcript_id INTEGER REFERENCES transcripts(id) ON DELETE CASCADE
    kind TEXT NOT NULL               -- 'raw', 'refined', 'edited'
    text TEXT NOT NULL
    model_id TEXT                    -- SLM model that produced this variant
    created_at TEXT

projects
    id INTEGER PRIMARY KEY
    name TEXT NOT NULL
    color TEXT                       -- hex color code
    parent_id INTEGER REFERENCES projects(id) ON DELETE CASCADE
    created_at TEXT
```

### Immutability Invariant

The `raw_text` column is **never modified** after insertion. All edits and refinements are stored as `transcript_variants` linked to the original transcript. The `current_variant_id` points to the active display version. The `text` property on the `Transcript` dataclass returns the current variant's text, falling back to `normalized_text`, then `raw_text`.

## Event System

The `EventBus` is a thread-safe pub/sub system. Events are emitted from service logic and broadcast to all WebSocket clients.

Key events:
- `transcription_complete` — new transcript captured
- `transcript_deleted` — transcript removed
- `refinement_complete` — SLM produced a new variant
- `refinement_error` — SLM inference failed
- `config_updated` — settings changed
- `project_created` / `project_deleted` — project mutations
- `recording_started` / `recording_stopped` — audio state changes
- `onboarding_required` — ASR model not provisioned

## Service Isolation

```
src/api/     ──imports──▶  src/core/     (buses, settings)
src/api/     ──imports──▶  src/database/ (read-only queries)
src/api/     ✗ NEVER ──▶  src/services/ (no direct service calls)

src/services/ ──imports──▶  src/core/     (buses, settings)
src/services/ ──imports──▶  src/database/ (persistence)
src/services/ ✗ NEVER ──▶  src/api/      (no reverse dependency)
```
