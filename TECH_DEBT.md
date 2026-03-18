# Vociferous — Technical Debt Assessment

**Date:** 2026-03-18
**Codebase Version:** v6.1.2
**Total LOC:** ~28,250 (Backend: 10,939 | Frontend: 9,927 | Tests: 7,383)

---

## Executive Summary

Vociferous is a **well-structured, mature codebase** with clean separation of concerns
and comprehensive test coverage (27 test files, 466+ tests). The architecture follows
clear patterns (H-Pattern intent dispatch, composition root, event bus) and shows
evidence of deliberate refactoring (the "God Object Slain" coordinator decomposition).

The overall technical debt level is **moderate** — concentrated in specific areas rather
than spread systemically. The primary debt categories are:

1. **Gold Plating** — Usage stats compute 35 dict keys; fewer than 25 are consumed
2. **Speculative Architecture** — Plugin system exists for an ecosystem that doesn't
3. **Maintenance Complexity** — Frontend views exceed 1,000 LOC without decomposition
4. **Pattern Over-Application** — Intent/handler indirection for trivial CRUD operations

No critical bugs or architectural defects were found. The codebase is production-ready
with the caveats noted below.

---

## Severity Guide

| Level | Meaning |
|-------|---------|
| 🔴 **High** | Active maintenance burden or scaling obstacle |
| 🟠 **Medium** | Adds friction but doesn't block development |
| 🟡 **Low** | Cosmetic or future-proofing concern |
| ✅ **Resolved** | Addressed in this assessment |

---

## 1. Dead Code (Resolved)

### ✅ `std_dev()` — `src/core/text_analysis.py`

Population standard deviation function that was defined, exported, and tested but
**never called by any production code**. Likely a remnant of a planned variance
analytics feature that was never shipped. Removed along with its 4 test cases.

### ✅ `DistributionChart.svelte` — Frontend Component

A 183-line Gaussian bell-curve SVG visualization component that was **never imported
by any view or parent component**. Its dependencies (`stdDev()` and
`buildDistributionCurve()` in `textAnalysis.ts`, totalling 40 lines) were also
dead code since their only consumer was this unused component. All removed.

### ✅ Empty PyInstaller Block — `resource_manager.py`

`get_asset_path()` contained a `if getattr(sys, "frozen", False): pass` block
with a comment about "adjusting based on .spec file" but zero implementation.
Dead conditional removed.

---

## 2. Gold Plating

### 🔴 `usage_stats.py` — Over-Computed Statistics (359 LOC)

**The Problem:** `compute_usage_stats()` is a 254-line function that computes a
35-key dictionary. Only ~21 keys are consumed by `InsightManager` and MOTD templates.
The remaining ~14 keys (processing performance metrics, detailed streak calculations,
filler breakdowns) are computed every time but go nowhere.

**Specific Waste:**
- **Processing performance metrics** (transcription speed, refinement WPM, time saved
  by refinement) — ~40 lines of accumulator loops for keys that are stored in the dict
  but never rendered in any UI or template
- **Streak computation** — 30 lines traversing all transcripts to compute
  `current_streak` and `longest_streak`, which appear in MOTD templates but could be
  computed lazily or on-demand
- **Filler breakdown by word** — Per-word filler counting (`_count_fillers_by_word()`)
  computes detailed breakdowns that the backend never uses (the frontend computes its
  own via `countFillersByWord()` in `textAnalysis.ts`)

**Impact:** Every insight refresh or MOTD generation runs the full computation.
Currently negligible (milliseconds), but scales linearly with transcript count.
With 10,000+ transcripts, this becomes noticeable.

**Recommendation:** Split into `compute_core_stats()` (essential 21 keys) and
`compute_extended_stats()` (remaining 14). Call extended only when explicitly
requested. ~100 LOC reduction.

### 🟠 Plugin System — `src/core/plugins/loader.py` (79 LOC)

**The Problem:** A plugin discovery system using `importlib.metadata.entry_points()`
that currently serves exactly two built-in backends (evdev, pynput) — both hardcoded
in the input handler. No external plugins exist, no documentation explains how to
write one, no CI validates the entry point discovery path, and no example plugin is
shipped.

**This is speculative architecture** — code written for a problem that doesn't exist
yet. The 79-line loader adds:
- Duck-type validation via `hasattr()` instead of a Protocol/ABC
- Entry point group registration that is never triggered
- Class-method-only state that can't support runtime unload/reload

