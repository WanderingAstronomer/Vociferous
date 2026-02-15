# Design Decisions

Key architectural choices and the reasoning behind them.

## Why pywebview instead of PyQt6?

PyQt6 was dropped in v4.0 because:

- **Licensing friction** — PyQt6's GPL/commercial license conflicts with rapid iteration
- **Widget maintenance** — 73+ custom Qt widgets were a significant maintenance burden for a solo developer
- **Web ecosystem** — Svelte + Tailwind provides faster UI development with better tooling
- **pywebview + GTK** — Native Linux window shell with minimal overhead; WebKitGTK handles rendering

## Why a subprocess for ASR?

whisper.cpp inference can take seconds. Running it in-process would freeze the UI. The subprocess model:

- **Isolation** — ASR crashes don't kill the UI
- **Responsiveness** — UI thread never blocks on inference
- **Recovery** — `EngineClient` watchdog detects subprocess death and can restart
- **Simplicity** — stdin/stdout IPC avoids socket management complexity

## Why CommandBus + EventBus (not just one)?

Two buses serve different communication patterns:

- **CommandBus** — Synchronous, request-response. User actions that need success/failure feedback. One handler per intent type. UI → Backend.
- **EventBus** — Fire-and-forget, pub/sub. Backend notifications that multiple subscribers may care about. Backend → UI (via WebSocket).

Combining them would conflate request handling with notification broadcasting.

## Why raw sqlite3 instead of an ORM?

SQLAlchemy was dropped in v4.0 because:

- **3 tables** — The data model is simple enough that an ORM adds overhead without benefit
- **WAL mode** — Direct sqlite3 gives explicit control over journaling and locking
- **Transparency** — SQL queries are visible and debuggable without ORM abstraction layers
- **Fewer dependencies** — One less heavy dependency to maintain

## Why Pydantic Settings instead of YAML config?

- **Type safety** — Every setting is typed and validated at load time
- **Defaults** — Complex nested defaults (refinement levels, voice calibration) are defined as Python code
- **Atomic persistence** — JSON serialization with temp-file + rename prevents corruption
- **No schema file** — The Python model IS the schema

## Why Wayland-first?

X11 is legacy. Wayland is the default on modern Linux distributions (GNOME, KDE Plasma 6). The Docker container and runtime both default to Wayland with X11 as an automatic fallback via `GDK_BACKEND=wayland,x11`.

## Why multi-stage Docker build?

- Node.js is only needed for the frontend build step
- The final image contains only Python + system libraries (~slim-bookworm base)
- Frontend assets are static files copied from the builder stage
- Keeps the runtime image lean and reduces attack surface

## Transcript Immutability

Raw transcriptions are **never overwritten**. This is the core data integrity invariant:

- Original capture → stored as `raw_text` in `transcripts` table
- Every edit, refinement, or format change → new row in `transcript_variants`
- `current_variant_id` on transcript points to the active variant
- Full history is always recoverable
