# Vociferous Changelog

**Vociferous** is a Linux-native speech-to-text application that lets you transcribe audio using Whisper and refine results with an AI language model. Version 3.0 focuses on stability, data integrity, and architectural clarity.

**Note on version tags:** Priority numbers (P0-P3) indicate severity/scope. Same-day releases are ordered by version number (higher = later).

---

## v3.0.18 - Feature: Database Backup Export
**Date:** 2026-02-06
**Status:** Feature

### Context
**VACUUM INTO** = SQLite operation that creates a consistent backup of the database file, ensuring no data is lost if the app crashes.

### Added
- **Database backup:** New "Backup Database…" button in Settings → History Management exports a consistent copy of the SQLite database via `VACUUM INTO`, with a WAL-checkpoint file-copy fallback.
- `HistoryManager.backup_database(dest)` encapsulates the logic; `MainWindow` wires a standard save-file dialog.

---

## v3.0.17 - Feature: Frameless Window Edge Resize
**Date:** 2026-02-06
**Status:** Bugfix / UX

### Fixed
- **Edge resize:** `MainWindow` now supports resizing from all four edges and corners using `startSystemResize()` with an 8 px grip zone, matching the behavior users expect from a frameless window.
- Mouse cursor updates to the correct resize arrow on hover and resets on leave.

---

## v3.0.16 - Bugfix: Project Color Refresh on Data Change
**Date:** 2026-02-06
**Status:** Bugfix

### Fixed
- **History view project colors:** `HistoryView._handle_data_changed` now handles `entity_type == "project"` events by calling `TranscriptionModel.refresh_project_colors()`, so color-identifier badges update without a manual refresh.

---

## v3.0.15 - Bugfix: Export Dialog Browse Button Height
**Date:** 2026-02-06
**Status:** Bugfix / UI

### Fixed
- **Browse button sizing:** Removed `setFixedHeight(42)` on the Browse button in `ExportDialog`, which conflicted with the stylesheet's `min-height: 44px`, causing a 2 px visual glitch. Vertical alignment centred via layout flag instead.

---

## v3.0.14 - Improvement: Versioned Database Migrations
**Date:** 2026-02-06
**Status:** Improvement / Safety

### Changed
- **Migration framework:** Replaced ad-hoc `ALTER TABLE` try/except migrations with a `schema_version` table and a numbered migration registry. Each migration runs inside an explicit transaction (`engine.begin()`), and the version counter advances atomically.
- Existing databases auto-bootstrap to the correct version on first run.

---

## v3.0.13 - Improvement: Engine Subprocess Logging
**Date:** 2026-02-06
**Status:** Improvement

### Changed
- **Engine log file:** The `core_runtime` subprocess now writes to `vociferous_engine.log` via a `RotatingFileHandler` (5 MB, 2 backups) in the same log directory as the main application, in addition to its existing stderr handler.
- Falls back to stderr-only if file handler setup fails.

---

## v3.0.12 - Bugfix: Refinement Acceptance Stores Variant
**Date:** 2026-02-06
**Status:** Bugfix

### Context
**Refinement** = AI-powered text enhancement using a Small Language Model (SLM).  
**Variant** = An immutable copy of a transcript at a point in time (original, refined, edited, etc.).

### Fixed
- **Variant persistence:** Accepting a refined transcription now stores an immutable variant (`kind="refined"`) via `HistoryManager.add_variant_atomic` before updating the normalised text, preserving the full refinement history per the data model's design intent.

---

## v3.0.11 - Refactor: Replace `SLMService` with `SLMRuntime` (P1)
**Date:** 2026-01-29
**Status:** Refactor / P1

