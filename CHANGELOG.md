# Vociferous Changelog

---

# v2.4.0 - Advanced Refinement & Resource Intelligence

**Date:** January 2026
**Status:** Feature Release

---

## Summary

This release brings significant maturity to the AI Refinement engine, replacing the legacy experimental backend with a robust **Qwen3-4B-Instruct** foundation. We introduce **Refinement Profiles** (Minimal, Balanced, Strong) to give users granular control over editing intensity, and a **Dynamic Resource Manager** that intelligently loads models into GPU memory based on available headroom.

The input system has been hardened against prompt injection using a "Swiss-Army-Knife" system prompt strategy, treating transcripts strictly as data rather than instructions.

## Added

### AI Refinement
- **Directive-Based Prompting**: New "Refinement Profiles" allow selecting between `MINIMAL` (grammar only), `BALANCED` (light cleanup), and `STRONG` (flow/structure) editing modes.
- **Dynamic VRAM Management**: The engine now queries `nvidia-smi` to calculate available GPU headroom:
  - **>40% Free**: Auto-loads to GPU (CUDA) for maximum speed.
  - **20-40% Free**: Defaults to GPU but logs warnings.
  - **<20% Free**: Pauses initialization and asks the user for explicit confirmation to avoid system instability.
- **32k Context Window**: Increased context limit from 4k to 32k tokens to support long-form dictation refinement.

### UI / UX
- **Profile Controls**: Integrated radio control group (Min/Bal/Str) directly into the workspace toolbar.
- **Sidebar Polish**: Aligned sidebar collapse button with search controls and improved styling consistency.

## Changed

### Core Infrastructure
- **Model Upgrade**: Replaced `vennify/t5-base` (Encoder-Decoder) with `Qwen/Qwen3-4B-Instruct` (Decoder-Only) for superior semantic reasoning.
- **Inference Optimization**: Switched CUDA compute type to `int8_float16` for optimal Tensor Core utilization on NVIDIA GPUs.

---

# v2.3.0 - AI Grammar Refinement (MVP)

**Date:** January 2026
**Status:** Feature Release

---

## Summary

Introduces **Single-Click AI Refinement**, a powerful new capability to instantly correct grammar, tense, and phrasing in your transcripts. Powered by a local, purpose-built GEC (Grammatical Error Correction) model, this feature transforms raw dictation, such as "him going to the store", into polished prose ("He was going to the store") without any valid text losing its meaning.

This release integrates a production-grade CTranslate2 inference engine directly into Vociferous, ensuring zero external dependencies at runtime and complete privacy.

## Added

### Core Features
- **Grammar Refinement (GEC)**: New backend engine using the `vennify/t5-base-grammar-correction` model (converted to quantized CTranslate2 format).
- **Non-Destructive Editing**: Refinements are saved as "variants" of the original transcript. The original raw text is never lost.
- **Local Inference**: All processing happens on-device using optimized CPU inference (Int8 quantization). No GPU required.

### UI / UX
- **Refinement Toggle**: New "Refine" button added to the Workspace (visible when enabled in settings).
- **Settings**: Added "Grammar Refinement" section to the Settings dialog to toggle the feature.
- **Status Feedback**: Real-time status messages during model loading and inference.

### Infrastructure
- **Model Management**: Automatic schema migration for variant support (`current_variant_id` column).
- **Artifact Caching**: Secure caching of model artifacts in standard system locations (`~/.cache/Vociferous/models`).
- **Dependencies**: Removed runtime dependence on heavy ML libraries (`torch`, `transformers`) in favor of lightweight inference runtimes.

---

# v2.2.1 - Group Hierarchy & UI Polish

**Date:** January 2026
**Status:** Minor Release

---

## Summary

Introduces hierarchical organization for Focus Groups (subgroups), enabling deeper content structuring. Enhances the sidebar with drag-and-drop management, bulk operations for transcripts, and improved visual controls.

## Added

### Organization
- **Nested Focus Groups**: Added ability to create subgroups up to one level deep.
- **Drag & Drop**: Transcripts can now be moved between groups via drag-and-drop.
- **Bulk Actions**: Support for multi-selecting transcripts in the sidebar to move or delete them in batches.

### UI / UX
- **Sidebar Toggle**: Added a dedicated button to collapse/expand the sidebar panel.
- **Dialog Usability**: Primary actions in dialogs now trigger on the "Enter" key.
- **Error Dialogs**: Improved layout and text visibility for error reporting.

## Changed

### Core Infrastructure
- **Database Schema**: Added `parent_id` column to `focus_groups` table with automatic micro-migration on startup.

### Styling
- **Visual Refinements**: Updated context menu selection styles and standardized radio button appearance.

---

# v2.2.0 - Architecture Overhaul (SQLAlchemy Migration)

**Date:** January 2026
**Status:** Major Release

---

## Summary

Complete persistence layer rewrite migrating from raw SQLite cursors to **SQLAlchemy 2.0 ORM**. This architectural shift lays the foundation for complex hierarchical data relationships (subgroups), external integrations, and robust schema management.

**⚠️ BREAKING CHANGE**: This release resets the local database structure. Legacy history files will be recreated (nuked) upon first launch to ensure schema consistency.

## Changed

### Core Infrastructure
- **Database Engine**: Replaced hand-rolled `sqlite3` queries with **SQLAlchemy** ORM sessions.
- **Schema Management**: Introduced declarative models (`src/models.py`) for `Transcript` and `FocusGroup` entities.
- **Migration Strategy**: Implemented "fresh start" policy—legacy databases are detected and reset to pristine state to guarantee stability.

### Internal API
- **Refactoring**: Rewrote `HistoryManager` to utilize SQLAlchemy `Session` for all CRUD operations, improving safety and maintainability.
- **Type Safety**: Enhanced type constraints on database models ensuring integrity at the application level before persistence.

---

# v2.1.6 - UI Polish (Focus Group Indicators)

**Date:** January 2026
**Status:** Enhancement

---

## Changed

### UX / Styling
- **Cleaned Up Tooltips**: Removed the full-text tooltip from sidebar items (transcripts and focus groups) to reduce UI clutter as requested.
- **Improved Selection Indicator**: Changed the Focus Group item selection style from a solid block to a cohesive background with a circular dot indicator on the left. The dot inherits the group's color (or defaults to blue), providing a cleaner and more distinct visual cue.

---

# v2.1.5 - Critical Hotfix (Dialog Crash & Safety)

**Date:** January 2026
**Status:** Hotfix

---

## Fixed

### Stability
- **Dialog Crash**: Fixed `NameError: name 'QFrame' is not defined` in `custom_dialog.py` caused by missing import in the v2.1.3 refactor. This prevented all custom dialogs (Confirmation, Input, Error) from opening.

### UX / Safety
- **Delete Confirmation**: Enforced confirmation dialog for ALL transcript deletion events, including those triggered by the "Delete" key in the sidebar history list (previously bypassed confirmation).

---

# v2.1.4 - Dialog Visual Polish

**Date:** January 2026
**Status:** Hotfix

---

## Changed

### UI / Styling
- **Dialog Frames**: Thickened the dialog blue border to 3px (was 1px) and removed border radius to match the rectangular window shape, ensuring a clean and consistent visual style for frameless dialogs.

---

# v2.1.3 - UI Refinements (Dialog Borders)

**Date:** January 2026
**Status:** Hotfix

---

## Fixed

### UI / Rendering
- **Dialog Borders**: Refactored all custom dialogs (`StyledDialog`, `SettingsDialog`, `ExportDialog`, `CreateGroupDialog`, `MetricsExplanationDialog`) to use a structural `QFrame` wrapper (`dialogFrame`) for proper border rendering. Moved border styling from `QDialog` to `QFrame` to prevent content-level border artifacts and ensure a consistent frameless window outline.

---

# v2.1.2 - UI Refinements & Binding Fixes

**Date:** January 2026
**Status:** Hotfix

---

## Fixed

### UI / Rendering
- **Sidebar Padding**: Increased timestamp column width in sidebar delegate (70px → 90px) to prevent time cutout on systems with wider fonts or varying DPI.

### Data Binding
- **Recent Transcripts**: Fixed regression where moving a transcript out of a Focus Group would not immediately make it reappear in the Recent list. Enabled `dynamicSortFilter` on `FocusGroupProxyModel` to react instantly to `GroupIDRole` changes.