**Impact:** Low immediate cost (79 lines isn't huge), but it creates a false
impression of extensibility. If a real plugin ecosystem is planned, this needs
significant rework. If not, it's dead weight.

**Recommendation:** Either (a) remove the entry point loader and hardcode backend
selection directly in `listener.py` (saves 79 lines, removes false extensibility
promise), or (b) if plugins are on the roadmap, invest properly: add a Protocol-based
interface, ship an example plugin, document the API, and add CI coverage.

### 🟡 `InsightCache` Class — `insight_manager.py`

The `InsightCache` class (lines 40–80) is a 41-line wrapper around "read/write a JSON
file." It maintains a `_data` dict, provides `load()`/`save()`/`is_stale()` methods,
and manages a file path. The same functionality could be achieved with 5 lines of
inline `Path.read_text()` / `json.dumps()` in the `InsightManager` class itself.

**Impact:** Minimal. It works correctly and doesn't cause maintenance problems. But
it's a textbook example of premature abstraction — creating a class for something that
doesn't need one.

---

## 3. Maintenance Complexity Hotspots

### 🔴 Frontend View Components — Size and Decomposition

Three view components exceed the point where single-file maintenance becomes painful:

| Component | LOC | State Variables | Functions | WebSocket Handlers |
|-----------|-----|----------------|-----------|-------------------|
| `TranscriptsView.svelte` | 1,126 | 35 | 39 | 12 |
| `TranscribeView.svelte` | 1,053 | 30 | 30 | 12 |
| `UserView.svelte` | 837 | 45 | — | — |

**TranscriptsView** is the worst offender — it implements transcript browsing,
full-text search, tag filtering, bulk refinement progress tracking, and tag assignment
all in one file. At minimum, extracting `TagFilterBar`, `BulkRefineProgress`, and
`TranscriptSearchBar` components would reduce it by ~200 lines and make each concern
independently testable.

**TranscribeView** manages 6 discrete workspace states (idle, recording, transcribing,
ready, viewing, editing) with complex conditional rendering. Extracting a state
machine pattern and splitting state-specific UI into sub-components would reduce it
by ~250 lines.

**UserView** is primarily justified by its 25+ `$derived.by()` metric computation
blocks. Extracting these to a `userMetrics.ts` utility module would make them
testable, reusable, and memoizable.

**Impact:** These are the hardest files to maintain as features scale. Any new
transcript feature touches TranscriptsView. Any new recording workflow state touches
TranscribeView. Both files are approaching the point where a new contributor needs
30+ minutes just to understand the data flow.

### 🟠 `application_coordinator.py` — 9 Responsibilities (745 LOC)

Despite the "God Object Slain" refactor that successfully extracted handler logic,
the coordinator still owns:

1. Application lifecycle (start/shutdown/cleanup)
2. Service initialization (6 services: DB, ASR, SLM, Audio, Input, Insight/MOTD)
3. Handler registration (25+ `bus.register()` calls)
4. Hotkey event dispatch
5. API server management (uvicorn + socket handling)
6. pywebview window lifecycle
7. Engine restart orchestration
8. Port conflict detection (35 lines with 4 nested try/except)
9. Platform quirk handling (Wayland backend detection)

The handler registration is the most maintenance-heavy part — adding a new intent
requires: (1) define intent dataclass, (2) add handler method, (3) import intent in
coordinator, (4) register in `_register_handlers()`. A metadata-driven or
decorator-based registration pattern would reduce this to one step.

### 🟠 `db.py` — Monolithic `recent()` Method (65 LOC, 3 Code Paths)

The `recent()` method handles three separate query patterns (no tags, tag_mode="any",
tag_mode="all") with duplicated count+fetch logic in each branch. Each branch
constructs its own WHERE clause, count query, and fetch query independently.

Bug fixes or query changes need to be applied to all 3 branches. A helper like
`_execute_paginated_query(where_clause, params)` would DRY this to a single path.

**Note:** The duplicated tag enrichment and system tag lookup patterns were extracted
into `_enrich_transcripts_with_tags()` and `_get_system_tag_id()` in this assessment.

### 🟠 `system.py` — API File Mixing 9 Domains (488 LOC)

This single API file handles: config CRUD, insight/MOTD endpoints, model management,
health checks, window control, key capture, file import/export, and intent dispatch.
The model download endpoint (70+ lines) violates the H-Pattern by running threading
and progress callbacks inline instead of dispatching an intent.

**Recommendation:** Split into domain-specific API modules (`config.py`, `models.py`,
`window.py`, `insight.py`).

---

## 4. Frontend-Backend Duplication

### 🟡 Text Analysis — Intentional Mirror (~150 LOC duplicated)

`frontend/src/lib/textAnalysis.ts` mirrors `src/core/text_analysis.py` for:
- `estimateSyllables()` / `estimate_syllables()`
- `splitSentences()` / `split_sentences()`
- `fleschKincaidGrade()` / `flesch_kincaid_grade()`
- `countFillers()` / `_count_fillers()` (in `usage_stats.py`)

This duplication is **intentional and justified** — the frontend needs instant
client-side metrics without server round-trips. However, there is **zero
documentation** linking the implementations as synchronization points.

**Risk:** If the filler word list (`FILLER_SINGLE`, `FILLER_MULTI`) is updated on one
side but not the other, metrics silently diverge between the UserView dashboard
(frontend-computed) and the insight/MOTD system (backend-computed).

**Recommendation:** Add header comments in both files documenting the mirror
relationship and listing which constants must stay synchronized.

---

## 5. Pattern Over-Application

### 🟡 Intent Indirection for Stateless CRUD

The H-Pattern (UI → Intent → CommandBus → Handler → EventBus → WebSocket) is the
correct abstraction for stateful operations (recording, refinement, engine restart).
But it's also applied to trivial CRUD operations where the handler is a 3-line
pass-through:

```python
# tag_handlers.py — entire handle_create method
def handle_create(self, intent):
    db = self._db_provider()
    tag = db.add_tag(name=intent.name, color=intent.color)
    self._emit("tag_created", {...})
```

For tag CRUD, transcript deletion, and transcript renaming, the intent system adds
~6 lines of boilerplate per operation (intent definition + handler method +
registration) with no decoupling benefit — these operations are synchronous, stateless,
and have no side effects beyond DB + event emit.

**24 intents** exist for ~40 API endpoints. At least 8-10 of these are trivial
pass-throughs that could be inline in the API handler without losing testability
(the CommandBus and EventBus are already independently tested).

**Impact:** Adding any new simple mutation requires touching 4 files instead of 1.
This is manageable for a solo maintainer who knows the pattern, but raises the
contribution barrier for others.

---

## 6. Scaling Projections

### What Will Break First as the Project Grows

1. **TranscriptsView.svelte** — Every new transcript feature (export formats, batch
   operations, column customization) adds to an already-overloaded 1,126-line file.
   This is the #1 file that needs decomposition before adding more features.

2. **`usage_stats.py` full-scan computation** — Currently loops through all
   transcripts on every insight refresh. With 10,000+ transcripts, this becomes a
   multi-second blocking operation. Needs incremental/cached computation.

3. **Handler registration ceremony** — 25+ manual `bus.register()` calls. Adding a
   new feature domain (e.g., collaboration, export pipelines) means more imports, more
   registrations, more files to touch. A registry pattern would scale better.

4. **`system.py` endpoint sprawl** — Already at 488 lines mixing 9 concerns. Any new
   system-level feature (updates, diagnostics, backup/restore) will push this past
   maintainability unless split into domain modules first.

5. **Single-threaded SQLite** — The `_write_lock` serializes all DB writes. Currently
   fine for single-user desktop, but becomes a bottleneck if the architecture ever
   moves to multi-user or concurrent recording sessions.

---

## 7. What's Actually Good

Areas that should be left alone — they're well-designed and appropriately scoped:

- **`command_bus.py` + `event_bus.py`** (134 LOC combined) — Minimal, clean, correct.
  Simple registry pattern without over-abstraction.
- **`audio_pipeline.py`** — Well-documented 5-stage pipeline with clear comments
  explaining every design decision (why noise gate was removed, why digital zero is
  bad for Whisper, why hysteresis prevents mid-word cutoffs).
- **`migrations.py`** — Clean append-only migration framework. Idempotent, version-
  tracked, transactional. The right amount of abstraction for SQLite schema evolution.
- **`title_generator.py`** — 169 LOC, single responsibility, thread-safe, graceful
  degradation. Nothing to complain about.
- **`audio_spool.py`** — 94 LOC append-only crash-safe spool writer. Minimal, correct.
- **`audio_cache.py`** — Simple LRU pruning with clean API. Not overengineered.
- **Test coverage** — 27 test files with 466+ tests. Good mixture of unit, integration,
  contract, and code quality tests.
- **Zero TODO/FIXME/HACK comments** — The codebase is unusually clean of deferred work
  markers.

---

## 8. Resolved in This Assessment

| Item | Files Changed | LOC Impact |
|------|--------------|------------|
| Remove dead `std_dev()` + tests | `text_analysis.py`, `test_text_analysis.py` | -36 |
| Remove dead `DistributionChart.svelte` | `DistributionChart.svelte` | -183 |
| Remove dead `stdDev()`/`buildDistributionCurve()` | `textAnalysis.ts` | -39 |
| Clean up dead PyInstaller block | `resource_manager.py` | -9 |
| Extract `_enrich_transcripts_with_tags()` | `db.py` | net -6 |
| Extract `_get_system_tag_id()` | `db.py` | net -4 |
| Eliminate duplicate RMS computation | `audio_pipeline.py` | +5 |
| Improve highpass filter documentation | `audio_pipeline.py` | +6 |
| **Total** | **7 files** | **-255 net lines** |

---

## 9. Recommended Priority for Future Work

### Tier 1 — High Impact, Low Risk
1. Split `TranscriptsView.svelte` into sub-components (~4 hours)
2. Split `system.py` into domain-specific API modules (~2 hours)
3. Add sync-point documentation to mirrored text analysis code (~30 min)

### Tier 2 — Medium Impact, Medium Risk
4. Slim down `usage_stats.py` to core-only computation (~3 hours)
5. Refactor `recent()` in `db.py` to DRY query construction (~2 hours)
6. Extract state machine in `TranscribeView.svelte` (~4 hours)

### Tier 3 — Strategic, Higher Risk
7. Implement decorator/metadata-driven handler registration (~4 hours)
8. Decide plugin system fate: kill it or invest properly (~2 hours)
9. Extract `UserView.svelte` metric computation to utility module (~3 hours)