### Changed
- **Runtime consolidation:** Replaced the legacy monolithic `SLMService` with a focused `SLMRuntime` (`src/services/slm_runtime.py`) that is responsible solely for loading provisioned models, running inference, and managing enable/disable lifecycle. The `ApplicationCoordinator` now wires and interacts with `SLMRuntime` directly.
- **UI model registry:** UI surfaces that previously used `SLMService.get_supported_models()` now read models from the canonical registry `src/core/model_registry.MODELS`.
- **MOTD compatibility:** Added a small `motd_ready` signal and `generate_motd()` shim in `SLMRuntime` to preserve existing MOTD plumbing during migration.
- **Tests & docs:** Updated and removed tests that depended on legacy behaviors; refreshed architecture docs (`docs/wiki/Architecture.md`, `docs/wiki/Refinement-System.md`) to reflect the change.

### Removed
- **Legacy service:** Deleted `src/services/slm_service.py` and removed in-band provisioning/GPU-confirmation and request-queueing responsibilities from the runtime. Provisioning should be performed by provisioning tooling (`scripts/provision_models.py`) or separate services.

### Impact & Rationale
- **Why:** Converging on a single, focused runtime reduces maintenance burden, eliminates duplicated behavior, and makes lifecycle semantics easier to reason about.
- **Effort:** Medium (refactor + tests + docs). All tests pass locally after the migration.

---

## v3.0.10 - Safety: SLM request queue dedupe & max size (P2)
**Date:** 2026-01-29
**Status:** Improvement / Safety

### Context
**Deduplication** = prevent duplicate refinement requests from flooding the queue if user clicks multiple times.

### Changed
- **SLM queue safety:** Added deduplication of queued refinement requests by `transcript_id` and a configurable queue size `refinement.max_queue_size` (default: `5`). Duplicate requests now replace pending entries (emits "Request updated in queue.") and requests that exceed the queue limit are rejected with a user-facing status message and `refinementError`.

---

## v3.0.9 - Improvement: Atomic model installs & manifest-based validation (P1)
**Date:** 2026-01-29
**Status:** Bugfix / P1

### Context
**Atomic** = all-or-nothing operation: model installation either completes fully or fails completely, preventing partial/broken installs.

### Fixed
- **Atomic provisioning:** `provision_model()` now converts artifacts into a temporary install directory and atomically moves the directory into place on success to prevent partial installs from being treated as valid.
- **Artifact manifest & checksums:** A `manifest.json` is written for each installed model containing SHA256 checksums for key artifacts; `validate_model_artifacts()` uses the manifest to verify file integrity and detect corruption or mismatches.
- **Cleanup on failure:** Partial conversion directories and temp downloads are cleaned up on failure (no half-installed models remain in the cache).
- **Tests:** Added unit tests that assert manifest creation, checksum verification, and proper cleanup when conversion fails.

---

## v3.0.8 - Bugfix: Atomic config saves (P1)
**Date:** 2026-01-29
**Status:** Bugfix / P1

### Context
**Atomic write** = use a temporary file + `os.replace()` to guarantee config is either fully saved or unchanged. Prevents corruption if the app crashes mid-save.

### Fixed
- **Crash-safe config persistence:** `ConfigManager.save_config` now performs atomic writes using a temporary file, fsync, and `os.replace()` to avoid partial/corrupt `config.yaml` files on crashes or power loss. The method also writes an optional `.bak` backup of the previous config when present.
- **Robustness:** The implementation cleans up temporary files on failure and raises on unrecoverable write errors so callers can react appropriately.
- **Tests:** Added tests to assert temp-file cleanup on failure and `.bak` creation on success.

---

## v3.0.7 - Bugfix: SLM GPU confirmation non-blocking fix
**Date:** 2026-01-29
**Status:** Bugfix / P0

### Context
**SLM** (Small Language Model) provisioning required GPU confirmation from users. Previous implementation used blocking waits that froze the UI.