---

# v2.1.1 - Critical Crash Fix

**Date:** January 2026
**Status:** Hotfix

---

## Summary

Emergency hotfix addressing a critical segmentation fault on application startup caused by infinite recursion in the transcription data model.

## Fixed

### Critical Stability
- **TranscriptionModel**: Fixed segmentation fault where leaf nodes (entries) were incorrectly processed as branch nodes in `rowCount()`. Implemented invalidation check using `internalId` to prevent proxy models from triggering infinite recursion stack overflows.

---

# v2.1.0 - Code Health & Type Safety

**Date:** January 2026
**Status:** Maintenance Release

---

## Summary

Comprehensive codebase cleanliness and type safety overhaul. Achieved zero metadata and type errors across the entire project by enforcing strict MyPy and Ruff compliance. Fixed latent logic bugs in proxy models and intent feedback handlers identified during static analysis.

## Fixed

### Critical Logic
- **Focus Group Proxy**: Removed unreachable dead code referencing undefined `source_model` variable in `focus_group_proxy.py`
- **Intent Feedback**: Fixed valid return type violation in status message timer callback (lambda returned tuple instead of `None`)
- **System Safety**: Replaced unsafe bare `except:` blocks with `except Exception:` in `transcription_model.py` to prevent masking system signals like `KeyboardInterrupt`

### Type Safety
- **Workspace**: Resolved variable type reuse ambiguity in `_on_primary_click` and related handlers in `workspace.py`
- **Architecture Tests**: Fixed type checking logic in `test_architecture_guardrails.py` for ensuring export string verification

## Changed

### Repository Hygiene
- **Linter Compliance**: Resolved ~54 Ruff issues covering unused imports, dead variables, and redundant logic
- **Type Compliance**: Achieved clean MyPy run across 108 source files
- **Code Cleanup**: Removed multiple instances of unused error logger assignments and redundant imports

---

# v2.0.1 - Repository Hygiene & Debt Assessment

**Date:** January 2026  
**Status:** Maintenance Release

---

## Summary

Post-stabilization maintenance release focused on repository hygiene and technical debt assessment. Removed transient planning artifacts, updated documentation structure, and conducted comprehensive code health audit. No functional changes—this is a pure documentation and repository organization release.

## Changed

### Repository Cleanup
- **Removed**: 7 transient planning artifacts from `docs/dev/planning/`:
  - `documentation-alignment-plan.md` — Superseded planning proposal
  - `file-relevance-audit-batch-01.md` — Exhausted audit log (scripts)
  - `file-relevance-audit-batch-02.md` — Exhausted audit log (README/wiki)
  - `file-relevance-audit-batch-03.md` — Exhausted audit log (launchers)
  - `tech-debt-assessment-batch-01.md` — Exhausted assessment (Type C findings)
  - `tech-debt-assessment-batch-02.md` — Exhausted assessment (complexity justified)
  - `tech-debt-assessment-batch-03.md` — Exhausted assessment (Type B declined)
- **Removed**: Empty `docs/dev/planning/` directory

### Documentation
- **Updated**: `docs/wiki/Home.md` Project Structure to include frozen architecture documentation in `docs/dev/`
- **Preserved**: All binding architecture documents (interaction-core-frozen.md, authority-invariants.md, intent-catalog.md, edit-invariants.md)

## Technical Debt Assessment

Conducted systematic code health audit across three batches covering non-UI infrastructure:

### Batch 01: Configuration & Utilities
- **Files Reviewed**: `src/utils.py`, `src/config_schema.yaml`
- **Findings**: One minor Type C finding (repeated guard pattern in ConfigManager)
- **Outcome**: Complexity justified; no action taken

### Batch 02: Core Infrastructure
- **Files Reviewed**: `src/key_listener.py`, `src/result_thread.py`, `src/transcription.py`
- **Findings**: One Type C finding (duplicate media key mappings in EvdevBackend)
- **Outcome**: All complexity proportionate to platform requirements; no action taken

### Batch 03: Utility Infrastructure
- **Files Reviewed**: `src/history_manager.py`, `src/ui/utils/clipboard_utils.py`, `src/ui/utils/error_handler.py`
- **Findings**: One Type B finding (repetitive try/except in HistoryManager), one Type C finding
- **Outcome**: Type B refactor declined due to heterogeneous method semantics; error_handler.py identified as exemplary implementation

### Assessment Conclusions
- **No code modifications**: All identified complexity was either justified defensive programming or cosmetic
- **Architecture validated**: Thread safety, error handling, and platform abstraction all proportionate to domain requirements
- **Remediation declined**: Proposed HistoryManager refactor determined unsafe without behavioral changes

## Notes

This release represents a **conservative post-stabilization posture**. The technical debt assessment confirmed that the non-UI codebase is architecturally healthy, with complexity patterns reflecting genuine platform requirements rather than entropy.

Repository surface area reduced by removing agent-specific planning logs that served their purpose during Phases 1-7 but are no longer needed for contribution or evolution.

---

# v2.0.0 - Architecture Stabilization

**Date:** January 2026
**Status:** Release

---

## Summary

Architecture stabilization release. Beta 2.0 introduces no new user-facing features. Its value lies entirely in correctness, safety, and long-term maintainability. This release establishes a frozen interaction architecture with automated guardrails that prevent regression.

## Added

### Intent-Driven Interaction Architecture
- All user actions are now represented as explicit intent objects (`BeginRecordingIntent`, `StopRecordingIntent`, `ViewTranscriptIntent`, `EditTranscriptIntent`, `CommitEditsIntent`, `DiscardEditsIntent`, `DeleteTranscriptIntent`, `CancelRecordingIntent`)
- Single authoritative `handle_intent()` method validates and processes all user interactions
- `IntentResult` objects capture outcome, reason, and state for every action

### Transactional Editing Model
- Edit sessions are explicitly entered and exited via `EditTranscriptIntent`, `CommitEditsIntent`, and `DiscardEditsIntent`
- Only terminal intents (commit or discard) can exit the editing state
- Unsaved changes are protected—recording, navigation, and deletion are blocked during editing

### Intent Outcome Visibility
- `IntentFeedbackHandler` maps intent results to user-visible status bar messages
- Feedback layer consumes `IntentResult` only—never queries workspace state
- Rejected actions produce informative messages explaining why they failed

### Architectural Guardrail Tests
- 9 static analysis tests in `test_architecture_guardrails.py` enforce frozen architecture
- Tests scan source code directly and fail CI on boundary violations
- Covers: `set_state` usage, feedback layer isolation, intent catalog sync, orchestration privilege

### Documentation
- [Interaction Core Freeze Declaration](docs/dev/interaction-core-frozen.md) — What is frozen and why
- [Intent Catalog](docs/dev/intent-catalog.md) — Complete vocabulary of user intents
- [Authority Invariants](docs/dev/authority-invariants.md) — Who owns state transitions
- [Edit Invariants](docs/dev/edit-invariants.md) — Transactional editing guarantees
- [Intent Outcome Visibility](docs/dev/intent-outcome-visibility.md) — Feedback layer design

## Changed

### Interaction Authority Consolidation
- All user-initiated state changes now flow through `handle_intent()` → `_apply_*()` methods
- UI components no longer call `set_state()` directly for user actions
- Clear separation between user interaction (intents) and engine orchestration

### Orchestration Privilege Formalization
- Renamed `update_transcription_status()` → `sync_recording_status_from_engine()`
- Orchestration method explicitly documented as the only external `set_state()` caller
- Edit-safety guards prevent orchestration from overriding editing state

## Fixed

### Eliminated Implicit State Transitions
- No more silent state changes without validation
- All transitions produce `IntentResult` with success/failure reason

### Editing Safety Violations
- Fixed: Recording could start while editing unsaved changes
- Fixed: Navigation could abandon unsaved edits without warning
- Fixed: Deletion could target content being actively edited

## Deprecated

### Direct State Mutation
- UI components calling `workspace.set_state()` directly is no longer valid
- All user actions must create and dispatch intents

### Ad-Hoc Interaction Handling
- Scattered `if/else` state checks in UI components are deprecated
- Use `handle_intent()` for all user action processing

## Notes

**This release introduces no new user-facing features.** Its purpose is to guarantee correctness, safety, and maintainability for future development.

The interaction architecture is now **frozen**. Changes to the frozen core require explicit design review and documentation updates.

**Versioning Policy:**
- `2.0.x` — Stabilization releases (no new features, bug fixes only)
- `2.1.x` — Feature development resumes (local SLM integration planned)

---

# v1.9.0 - Intent Outcome Visibility

**Date:** January 2026  
**Status:** Release

---

## Summary

User feedback layer for the intent-driven interaction architecture. Introduces `IntentFeedbackHandler` to provide clear, actionable status messages when user actions are rejected, completing the interaction architecture with proper outcome visibility.

## Added

### Intent Feedback System
- **`IntentFeedbackHandler`**: Presentation layer that consumes `IntentResult` and displays user-friendly status messages
- **Outcome Mapping**: Maps intent results to appropriate feedback:
  - `ACCEPTED`/`NO_OP`: Silent (success is expected)
  - `REJECTED` with user-actionable reasons: Display informative status message
  - `REJECTED` when button shouldn't be visible: Silent logging only
- **Status Bar Integration**: 4-second auto-dismiss messages styled consistently with application theme
- **Structured Logging**: Configurable debug verbosity for intent processing outcomes

### Documentation
- [Intent Outcome Visibility](docs/dev/intent-outcome-visibility.md) — Outcome mapping specification and architecture diagram
- Phase 6 exit criteria and constraints documented

### Tests
- **13 new tests** (67 total intent/feedback tests, 165 Tier 1 tests passing)
  - `TestIntentFeedbackMapping` (8 tests): Verify correct status messages for each outcome type
  - `TestIntentFeedbackLogging` (3 tests): Verify logging behavior and verbosity
  - `TestPhase6Constraints` (2 tests): Verify handler never queries workspace state directly

## Changed

### Feedback Layer Design
- Status messages driven entirely by `IntentResult`—no inspection of workspace state
- Clear separation between interaction processing and user feedback

## Technical Notes

**Phase 6 Constraints Maintained:**
- No new state transitions introduced
- No UI branches on workspace state for feedback decisions
- All feedback driven exclusively by `IntentResult` data

**Architecture Completeness:** With this release, the intent-driven interaction architecture is feature-complete with proper outcome visibility.

---

# v1.8.0 - Authority Consolidation

**Date:** January 2026  
**Status:** Release

---

## Summary

Final authority consolidation for user-initiated state changes. All user interactions now flow through the intent layer with authoritative `_apply_*()` methods. Establishes clear separation between user interaction (intents) and orchestration (engine sync).

## Added

### Authority Invariants
- **All Invariants Enforced**: 7-11 in [Authority Invariants](docs/dev/authority-invariants.md) now have `ENFORCED` status
- **Stopping Condition Verified**: No external component directly mutates workspace state for user actions
- **Orchestration Privilege Formalized**: `sync_recording_status_from_engine()` (renamed from `update_transcription_status()`) documented as the only external `set_state()` caller

### Intent Migration Completed
- **`ViewTranscriptIntent`**: Migrated to authoritative `_apply_view_transcript()` method
  - Carries both timestamp and text
  - Validates state (cannot view while recording or with unsaved edits)
  - Transitions to `VIEWING` or `IDLE` based on content
- **`DeleteTranscriptIntent`**: Migrated to authoritative `_apply_delete_transcript()` method  
  - Validates state (can only delete in `VIEWING`)
  - Emits deletion signal after validation
  - State transition deferred until after user confirmation via `clear_transcript()`

### Edit Safety Guards
- **Orchestration Safety**: Engine status sync prevented from overriding `EDITING` or `VIEWING` states
- **Clear History**: Now uses `clear_transcript()` instead of direct `set_state()` calls

### Documentation
- [Authority Invariants](docs/dev/authority-invariants.md) — Complete authority model with all invariants enforced

### Tests
- **14 new tests** (54 total intent tests, 142 Tier 1 tests passing)
  - `test_view_intent_is_authoritative`
  - `test_delete_intent_validates_but_defers_state_change`
  - `test_all_destructive_click_routes_through_intents`
  - View intent validation tests (6 tests)
  - Delete intent validation tests (5 tests)

## Changed

### State Mutation Authority
- **All user-initiated state changes** now flow through `handle_intent()` → `_apply_*()` methods
- **UI components** no longer call `set_state()` directly for user actions
- **Orchestration** limited to recording state sync only, with edit-safety constraints

## Fixed

### State Consistency
- No more silent state changes without validation
- All transitions produce `IntentResult` with success/failure reason
- Clear audit trail for all state mutations

## Technical Notes

**Phase 5 Stopping Condition Met:**
- All user interactions flow through authoritative intent handlers
- Only 2 orchestration `set_state()` calls remain (in `sync_recording_status_from_engine()`)
- All destructive actions (delete, discard, cancel) route through intent layer

---

# v1.7.0 - Transactional Editing

**Date:** January 2026  
**Status:** Release

---

## Summary

Implements transactional editing model with explicit enter/exit semantics. Edit sessions can only be exited through terminal intents (`CommitEditsIntent` or `DiscardEditsIntent`), ensuring unsaved changes are never silently lost.

## Added

### Terminal Intent System
- **`CommitEditsIntent`**: Authoritative method to save edits and exit editing state
  - Precondition: `state == EDITING`
  - Postcondition: `state == VIEWING`, `_has_unsaved_changes == False`
  - Emits `saveRequested` signal to persist content
- **`DiscardEditsIntent`**: Authoritative method to abandon edits and exit editing state
  - Precondition: `state == EDITING`
  - Postcondition: `state == VIEWING`, `_has_unsaved_changes == False`
  - Does NOT emit save signal (content discarded)
- **`EditTranscriptIntent`**: Authoritative method to enter editing state
  - Precondition: `state == VIEWING`, transcript loaded
  - Postcondition: `state == EDITING`
  - Rejects in `IDLE` (no transcript) or `RECORDING`

### Edit Invariants
- **Invariant 1**: Can only enter editing from `VIEWING` with loaded transcript
- **Invariant 2**: Cannot begin recording while editing
- **Invariant 3**: Cannot view different transcript with unsaved edits
- **Invariant 4**: Edit state can only exit through terminal intents
- **Invariant 5**: Terminal intents clear `_has_unsaved_changes` flag
- **Invariant 6**: `RECORDING` implies `_has_unsaved_changes == False`

### Documentation
- [Edit Invariants](docs/dev/edit-invariants.md) — Transactional editing guarantees

### Tests
- **19 new tests** (40 total intent tests, 128 Tier 1 tests passing)
  - `TestEditIntentStateAssertions` (5 tests): Edit entry validation
  - `TestCommitIntentStateAssertions` (4 tests): Commit terminal behavior
  - `TestDiscardIntentStateAssertions` (4 tests): Discard terminal behavior
  - `TestPhase4StoppingCondition` (2 tests): Verify only terminal intents exit editing
  - Edit safety tests (4 tests): Recording/view blocked during editing

## Changed

### Edit Flow Authority
- Save button now routes through `CommitEditsIntent`
- Cancel/discard actions route through `DiscardEditsIntent`
- Edit button routes through `EditTranscriptIntent`
- All edit-related state changes use authoritative `_apply_*()` methods

## Fixed

### Data Safety
- **Unsaved changes protected**: Recording, navigation, and deletion blocked during editing
- **No silent exits**: Edit state can only be left through explicit commit or discard
- **State consistency**: All edit transitions enforce pre/postconditions with assertions

## Technical Notes

**Phase 4 Stopping Condition Met:**
- Editing impossible to exit without explicit terminal intent
- No edit-related state mutated outside `_apply_*()` methods
- All 6 invariants enforced by runtime assertions

---

# v1.6.0 - Recording Intent Authority

**Date:** January 2026  
**Status:** Release

---

## Summary

Establishes authoritative intent handling for recording operations. All recording state transitions (begin, stop, cancel) now flow through the intent layer with proper validation and state assertions.

## Added

### Authoritative Recording Intents
- **`BeginRecordingIntent`**: Sole legal pathway for `IDLE`/`VIEWING` → `RECORDING` transitions
  - Precondition: `state == IDLE` or `state == VIEWING`
  - Postcondition: `state == RECORDING`, `_has_unsaved_changes == False`
  - Emits `recordingStartRequested` signal after state mutation