### Fixed
- **SLM GPU confirmation deadlock:** Removed legacy blocking primitives (`QWaitCondition`/`QMutex`) from `SLMService` and replaced the blocking wait flow with an asynchronous signal/queued-invoke pattern. The service now emits `askGPUConfirmation` and returns immediately; the UI confirmation handler invokes `submit_gpu_choice` using a queued call so the choice is processed on the service thread.
- **Timeout fallback:** Added/ensured a 30s GPU confirmation timeout that defaults to CPU when no response is received.
- **Thread-safety & test-hardened coordinator:** The `ApplicationCoordinator` now safely invokes `initialize_service`, `generate_motd`, and `submit_gpu_choice` using a queued invocation when possible and falls back to direct calls when the service is mocked in tests.
- **Tests:** Added unit tests verifying that initialization runs on the SLM service thread and that the GPU confirmation flow resumes initialization via queued invocation.

---

## v3.0.6 - Maintenance: Test Suite Recovery and Venv Integrity
**Date:** 2026-01-30
**Status:** Maintenance / Bugfix

### Context
Tests were failing due to broken import paths in the virtual environment. This fix ensures the test suite runs correctly using `scripts/run_tests.sh`.

### Added
- **Test Runner**: Added `scripts/run_tests.sh` to provide an authoritative way to execute the test suite within the project's virtual environment.
- **Environment Discovery**: Added `pythonpath = ["src"]` to `pyproject.toml` to ensure consistent module discovery across all platforms.

### Fixed
- **Test Collection**: Resolved 14+ `ModuleNotFoundError` errors caused by legacy imports of the defunct `src.provisioning.core` module.
- **Path Resolution**: Fixed pathing errors in test utilities that prevented script detection when run from the repository root.
- **Legacy Tests**: Purged or updated tests targeting removed private methods (`_validate_artifacts`, `_run_conversion`) in `SLMService`.

### Changed
- **Testing Philosophy**: Updated `docs/wiki/Testing-Philosophy.md` to document the new `scripts/run_tests.sh` workflow.

---

## v3.0.5 - Refactor: SLM Service Decomposition
**Date:** 2026-01-29
**Status:** Refactor

### Context
**SLM** = Small Language Model service for text refinement. This refactor broke a large service into focused modules.

### Changed
- **SLM Service Refactor**: Decomposed `src/services/slm_service.py` into focused modules:
  - `src/services/slm_types.py`: Centralized `SLMState` and shared signals.
  - `src/services/slm_background_workers.py`: Isolated `ProvisioningWorker` and `MOTDWorker`.
  - `src/services/slm_utils.py`: Extracted GPU discovery and artifact validation.
- **Deduplication**: Unified `SLMState` and `SupportedModel` definitions between `SLMService` and `SLMRuntime`.

---

## v3.0.4 - Feature: Provisioning Isolation
**Date:** 2026-01-29
**Status:** Feature / Refactor

### Context
**Provisioning** = downloading and setting up speech-to-text models (Whisper and SLM). This separates provisioning into a standalone library for easier maintenance.

### Added
- **Provisioning Library**: New `src.provisioning` package for centralized model management.
- **CLI Tool**: `vociferous-provision` (via `scripts/provision_models.py`) now wraps the new library with improved diagnostics.
- **Dependency Lock**: Added `requirements.lock` for deterministic environments.
- **Startup Integrity**: Strict environment check in `src/main.py` prevents startup if critical dependencies are missing.

### Changed
- **Runtime Isolation**: Removed inline `pip install` suggestions and subprocess conversion logic from `ProvisioningWorker`. It now delegates to the robust provisioning library.
- **Fail Fast**: The application now hard-fails with a clear error message at startup if the environment is incomplete, rather than crashing during operation.

---

## v3.0.3 - Bugfix: Remove legacy DB detection
**Date:** 2026-01-28
**Status:** Bugfix

### Changed
- **Removed** legacy schema detection and automatic reset:
  - Removed `DatabaseCore._check_legacy_schema` and `DatabaseCore._create_backup` (no automatic backup/migration on legacy `schema_version` DBs). Users with existing legacy DBs must manually backup/migrate before upgrading. See `docs/wiki/History-Storage.md` for guidance.

---

## v3.0.2 - Documentation Styling and Accessibility
**Date:** 2026-01-19
**Status:** Documentation Release

### Changed
- **Wiki content reformatting** — Eliminated all emojis and purely decorative symbols from the entire GitHub Wiki documentation suite (14 pages).
- **GitHub Wiki best practices** — Standardized formatting across all wiki pages, replaced manual warning icons with GitHub-native alert blocks (`[!TIP]`, `[!WARNING]`, etc.), and converted status symbols (`✓`, `❌`) to text-based equivalents (`Yes`, `No`) for improved accessibility and professional presentation.

---

## v3.0.1 - Desktop Entry Launcher Fixes
**Date:** 2026-01-19
**Status:** Major Release — Production Ready

### Added
- **Complete GitHub Wiki:** 14 pages covering installation, architecture, UI views, refinement system, and testing strategy
- **Architecture documentation:** Mermaid diagrams, component responsibilities, threading model, and design patterns
- **Design system:** Color scales, typography, spacing tokens, and unified stylesheet patterns

### Changed
- **Documentation standards:** Repository-first authority with all diagrams traceable to source code
- **Accessibility:** Converted emoji and symbols to text for inclusive design

---

## v3.0.0 - Beta Release: Production-Ready with Complete Documentation
**Date:** 2026-01-19
**Status:** Major Release — Beta

### Summary

Vociferous v3.0.0 marks the transition to a production-ready, fully documented release. This version includes a comprehensive GitHub Wiki (14 pages), complete Mermaid diagram audit with repository-backed architecture visualizations, and validated architecture documentation. All architectural invariants are documented, all views are explained with capabilities matrices and state machines, and the entire system is now suitable for professional deployment and contribution.

### Added

**Complete GitHub Wiki (14 Pages):**
```
docs/wiki/
├── Home.md                               # Landing page with technology stack
├── Getting-Started.md                    # Installation and first-run guide
├── Architecture.md                       # System design (Mermaid flowchart)
├── Design-System.md                      # Design tokens and styles
├── Data-and-Persistence.md               # Database layer (Mermaid ER)
├── UI-Views-Overview.md                  # View architecture (Mermaid)
├── Refinement-System.md                  # AI refinement (Mermaid)
├── View-Transcribe.md                    # Transcription view (Mermaid)
├── View-History.md                       # History browser (Mermaid)
├── View-Search.md                        # Search interface (Mermaid)
├── View-Refine.md                        # AI refinement UI (Mermaid)
├── View-Settings.md                      # Configuration view
├── View-User.md                          # User metrics view
├── Testing-Philosophy.md                 # Test strategy (2-tier)
├── DIAGRAM_AUDIT_REPORT.md               # Complete diagram audit (planning, execution, validation)
├── MERMAID_VALIDATION_REPORT.md          # Post-conversion validation (22 blocks verified)
├── WIKI_PLAN.md                          # Planning document
└── phase2/                               # 14 trace reports (per-page)
    ├── TRACE_*.md
    └── ...
```

**Architecture Documentation:**
- **Architecture.md** — Layered architecture diagram (Mermaid flowchart), component responsibilities, threading model, ApplicationCoordinator design pattern
- **Design-System.md** — Color scales (Gray/Blue/Green/Red/Purple), typography, spacing (S0-S7), unified stylesheet patterns
- **Data-and-Persistence.md** — Entity-relationship diagram, ORM models (Transcript, Project, TranscriptVariant), dual-text invariant, HistoryManager facade
- **UI-Views-Overview.md** — View architecture, BaseView protocol, Capabilities system, ActionDock, navigation flow
- **View-Transcribe.md** — Live recording view, WorkspaceState machine, capabilities matrix, MOTD integration
- **View-History.md** — Master-detail browser, TranscriptionModel, database reactivity via SignalBridge
- **View-Search.md** — Tabular search interface, SearchProxyModel, preview overlay, multi-select handling
- **View-Refine.md** — AI-powered text refinement, side-by-side comparison, strength selector, custom instructions
- **View-Settings.md** — Configuration mutations, custom widgets (ToggleSwitch, HotkeyWidget, StrengthSelector), validation
- **View-User.md** — Usage metrics, personalization, application info, credits, insights generation
- **Refinement-System.md** — SLM lifecycle, provisioning flow, state machine, model registry, GPU memory management
- **Getting-Started.md** — Installation, first run, Wayland setup, troubleshooting, default configuration
- **Testing-Philosophy.md** — Two-tier test strategy, fixtures, lock prevention, architecture guardrails
- **Home.md** — Landing page with technology stack, navigation, screenshots, links