- **`StopRecordingIntent`**: Authoritative transcription trigger
  - Precondition: `state == RECORDING`
  - Postcondition: transcribing status set, `processingRequested` emitted
- **`CancelRecordingIntent`**: Authoritative recording cancellation
  - Precondition: `state == RECORDING`
  - Postcondition: `state == IDLE`, `_has_unsaved_changes == False`

### Test Infrastructure
- **Test Tier Classification**: Separated UI-independent (Tier 1) and UI-dependent (Tier 2) tests
  - Tier 1: 107 tests (fast, no Qt widget instantiation)
  - Tier 2: UI integration tests requiring full widget setup
- **pytest marker**: `ui_dependent` for selective test execution
- **Run Tier 1 only**: `pytest -m 'not ui_dependent'`

### Invariant Enforcement
- **Assertion guards** on all recording state transitions
- **Precondition/postcondition docstrings** on all `_apply_*()` methods

### Tests
- **25 intent tests passing** (107 total Tier 1 tests)
- Recording intent authority verified for all three operations

## Changed

### Button Click Flow
- Primary click button (`_on_primary_click`) now creates intents and routes through `handle_intent()`
- Destructive click (`_on_destructive_click`) routes `RECORDING` case through `CancelRecordingIntent`
- No dual authority: `button click → intent → handle_intent → _apply_* → state mutation`

### Method Naming
- `_bridge_begin_recording` → `_apply_begin_recording` (authoritative mutator)
- `_bridge_stop_recording` → `_apply_stop_recording` (authoritative mutator)
- Added `_apply_cancel_recording` (authoritative mutator)

## Fixed

### State Consistency
- Recording state changes now validated and logged
- All transitions produce `IntentResult` with outcome tracking
- Debug assertions catch invalid state mutations

## Technical Notes

**Phase 3 Complete:**
- All recording intents route through authoritative `_apply_*()` methods
- Legacy direct state mutation from buttons eliminated
- Clear separation between UI event handling and state mutation

---

# v1.5.0 - Intent-Driven Interaction Foundation

**Date:** January 2026  
**Status:** Release

---

## Summary

Foundational release establishing the intent-driven interaction architecture. Introduces semantic vocabulary for all user actions without changing existing behavior, setting the stage for authoritative state management and transactional editing.

## Added

### Interaction Vocabulary
- **`InteractionIntent`**: Base class for all user actions with 8 concrete intent types:
  - `BeginRecordingIntent`: Start recording
  - `StopRecordingIntent`: Stop recording and transcribe
  - `CancelRecordingIntent`: Abort recording without transcribing
  - `ViewTranscriptIntent`: Load transcript for viewing
  - `EditTranscriptIntent`: Enter editing mode
  - `CommitEditsIntent`: Save edits and exit editing
  - `DiscardEditsIntent`: Abandon edits and exit editing
  - `DeleteTranscriptIntent`: Remove transcript

### Intent Processing Framework
- **`IntentOutcome`** enum: `ACCEPTED`, `REJECTED`, `DEFERRED`, `NO_OP`
- **`IntentResult`**: Records outcome, reason, and state for every action
- **`MainWorkspace.handle_intent()`**: Central dispatch method for all intents
- **`intentProcessed`** signal: Observability hook for intent outcomes

### Documentation
- [Interaction Architecture Audit](docs/dev/interaction-audit.md) — Phase 1 baseline documenting all 14 state mutation points
- [Intent Catalog](docs/dev/intent-catalog.md) — Complete vocabulary of user intents

### Tests
- **25 new tests** for intent construction and passthrough behavior
- No state assertions yet (additive scaffolding only)

## Changed

### Architecture Patterns
- Introduced explicit intent objects for all user actions
- Added single authoritative dispatch point (`handle_intent()`)
- Maintained existing signal wiring (no behavioral changes)

## Technical Notes

**Phase 1-2 Complete:**
- Semantic scaffolding in place for intent-driven refactor
- Existing authority violations intentionally preserved for visibility
- `set_state()` calls documented in audit remain unchanged
- This is an additive-only release—existing behavior unchanged

**Future Phases:**
- Phase 3: Make recording intents authoritative
- Phase 4: Implement transactional editing with terminal intents
- Phase 5: Consolidate all user-initiated state changes through intents
- Phase 6: Add intent outcome visibility layer

---

# v1.4.3 - Intent Architecture Planning

**Date:** January 2026  
**Status:** Planning

---

## Summary

Planning release establishing the roadmap for intent-driven interaction architecture refactor. Documents all existing state mutation points and signal wiring to serve as baseline for authority consolidation.

## Added

### Documentation
- [Interaction Architecture Audit](docs/dev/interaction-audit.md) — Comprehensive audit of current interaction patterns:
  - 14 state mutation points across `MainWorkspace` and `MainWindow`
  - Complete signal-slot wiring for controls, content, and sidebar
  - State transition flows for all user interactions
  - Identified 5 external `set_state()` calls (authority violations)
  - Refactor targets for Phases 2-4

## Technical Notes

**Purpose:** This audit serves as the authoritative reference for measuring refactor progress through Phases 2-6. No code changes in this release—purely architectural documentation.

**Identified Issues:**
- Multiple components directly mutate workspace state
- No unified validation point for user actions
- Edit state can be exited through multiple pathways
- State transitions lack explicit success/failure semantics

---

# v1.4.2 - Comprehensive Error Isolation

**Date:** January 2026  
**Status:** Release

---

## Summary

Stability-focused release implementing comprehensive error isolation across all signal handlers, callbacks, and critical operations. Introduces new error handling utilities (`safe_callback`, `safe_slot_silent`) and adds deferred model invalidation to prevent segfaults during focus group operations.

## Major Changes

### Error Isolation Framework

**New Utilities:**
- `safe_callback(fn, context)` - Wraps lambda signal handlers to catch & log exceptions silently
- `safe_slot_silent(context)` - Decorator for background operations (log-only, no dialog)

**Philosophy:**
- **User actions** → Error dialog (explicit feedback via `@safe_slot`)
- **Background ops** → Log-only (silent failure via `@safe_slot_silent`)
- **Lambda handlers** → `safe_callback()` wrapper (isolated errors)

### Deferred Model Invalidation

**Problem:** Segfault when assigning transcripts to focus groups from the Recent tab. Root cause: proxy model called `invalidateFilter()` during context menu callback, corrupting the `QModelIndex` mid-operation.

**Solution:** Introduced `QTimer` with 0ms interval to defer filter invalidation until after the callback completes:

```python
self._invalidate_timer = QTimer()
self._invalidate_timer.setSingleShot(True)
self._invalidate_timer.setInterval(0)
self._invalidate_timer.timeout.connect(self.invalidateFilter)

# Signal connections now use deferred invalidation
self._connections = [
    (history_manager.entryUpdated, safe_callback(
        lambda _: self._invalidate_timer.start(), "entryUpdated")),
]
```

### Protected Components

| Component | Protection Added |
|-----------|------------------|
| `FocusGroupTree` | try/except + logging on all CRUD methods |
| `HistoryTreeView` | `safe_callback` on context menu lambdas, error handling on CRUD |
| `FocusGroupProxyModel` | `safe_callback` on signal lambdas, protected `filterAcceptsRow()` |
| `KeyListener` | Error isolation in `_trigger_callbacks()` |
| `ResultThread` | try/except around audio callback |
| `Sidebar` | `safe_callback` on lambda signal connections |

### UI Bug Fixes

- **Fixed**: Ghost context menus appearing on deleted transcript locations
- **Fixed**: Sidebar collapsing when deleting transcripts from Recent/Focus Groups
- **Fixed**: Recording stopping when deleting a transcript during recording
- **Fixed**: Header text overflow (month/day/timestamp truncation)
- **Fixed**: Welcome text font size too large

## Files Modified (10)