Every page includes:
- Trace points to repository source files (class names, line numbers)
- State diagrams and sequence flows (Mermaid)
- Capabilities matrices for views
- Examples and configuration details
- Internal wiki cross-links

**Mermaid Diagram Suite:**
Full audit of wiki diagrams with 4 conversions applied:
- **Architecture.md** — ASCII layered architecture → Mermaid `flowchart TB` with 4 subgraphs (UI, Core, Runtime, Database layers)
- **Refinement-System.md** — ASCII component stack → Mermaid `flowchart TB` with proper hierarchy
- **Refinement-System.md** — Enhanced SLMState machine with `WAITING_FOR_USER` transition and error recovery paths
- **View-Transcribe.md** — Aligned WorkspaceState diagram with enum; added `VIEWING` state and `RECORDING → IDLE` cancel transition

All conversions verified with 7 trace points per diagram and validated against GitHub's Mermaid renderer.

**Audit & Validation Reports:**
- **DIAGRAM_AUDIT_REPORT.md** — Complete audit of all 14 wiki pages, classifying 100+ diagrams by type, conversion feasibility, and evidence traces
- **MERMAID_VALIDATION_REPORT.md** — Post-conversion validation confirming syntax validity, semantic accuracy, and repository-backed nodes/edges

### Changed

- **CHANGELOG.md** — Added comprehensive v3.0.0 entry with full documentation of wiki pages, diagram conversions, and validation results
- **docs/wiki/** — 14 production-ready wiki pages with Mermaid diagrams and trace points
- **docs/wiki/DIAGRAM_AUDIT_REPORT.md** — 3-part audit report (planning, execution, validation)
- **docs/wiki/MERMAID_VALIDATION_REPORT.md** — Post-conversion validation with 22 Mermaid blocks verified

### Not Changed (Intentional)

The following were intentionally NOT converted to Mermaid as they represent pixel-geometry UI layouts rather than architectural structures:
- MainWindow layout diagrams (spatial arrangement, not hierarchy)
- All view layout diagrams (Form, master-detail, table, cards layouts)
- These remain as ASCII for clarity of visual intent

### Documentation Architecture

All documentation follows strict repository authority with:
- Zero invented components or behaviors
- All diagrams traceable to source files (file path + class/function name)
- Prose flows explained with "Derived from implementation" citations
- Internal links validated
- ASCII layouts preserved where appropriate (UI mockups, pixel-geometry representations)
- Mermaid conversions used only for structural/behavioral diagrams

### Documentation Standards Established

This release establishes documentation standards for future development:
1. **Repository-First Authority** — Documentation never invents; it traces to code
2. **Trace Points Required** — Every diagram includes source file references
3. **Mermaid for Architecture** — Structural/behavioral flows use Mermaid; pixel layouts remain ASCII
4. **Dual Reports** — Complex documentation includes audit + validation reports
5. **Cross-Link Integrity** — All internal links maintained through automated validation

### Validation & Quality Assurance

- All 22 Mermaid blocks syntactically valid (GitHub-compatible)
- 14 wiki pages internally linked and cross-referenced
- 6 image paths verified (docs/images/)
- Zero unevidenced nodes or edges in any diagram
- README.pdf successfully generated and tested
- All tests pass: `ruff check`, `mypy`, `pytest`

### Commits & Reproducibility

This release is fully reproducible. All wiki content is:
- Derived from repository code via trace points
- Validated against Mermaid rendering rules
- Cross-linked and consistent
- Suitable for git history and attribution

---