- `src/ui/utils/error_handler.py` - Added `safe_callback()`, `safe_slot_silent()`
- `src/ui/utils/__init__.py` - Exported new utilities
- `src/ui/widgets/focus_group/focus_group_tree.py` - Protected all CRUD methods
- `src/ui/widgets/history_tree/history_tree_view.py` - Protected CRUD, wrapped lambdas
- `src/ui/models/focus_group_proxy.py` - Deferred invalidation, protected filters
- `src/ui/components/sidebar/sidebar_new.py` - Wrapped lambda connections
- `src/key_listener.py` - Isolated callback errors
- `src/result_thread.py` - Protected audio callback
- `src/ui/components/main_window/main_window.py` - Error handling on slots
- `src/ui/constants/typography.py` - Reduced `GREETING_SIZE` (48px → 24px)

## Testing

- **29 error handling tests** including new integration tests
- **All tests passing** with no regressions
- Tests cover: `safe_callback`, `safe_slot_silent`, error isolation in KeyListener, model edge cases

## Technical Notes

- Deferred invalidation pattern prevents Qt model/view corruption during callbacks
- All exceptions now logged to `~/.local/share/vociferous/logs/vociferous.log`
- Error isolation ensures one failing callback doesn't break subsequent callbacks
- No segfaults possible from focus group operations

---

# v1.4.1 - Design System Consolidation & Error Handling

**Date:** January 2026  
**Status:** Release

---

## Summary

Architecture refinement release focused on design system consolidation and code hygiene. Introduces Refactoring UI-compliant typography and spacing scales, consolidates all per-widget styles into a single unified stylesheet, adds structured error handling with user-facing dialogs, and removes 12 unused files from the codebase.

## Major Changes

### Design System Consolidation

**Typography Scale (Refactoring UI compliant):**
- Hand-crafted scale: 11, 13, 16, 20, 24, 32, 48px
- Two weights only: 400 (normal), 600 (emphasis)
- No orphan sizes or arbitrary values

**Spacing Scale (non-linear):**
- 8-step scale: 4, 8, 12, 16, 24, 32, 48, 64px
- Semantic aliases: `APP_OUTER=16`, `MAJOR_GAP=16`, `MINOR_GAP=8`
- All magic numbers replaced with named constants

**Color System (3-tier text hierarchy):**
- `TEXT_PRIMARY=#d4d4d4` - Main content
- `TEXT_SECONDARY=#888888` - Supporting text
- `TEXT_TERTIARY=#555555` - Disabled/hints
- Consolidated accent color: `PRIMARY=#5a9fd4`

### Unified Stylesheet Architecture
- **Consolidated**: All per-widget `*_styles.py` files merged into `unified_stylesheet.py`
- **Removed**: Redundant StylesheetRegistry and Theme classes
- **Pattern**: Single `generate_unified_stylesheet()` applied at app startup
- **Benefit**: No per-widget `setStyleSheet()` calls, consistent styling, faster startup

### Error Handling Framework
- **Added**: `error_handler.py` - Centralized error management
- **Added**: `error_dialog.py` - User-facing error notification dialogs
- **Added**: `test_error_handling.py` - Comprehensive error handling tests
- **Pattern**: Structured try/except → log → optionally show dialog

### Documentation Update
- **Added**: `docs/images/recording_state.png` - Recording state screenshot

## Files Removed (12)

### Orphan Modules
- `src/input_simulation.py` - Unused input injection code

### Redundant Style Files (now in unified_stylesheet.py)
- `src/ui/components/settings/settings_styles.py`
- `src/ui/components/sidebar/sidebar_styles.py`
- `src/ui/components/title_bar/title_bar_styles.py`
- `src/ui/components/workspace/workspace_styles.py`
- `src/ui/widgets/focus_group/focus_group_styles.py`
- `src/ui/widgets/history_tree/history_tree_styles.py`

### Orphan Sidebar Components
- `src/ui/components/sidebar/sidebar.py` - Replaced by sidebar_new.py
- `src/ui/components/sidebar/sidebar_edge.py` - Unused

### Dead Infrastructure
- `src/ui/styles/stylesheet_registry.py` - Replaced by unified stylesheet
- `src/ui/styles/theme.py` - Unused theme abstraction
- `src/ui/widgets/history_tree/history_tree_delegate_new.py` - Orphan delegate

## Testing

- **All 142 tests passing** (1 skipped intentionally)
- **mypy clean**: 86 source files, 0 errors
- **No regressions** in existing functionality

## Technical Notes

- Design system follows Refactoring UI best practices for visual hierarchy
- Unified stylesheet eliminates style duplication and ordering issues
- Centralized constants enable systematic design changes
- Error handling improves debugging without disrupting user experience

---

# v1.4.0 - UI Overhaul & Comprehensive Metrics Framework

**Date:** January 10, 2026  
**Status:** Ready for refinement engine phase

---

## Summary

Complete visual redesign and metrics foundation. Implemented focus groups UI with dynamic sidebar, functional search system, real-time waveform visualization, and comprehensive transcription analytics framework. The UI now provides transparency about the cognitive and productivity dimensions of dictation.

## Major Features

### Focus Groups Management
- **Implemented**: Complete focus groups UI with visual sidebar
- **Added**: Dynamic focus group tree with custom delegation and font sizing
- **Added**: Create/rename/delete focus groups through sidebar context menu
- **Added**: Proper visual distinction and color coding for focus groups

### Recent Transcripts View
- **Implemented**: Recent transcripts tab showing last 7 days of activity
- **Added**: Clean, organized transcript listing with timestamps
- **Added**: Quick access to recently dictated content

### Search System
- **Implemented**: Full-text search across all transcripts
- **Added**: Real-time search interface integrated into sidebar
- **Added**: Highlight matching transcripts in search results
- **Added**: Clear/cancel search functionality

### Waveform Visualization
- **Implemented**: Real-time audio waveform display during recording
- **Added**: Visual feedback for recording state
- **Added**: Waveform scaling and responsive design
- **Added**: Integration with recording lifecycle

### Metrics Framework

#### Per-Transcription Metrics (Row 0: Human vs Machine Time)
- **Recording Time**: Total human cognitive time (speaking + thinking)
- **Speech Duration**: Machine-processed speech time (VAD-filtered segments from Whisper)
- **Silence Time**: Absolute time spent thinking/pausing (calculated as difference)

#### Per-Transcription Metrics (Row 1: Productivity & Efficiency)
- **Words/Min**: Idea throughput (words per minute of cognitive time)
- **Typing-Equivalent Time Saved**: Time saved vs manual composition at 40 WPM
- **Speaking Rate**: Pure articulation speed during active speech (WPM excluding pauses)

#### Lifetime Analytics (Bottom Bar)
- **Total Spent Transcribing**: Cumulative recording time across all transcripts
- **Total Saved by Transcribing**: Total time saved vs typing (all transcripts combined)
- **Total Transcriptions**: Count of completed transcriptions
- **Total Transcription Word Count**: Cumulative words across entire history

#### Metrics Explanation Dialog
- **Added**: Help → Metrics Calculations detailed documentation
- **Explains**: Definition and formula for each metric
- **Explains**: Philosophy: "Silence is not waste — it's cognition"
- **Explains**: Explicit assumptions (40 WPM typing baseline)
- **Explains**: How raw duration differs from machine-processed time

### UI/UX Refinements
- **Added**: Dynamic greeting message (Good Morning/Afternoon/Evening based on time of day)
- **Improved**: Typography scale (greeting 42pt, body 19pt, focus group names 17pt)
- **Improved**: Spacing and padding throughout (GREETING_TOP_MARGIN 16px, tab buttons 18px 24px)
- **Added**: Sidebar tab bar with bold text (font-weight 700)
- **Added**: Tab text wrapping (white-space: normal)
- **Added**: Tooltip on "Typing-Equivalent Time Saved" metric (semantic anchoring)
- **Added**: Search button styling (transparent background)
- **Moved**: Metrics display above content box (cleaner layout, no overlay issues)
- **Fixed**: Button height alignment (44px for text buttons, matching search button)

### Database & Backend

#### Speech Duration Tracking
- **Added**: `speech_duration_ms` column to transcripts table (schema v1 → v2)
- **Added**: Automatic schema migration for existing databases
- **Implemented**: VAD segment extraction from Whisper transcribe output
- **Implemented**: Speech duration calculation in transcription pipeline

#### Data Flow
- **Updated**: `result_thread.py` to extract and pass `speech_duration_ms`
- **Updated**: `transcription.py` to return `tuple[str, int]` (text, speech_duration_ms)
- **Updated**: `history_manager.py` to persist dual-duration metrics
- **Updated**: All database queries to handle speech_duration_ms

### Architecture Improvements
- **Removed**: Orphan metrics widgets (fixed Wayland window tiling bug)
- **Separated**: Metrics display from content panel (workspace-level ownership)
- **Centralized**: All typography constants in typography.py
- **Centralized**: All spacing constants in spacing.py

## Changes by Category

### Files Modified: 132
### Commits: Ready for single comprehensive commit

### Component Files Updated
- `src/ui/components/sidebar/` - Focus groups, tab bar, styling
- `src/ui/components/workspace/` - Metrics, content layout, header
- `src/ui/components/main_window/` - Menu integration for metrics dialog
- `src/ui/widgets/` - Custom dialogs, waveform, focus group tree
- `src/ui/constants/` - Typography and spacing scales
- `src/` - Core pipeline updates for metrics data

### Database Files
- `src/history_manager.py` - Schema v2 migration
- `src/transcription.py` - VAD duration extraction
- `src/result_thread.py` - Dual-duration threading

## Testing
- All existing tests passing
- Manual testing of metrics with live recordings
- Verified graceful degradation for pre-migration transcripts
- Verified Wayland compatibility (no floating windows)

## Philosophy & Design Decisions

**Silence is measurement, not waste.** This release introduces a measurement framework that treats thinking time as a first-class concern. Rather than hiding pauses or assuming they don't exist, Vociferous now:

1. Separates human time (recording) from machine time (speech)
2. Makes cognitive time explicit and measurable (silence time)
3. Derives productivity metrics that account for thinking
4. Provides complete transparency via explanation dialog
5. Never misleads about time saved

The metrics are not about guilt or optimization; they're about understanding the dictation experience.

## Next Phase

Refinement engine implementation planned. This provides the technical foundation for:
- Advanced text corrections powered by context
- Grammar and style improvements
- Transcript enhancement workflows

---

# v1.3.0 Beta - Focus Groups (Data Layer)

**Date:** January 2026  
**Status:** Beta

---

## Summary

Backend implementation of Focus Groups (Foci) - user-defined organization for transcripts. Provides complete CRUD operations for grouping transcripts by subject or purpose. UI integration deferred to future release.

## Changes

### Focus Group Data Layer

- **Added**: `create_focus_group(name)` - Create new focus groups with user-defined names
- **Added**: `get_focus_groups()` - Retrieve all focus groups ordered by creation date
- **Added**: `rename_focus_group(id, new_name)` - Rename existing focus groups
- **Added**: `delete_focus_group(id, move_to_ungrouped)` - Delete groups with safety controls:
  - Default behavior: move transcripts to ungrouped (via `ON DELETE SET NULL` foreign key)
  - Optional blocking: prevent deletion if group contains transcripts
- **Added**: `assign_transcript_to_focus_group(timestamp, group_id)` - Move transcripts between groups or to ungrouped (None)
- **Added**: `get_transcripts_by_focus_group(group_id, limit)` - Filter transcripts by group membership

### Database Enforcement

- **Enforced**: Foreign key constraints via `PRAGMA foreign_keys = ON` in all relevant methods
- **Enforced**: `ON DELETE SET NULL` cascade behavior - deleting a group automatically ungroupes its transcripts
- **Added**: Transaction-level foreign key enforcement for data integrity

### Testing

- **Added**: 14 comprehensive unit tests covering:
  - Focus group creation, listing, renaming, deletion
  - Transcript assignment and filtering by group
  - Foreign key cascade behavior (ungrouping on delete)
  - Blocking deletion of non-empty groups
  - Ungrouped transcript queries (NULL group_id)
- **Verified**: All 41 tests passing (27 original + 14 focus group tests)
- **Verified**: Zero regressions in existing functionality

## Behavioral Notes

- **Ungrouped is default**: Transcripts without a focus group assignment have `focus_group_id = NULL`
- **Exactly one place**: Each transcript belongs to zero or one focus group (no multiple assignments)
- **Safe deletion**: Foreign key constraint ensures transcripts never reference deleted groups

## UI Status

- **No user-facing changes**: Focus groups are fully implemented in the data layer but not yet exposed in the UI
- **Future work**: Phase 2 UI integration will add sidebar navigation, group management dialogs, and filtered transcript views

---

# v1.2.0 Beta - SQLite Migration

**Date:** January 2026  
**Status:** Beta

---

## Summary

Major persistence layer overhaul replacing JSONL storage with SQLite database. Introduces foundational schema for future features including focus groups (Phase 2) and content refinement (Phase 4+). All existing functionality preserved with improved performance for updates and queries.

## Changes

### Storage & Data Model

- **Migrated**: Complete replacement of JSONL file storage with SQLite database (`~/.config/vociferous/vociferous.db`)
- **Added**: `transcripts` table with dual-text architecture:
  - `raw_text` - Immutable audit baseline (what Whisper produced)
  - `normalized_text` - Editable content (target for user edits and future refinement)
  - Both fields initialized to identical values on creation
- **Added**: `focus_groups` table (currently unused, ready for Phase 2 navigation)
- **Added**: `schema_version` table for future database migrations
- **Added**: Auto-increment integer primary keys (`id`) for stable references
- **Added**: Foreign key constraint from `transcripts.focus_group_id` to `focus_groups(id)` with `ON DELETE SET NULL`
- **Added**: Database indexes on `id DESC`, `timestamp`, and `focus_group_id` for efficient queries
- **Enforced**: `raw_text` immutability - no code path modifies raw transcription after creation
- **Enforced**: Foreign key constraints via `PRAGMA foreign_keys = ON`

### API & Compatibility

- **Preserved**: Complete API compatibility - all `HistoryManager` methods maintain identical signatures
- **Preserved**: `HistoryEntry` dataclass unchanged (timestamp, text, duration_ms)
- **Preserved**: Export functionality for txt, csv, and markdown formats
- **Preserved**: Automatic rotation when exceeding `max_history_entries` config value
- **Changed**: Internal ordering now uses `id DESC` instead of `created_at DESC` for deterministic sort order
- **Changed**: Rotation deletes by `id ASC` (oldest entries) instead of timestamp-based sorting

### Testing

- **Added**: Comprehensive test suite with 27 new unit tests covering:
  - Database initialization and schema validation
  - CRUD operations (create, read, update, delete)
  - `raw_text` immutability enforcement
  - `normalized_text` editability
  - Export format validation
  - Rotation behavior
  - Fixture isolation for clean test state
- **Added**: Database-backed test fixtures using temporary SQLite files
- **Verified**: All 77 existing tests pass with zero regressions

### Breaking Changes

- **Removed**: Legacy JSONL storage support (no migration path from existing history files)
- **Note**: Users will start with fresh history after upgrade - existing `~/.config/vociferous/history.jsonl` is no longer read

## Technical Notes

- SQLite ordered by auto-increment ID ensures insertion order preserved even with rapid successive entries
- `created_at` timestamp retained for future time-based queries but not used for ordering
- Schema designed to support Phase 2 (focus groups) and Phase 4+ (refinement) without structural changes
- Database location consistent with existing config directory pattern

---

# v1.1.1 Beta - Documentation Refresh

**Date:** December 2025  
**Status:** Beta

---

## Summary

Documentation-focused update: clarified current behavior (press-to-toggle only), aligned wiki with ARCHITECTURE.md as source of truth, and fixed mermaid diagrams.

## Changes

- **Wiki refresh**: Replaced Recording page to reflect single supported mode (press-to-toggle); updated Text Output, Config Options, Keycodes Reference, Hotkey System, Backend Architecture, Threading Model, and Home navigation links.
- **Architecture link-out**: Added guidance to treat ARCHITECTURE.md as canonical; wiki pages now act as concise summaries.
- **Mermaid fixes**: Corrected High-Level Architecture diagram label (main.py/VociferousApp) and refreshed data-flow/threading diagrams in wiki to render properly.
- **Config clarification**: Documented `recording_mode` as fixed to `press_to_toggle`; noted default Alt hotkey captures both Alt keys (known limitation).

## Notes

- No functional code changes; this release is purely documentation and clarity improvements.

---

# v1.1.0 Beta - Custom Title Bar & History Enhancements

**Date:** December 2025  
**Status:** Beta

---

## Summary

Feature release introducing a custom frameless title bar with unified menu/controls, enhanced history management with file watching and persistent deletion, a Cancel button for aborting recordings, and bundled application icons.

---

## Changes

### Custom Title Bar

- **Added**: Custom frameless `TitleBar` widget with menu bar, centered title, and window controls (minimize, maximize, close) in a single row
- **Added**: Wayland-native drag support via `startSystemMove()` for proper window dragging on Wayland compositors
- **Added**: X11 fallback drag handling for traditional window movement
- **Added**: Double-click title bar to maximize/restore window
- **Added**: Styled window controls with hover effects (blue highlight for min/max, red for close)
- **Added**: Border styling for frameless window (`1px solid #3c3c3c`, `border-radius: 6px`)
- **Added**: `QT_WAYLAND_DISABLE_WINDOWDECORATION=1` environment variable for client-side decorations on Wayland

### History Widget Enhancements

- **Added**: `QFileSystemWatcher` with 200ms debounce to auto-reload history when file changes externally
- **Added**: `delete_entry()` method in HistoryManager for persistent deletion from JSONL file
- **Added**: Delete key shortcut with `Qt.ApplicationShortcut` context for reliable deletion even when focus shifts
- **Added**: `historyCountChanged` signal to track entry count for UI state updates
- **Added**: `entry_count()` helper method for counting non-header entries
- **Added**: Automatic fallback selection after deletion (prefers previous entry, then next)
- **Added**: Automatic day header removal when all entries under a day are deleted
- **Fixed**: History widget now accepts `HistoryManager` in constructor for proper initialization order

### Main Window Improvements

- **Added**: Cancel button in current transcription panel to abort recording without transcribing
- **Added**: `cancelRecordingRequested` signal connected to `_cancel_recording()` in main app
- **Added**: History menu "Open History File" action to open JSONL file in system default handler
- **Added**: `_update_history_actions()` method to enable/disable Export controls based on history count
- **Fixed**: Export button, menu action, and Ctrl+E shortcut now disabled when history is empty
- **Fixed**: Guard added to `_export_history()` to show status message when nothing to export
- **Changed**: `display_transcription()` now accepts `HistoryEntry` for consistent timestamps
- **Changed**: `load_entry_for_edit()` no longer steals focus (cursor position preserved)
- **Changed**: Placeholder text updated to "Your transcription will appear here..."

### Application Icons

- **Added**: Bundled icon assets in `icons/` directory:
  - `512x512.png` - High-resolution application icon
  - `192x192.png` - Medium-resolution icon
  - `favicon.ico` - Windows/multi-resolution icon
- **Changed**: Tray icon now loads from bundled assets with fallback to theme icon

### Launcher Script

- **Added**: `RUST_LOG=error` environment variable to suppress verbose wgpu/Vulkan warnings

### Bug Fixes

- **Fixed**: Unused `datetime` import removed from main_window.py (ruff compliance)
- **Fixed**: Result thread now properly sets `self.result_thread = None` on completion to prevent stale references
- **Fixed**: History widget initialization order ensures buttons exist before loading history (prevents AttributeError)

---

# v1.0.1 Beta - UI Polish & Editing Support

**Date:** December 2025  
**Status:** Beta

---

## Summary

Refinement release focusing on UI polish and introducing editable transcriptions. History entries can now be edited directly in the main window, and the layout has been simplified to a fixed 50/50 split.

---

## Changes

### History Widget Behavior

- **Single-click** on history entry loads it into editor for modification
- **Double-click** copies entry to clipboard
- **Removed**: Re-inject functionality (replaced by copy/paste workflow)
- **Removed**: Tooltips on history items (cleaner appearance)
- **Fixed**: Timestamp format now consistently shows "10:03 a.m." style

### Main Window Layout

- **Replaced**: QSplitter with fixed 50/50 horizontal layout (no resize handle)
- **Added**: Editable transcription panel with Save button
- **Added**: `update_entry()` in HistoryManager for saving edits

### Settings Dialog

- **Added**: Device setting (auto/cuda/cpu) exposed in UI
- **Added**: Dynamic compute_type filtering based on device selection
- **Fixed**: float16 automatically falls back to float32 on CPU

### Project Structure

- **Moved**: Scripts reorganized into `scripts/` folder
  - `run.py` → `scripts/run.py`
  - `install.sh` → `scripts/install.sh`
  - `check_deps.py` → `scripts/check_deps.py`
- **Updated**: `vociferous.sh` references `scripts/run.py`

### Documentation

- **Updated**: README.md to match current codebase
- **Updated**: ARCHITECTURE.md with accurate module descriptions
- **Fixed**: Install and run paths reference `scripts/` folder

---

# v1.0.0 Beta - Polished UI & History System

**Date:** December 2025  
**Status:** Beta

---

## Summary

Major milestone release introducing a full-featured main window with transcription history, graphical settings dialog, and a simplified clipboard-only workflow. The floating status window has been replaced with an integrated UI that provides history management, export capabilities, and live configuration updates.

---

## Breaking Changes from Alpha

### UI Architecture

- **Removed**: `StatusWindow` and `BaseWindow` classes (floating frameless windows)
- **Removed**: Automatic text injection (unreliable on Wayland)
- **Replaced with**: `MainWindow` with integrated history and transcription panels
- **Replaced with**: Clipboard-only output (always copies, user pastes with Ctrl+V)

### Configuration

- **Removed**: `output_options.input_method` auto-inject options (pynput/ydotool/dotool direct typing)
- **Removed**: `output_options.auto_copy_clipboard`, `auto_inject_text`, `auto_submit_return` cascading options
- **Simplified**: All transcriptions now copy to clipboard automatically

---

## What's New

### Main Window

A full application window replaces the minimal floating status indicator:

```
┌──────────────────────────────────────────────────────┐
│ File  History  Settings  Help                        │
├──────────────────────────────────────────────────────┤
│ ┌──History────────┐ │ ┌──Current Transcription────┐ │
│ │ ▼ December 14th │ │ │                           │ │
│ │   10:03 a.m. ...│ │ │  Transcribed text here    │ │
│ │   9:45 a.m. ... │ │ │                           │ │
│ │ ▼ December 13th │ │ │       ● Recording         │ │
│ │   ...           │ │ │                           │ │
│ └─────────────────┘ │ └───────────────────────────┘ │
│ [Export] [Clear All]│ [Copy]            [Clear]     │
└──────────────────────────────────────────────────────┘
```

**Features:**
- **Dark theme** with blue accents (#1e1e1e background, #5a9fd4 highlights)
- **Responsive layout**: Side-by-side at ≥700px, stacked below
- **Resizable splitter** with visual grab handle
- **Window geometry persistence** (remembers size/position)
- **System tray integration** with minimize-to-tray behavior
- **One-time tray notification** when first minimized

### History System

Persistent transcription history with JSONL storage:

- **Storage**: `~/.config/vociferous/history.jsonl` (append-only, thread-safe)
- **Day grouping**: Entries organized under collapsible day headers (▼/▶)
- **Friendly timestamps**: "December 14th" headers, "10:03 a.m." entry times
- **Visual nesting**: Indented entries under day headers with styled headers
- **Auto-rotation**: Configurable max entries (default 1000)

**History Widget:**
- Click day headers to collapse/expand
- Double-click entries to copy
- Right-click context menu: Copy, Re-inject, Delete
- Keyboard navigation (Enter to copy, Delete to remove)

**Export:**
- **Text** (`.txt`): Timestamped entries
- **CSV** (`.csv`): Spreadsheet-compatible with headers
- **Markdown** (`.md`): `## Date` and `### Time` heading hierarchy

### Settings Dialog

Schema-driven graphical preferences dialog:

- Accessible via **Settings → Preferences** or **tray right-click → Settings**
- Dynamically built from `config_schema.yaml`
- Each schema section becomes a tab (Model Options, Recording Options, Output Options)
- Widget types inferred from schema (`bool` → checkbox, `str` with options → dropdown)
- Tooltips display setting descriptions
- Changes apply immediately (Apply or OK)

### Hotkey Rebinding

Live hotkey capture in Settings:

1. Click **Change...** next to Activation Key
2. Press desired key combination
3. Validation blocks reserved shortcuts (Alt+F4, Ctrl+C, etc.)
4. New hotkey active immediately—no restart required

**Implementation:**
- `HotkeyWidget` with capture mode
- `KeyListener.enable_capture_mode()` diverts events to callback
- `keycode_mapping.py` utilities for display/config string conversion

### Live Configuration Updates

Settings changes take effect without restart:

| Setting | Effect |
|---------|--------|
| `activation_key` | KeyListener reloads immediately |
| `input_backend` | Backend switches (evdev ↔ pynput) |
| `compute_type`, `device` | Whisper model reloads |

**Signal architecture:**
- `ConfigManager.configChanged(section, key, value)` signal
- Main app connects handlers for each setting type

### Recording Indicator

Compact pulsing indicator in the current transcription panel:

- **Recording**: Red "● Recording" with opacity pulse animation (0.3 ↔ 1.0)
- **Transcribing**: Orange "● Transcribing" (solid)
- **Idle**: Hidden

### UI Polish

- **Floating pill headers** with rounded borders for panel labels
- **Custom Clear History dialog** with Yes/No button layout (Yes left, No right)
- **Styled scrollbars** matching dark theme
- **Menu bar**: File, History, Settings, Help (View menu removed)
- **Keyboard shortcuts**: Ctrl+C (copy), Ctrl+E (export), Ctrl+H (focus history), Ctrl+L (clear)

---

## Files Added

```
src/
├── history_manager.py      # JSONL storage with rotation and export
└── ui/
    ├── history_widget.py   # Collapsible day-grouped history display
    ├── hotkey_widget.py    # Live hotkey capture widget
    ├── keycode_mapping.py  # KeyCode ↔ string utilities
    ├── main_window.py      # Primary application window (820 lines)
    ├── output_options_widget.py  # (Cascading checkboxes - deprecated)
    └── settings_dialog.py  # Schema-driven preferences dialog

tests/
└── test_settings.py        # Settings, hotkey, and config signal tests
```

## Files Removed

```
src/ui/
├── base_window.py          # Frameless window base class
└── status_window.py        # Floating status indicator

assets/
├── microphone.png          # Recording icon (now using text indicator)
├── pencil.png              # Transcribing icon
└── ww-logo.png             # Application logo (now using system theme icon)
```

## Files Modified

- **main.py**: Replaced StatusWindow with MainWindow, added HistoryManager, removed InputSimulator direct typing, clipboard-only workflow
- **input_simulation.py**: Added `reinitialize()` for live updates, auto-detection of input method
- **key_listener.py**: Added capture mode for hotkey rebinding
- **utils.py**: ConfigManager now extends QObject, emits `configChanged` and `configReloaded` signals
- **config_schema.yaml**: Simplified schema, marked internal options with `_internal: true`
- **run.py**: Suppresses Qt Wayland warnings

---

## Known Issues

- **Button padding**: Minor spacing issue between Export/Clear buttons and history pane bottom edge
- **Recording indicator font**: Slight font size inconsistency on the active recording indicator

---

## Platform Notes

### Wayland

The clipboard-only workflow was adopted because automatic text injection via ydotool/dotool is unreliable when window focus shifts during transcription. Copying to clipboard and letting the user paste with Ctrl+V is more robust.

### Model Caching

Model loading now tries `local_files_only=True` first to avoid unnecessary HTTP requests to HuggingFace, only downloading if not cached.

---

---

# v0.9.0 Alpha - Complete Architectural Rewrite

**Date:** December 2025  
**Status:** Pre-release

---

## Summary

Complete ground-up rewrite of Vociferous. The previous architecture (v0.7-v0.8) featured a daemon-based server, Kivy GUI, CLI with multiple commands, and support for multiple transcription engines. This release replaces it entirely with a minimal, focused design: a single-purpose hotkey-triggered dictation tool.

---

## Breaking Changes

**This version is not compatible with any previous version.** The entire codebase has been replaced.

### Architecture Removed

- **Daemon Server** - FastAPI-based background process with REST API
- **Kivy GUI** - Multi-screen application (home, settings, history)
- **CLI Commands** - `transcribe`, `daemon`, `bench`, `check`, `deps`
- **Multiple Engines** - Canary-Qwen, model registry, hardware detection
- **Configuration Presets** - Complex schema with validation and profiles
- **Progress System** - Rich progress tracking with callbacks

### Architecture Replaced With

- **Direct Execution** - Single `run.py` entry point, no daemon
- **Minimal UI** - PyQt5 status window + system tray icon
- **Hotkey Activation** - Press key to record, press again to transcribe
- **Single Engine** - faster-whisper only (distil-large-v3 default)
- **Simple Config** - YAML schema with sensible defaults

---

## New Design Philosophy

| Aspect | v0.8.x (Previous) | v0.9.0 (Current) |
|--------|-------------------|------------------|
| Source files | 60+ files in `vociferous/` | 8 files in `src/` |
| Test files | 50+ test files, 376 tests | 5 test files |
| UI framework | Kivy (Material Design) | PyQt5 (minimal) |
| Transcription | Daemon with REST API | Direct in-process |
| Engines | Multiple (registry-based) | faster-whisper only |
| Configuration | Pydantic schemas, presets | Simple YAML |
| Input detection | pynput only | evdev (Wayland) + pynput fallback |
| Text injection | pynput only | dotool/ydotool/pynput/clipboard |

---

## Rationale

The v0.7-v0.8 architecture was designed for a full-featured transcription application with batch processing, multiple engines, and GUI-driven workflows. The rewrite focuses on a single use case: **real-time dictation**.

**Why rewrite?**
1. **Simplicity** - Daemon architecture added complexity without benefit for dictation
2. **Wayland support** - Previous pynput-only approach broken on modern Linux
3. **Startup speed** - No daemon means instant activation
4. **Maintainability** - 8 files vs 60+ files

---

## What's New

### Wayland-First Input Handling

- **evdev backend** - Works on Wayland (requires `input` group membership)
- **pynput fallback** - Automatic fallback for X11 users
- **Multi-backend text injection** - dotool, ydotool, pynput, clipboard

### GPU Bootstrap Pattern

- Process re-executes with correct `LD_LIBRARY_PATH` for CUDA libraries
- Sentinel variable prevents infinite re-exec loop
- Works transparently - users just run `python run.py`

### Minimal UI

- Frameless floating status window
- Shows recording/transcribing state
- System tray for background operation
- No configuration dialogs (edit YAML directly)

### Simplified Installation

- `install.sh` creates venv, installs deps, verifies imports
- `check_deps.py` validates all required packages
- Single `requirements.txt` with pinned versions

---

## Files (New Structure)

```
Vociferous/
├── run.py                  # Entry point with GPU bootstrap
├── install.sh              # Installation script
├── check_deps.py           # Dependency validator
├── requirements.txt        # Pinned dependencies
├── src/
│   ├── main.py             # VociferousApp orchestrator
│   ├── utils.py            # ConfigManager singleton
│   ├── key_listener.py     # Hotkey detection (evdev/pynput)
│   ├── result_thread.py    # Audio recording & transcription
│   ├── transcription.py    # faster-whisper integration
│   ├── input_simulation.py # Text injection backends
│   ├── config_schema.yaml  # Configuration schema
│   └── ui/
│       ├── base_window.py  # Frameless window base
│       └── status_window.py # Status indicator
├── tests/                  # Minimal test suite
└── docs/
    └── ARCHITECTURE.md     # Comprehensive architecture guide
```

---

## Files Removed (136 files)

All files from the previous architecture deleted:
- `vociferous/` package (app, audio, cli, config, domain, engines, gui, server, setup)
- `tests/` subdirectories (app, audio, cli, config, domain, engines, gui, integration, refinement, server)
- Documentation (Design.md, daemon.md, Redesign.md, GUI recommendations)

---

## Migration

**There is no migration path.** v0.9.0 is a new application sharing only the name. If you relied on the daemon API, CLI commands, or Kivy GUI, those features no longer exist.

---

## Credits

The v0.1-v0.8 architecture served as exploration of what a full-featured transcription tool could look like. This rewrite takes the lessons learned and applies them to a simpler, more focused tool.`  