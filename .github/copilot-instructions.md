# Vociferous — Copilot & VS Code AI Instructions

## 0. Scope and Intent

This file defines **authoritative, binding instructions** for GitHub Copilot, VS Code AI agents, and any autonomous or semi-autonomous coding assistants operating in this repository.

These instructions exist to:

* Preserve long-term architectural integrity
* Reduce cognitive and procedural friction for a **solo maintainer**
* Prevent AI-introduced process ceremony
* Encode project invariants and design intent explicitly

All guidance in this file is **normative**, not advisory. If a conflict exists between AI defaults and this document, **this document takes precedence**.

---

## 1. Philosophy

**Move carefully and Socratically.** Before writing code, understand context. Before changing a pattern, understand why it exists.

* Ask clarifying questions when requirements are ambiguous (prefer 1-3 precise questions).
* For non-trivial work, propose a short plan before execution.
* Prefer small, verifiable increments over broad rewrites.
* When uncertain about intent, present 2-3 options with tradeoffs instead of guessing.
* When touching shared infrastructure (runtime, database, command bus, configuration), trace downstream consumers before editing.

---

## 2. Project Context (Always Read First)

**Vociferous** is a production-quality, Linux-native speech-to-text application written in **Python 3.12+**.

Core characteristics:

* Desktop GUI built with **PyQt6**
* Offline-capable transcription using **Whisper / faster-whisper**
* **Process-based Architecture**: Transcription runs in a dedicated subprocess (`core_runtime`) to ensure UI responsiveness
* **Component-based Design**: Orchestrated by an `ApplicationCoordinator`
* **Command Bus**: Centralized intent dispatch system
* **Small Language Model (SLM)** integration for text refinement

The project is actively developed and maintained by a **single primary developer**. All workflow rules are calibrated accordingly.

---

## 3. Architectural Invariants (Non-Negotiable)

### 3.1 Composition Root

* `src/main.py` is a thin entry point only.
* **`src/core/application_coordinator.py`** is the true Composition Root and owns lifecycle of services, UI, and runtime.
* New global services MUST be initialized in `ApplicationCoordinator`.

### 3.2 Intent-Driven Interaction

* **All** user actions that affect application state MUST be encapsulated as an `InteractionIntent`.
* Intents are dispatched via the **`CommandBus`** (`src/core/command_bus.py`).
* Widgets should NOT call service methods directly. They should dispatch intents.
* Intents are defined in `src/ui/interaction/intents.py`.

### 3.3 Process & Threading Model

* **Transcription Engine** runs in a separate process (`src/core_runtime/server.py`).
    * Communication is via IPC (`EngineClient` -> `PacketTransport`).
    * NEVER block the UI thread with model inference.
* **Background services** (e.g., SLM workers) run in `QThread` wrappers.
* The UI thread (`MainWindow`) handles presentation logic only.

### 3.4 Persistence Model

* Access persistence through **`HistoryManager`** (`src/database/history_manager.py`).
* **Immutability**: Original raw transcription is immutable.
* **Variants**: Edits, refinements, and formatted versions are stored as variants linked to original transcript ID.
* Do not overwrite original captures.

---

## 4. Repository Structure (Semantic and Binding)

The `src/` layout is intentional:

* `core/` — Application plumbing (Coordinator, CommandBus, Config, State)
* `core_runtime/` — Isolated process for transcription runtime and IPC
* `database/` — Persistence layer (repositories, manager, DTOs)
* `services/` — Business logic and background workers (audio, SLM, runtime services)
* `ui/` — PyQt6 views, widgets, and interaction logic
    * `interaction/` — Intent definitions
* `input_handler/` — Global hotkey and input listening
* `provisioning/` — Model download and management tools
* `refinement/` — Text-processing engines

Do not introduce new top-level directories without explicit approval.

---

## 5. Critical Patterns — Understand Before Changing

### 5.1 Command Bus Boundary

User-driven state changes should enter through intents and `CommandBus`, not by direct widget-to-service mutation calls.

### 5.2 Runtime Boundary

Transcription inference belongs in `core_runtime` process, not UI thread and not ad hoc worker calls from view code.

### 5.3 Variant Integrity

Raw transcript records are immutable. Refinements and edits are new variants linked to originals.

### 5.4 Styling Boundary

Use `src/ui/styles/unified_stylesheet.py` for styling changes. Avoid ad hoc inline style rules.

---

## 6. Coding Standards

### 6.1 Python

* Python **3.12+** only
* **Strict type hints** for function signatures
* Prefer frozen/slotted dataclasses for value objects
* Use `logging` (`src.core.log_manager` or `logging.getLogger(__name__)`)
* No `print()` for runtime diagnostics

### 6.2 Qt / UI

* Styling through `src/ui/styles/unified_stylesheet.py`
* Avoid inline `setStyleSheet()`
* Use `pyqtSignal` for cross-component communication when not using intents

---

## 7. Defensive Engineering Standards (Mandatory)

These constraints reduce high-risk failure modes common in AI-generated code.

### 7.1 Responsiveness & Concurrency Safety

* No heavy/blocking work on the UI thread.
* Do not run model inference in UI callbacks.
* Bound concurrent work; do not fan out unbounded task/thread creation.
* For retries or poll loops, always use finite bounds.

### 7.2 Process & IPC Safety

* Runtime IPC calls must include timeout and failure handling.
* Handle subprocess disconnect/restart paths explicitly.
* Do not introduce silent fallback paths that hide runtime failure.

### 7.3 Database Safety

* Route persistence writes through `HistoryManager` / repository abstractions.
* Preserve immutability + variant linkage semantics.
* Avoid check-then-act race patterns for mutable state updates.

### 7.4 Security & Logging Hygiene

* Never generate placeholder security logic that always succeeds.
* Sanitize user-controlled text before logging when needed (avoid log-forging via control characters).
* Avoid introducing unverified third-party dependencies.

### 7.5 Operational Resilience

* All external calls (runtime IPC, network downloads, subprocess ops) require explicit timeout.
* Retry logic must use bounded attempts with backoff.
* Long-running loops must have explicit exit conditions or maximum iteration bounds.
* Keep safety limits/rate limits unless there is a documented reason to change them.

### 7.6 Destructive Operation Safety

* Default to analysis/dry-run for destructive changes.
* Explain blast radius before data-destructive operations.
* Do not perform destructive schema/data operations without explicit user confirmation.

---

## 8. Workflow Model (Solo Maintainer, Production Quality)

### 8.1 Core Principle

Process exists to **reduce risk and cognitive load**, not to simulate team workflows.
AI agents MUST NOT introduce ceremony unless it provides clear functional benefit.

### 8.2 Issues & Branches

* **Issues**: Optional; use for complex, multi-session tracking.
* **Branches**:
    * Direct commits to `main` are allowed for localized, low-risk changes.
    * Branches are required for architectural refactors or high-risk features.

### 8.3 Commits

* Small, descriptive commits.
* Explain the *why*.

### 8.4 Anti-Ceremony Rule (Explicit)

AI agents MUST NOT:

* Create branches, issues, or PRs "for best practice" without specific cause
* Optimize for activity metrics
* Suggest maintenance-heavy CI/CD complexity without clear need

### 8.5 Plan -> Track -> Execute

For non-trivial changes (multi-file, multi-phase, or shared infrastructure):

1. Plan the phases and success criteria before edits
2. Track progress as work proceeds (update status continuously)
3. Verify each phase before starting the next

Use lightweight tracking (e.g., todo lists or temporary notes) and remove temporary artifacts after completion.
Prefer the simplest tracking mechanism that preserves safety; do not introduce process documents unless complexity warrants it.

---

## 9. Change Playbooks

### 9.1 Adding a New User Interaction

1. Define/update intent in `src/ui/interaction/intents.py`
2. Route it through `src/core/command_bus.py`
3. Implement service/runtime handling in the correct layer
4. Keep UI classes presentation-focused
5. Add/update tests

### 9.2 Adding/Changing Transcription or Refinement Behavior

1. Determine whether logic belongs in runtime, service, or refinement layer
2. Keep heavy inference off UI thread
3. Preserve transcript immutability + variant creation rules
4. Verify IPC and fallback behavior under failure modes
5. Add/update tests for regressions and edge cases

### 9.3 Persistence/Data Model Changes

1. Update model/repository code in `src/database/`
2. Preserve raw transcript immutability
3. Validate compatibility with `HistoryManager`
4. Verify tests touching history retrieval and variant lineage

---

## 10. Execution & Verification

* Use project virtual environment
* Run app via `./vociferous` (wraps `src/main.py`)
* Respect `requirements.txt`
* Run targeted tests first, then broader suites as needed
* Do not skip relevant tests for touched behavior

Common commands:

* `./vociferous`
* `pytest -v`
* `./scripts/run_tests.sh`

---

## 11. Guardrails (Quick Reference)

* Never block UI thread with inference or long operations
* Never bypass `CommandBus` for user-driven state changes
* Never overwrite original transcript captures
* Never add DB/network/process calls inside presentation-only widgets
* Never add unbounded retry loops or unbounded task fan-out
* Never add unbounded `while` loops without explicit termination strategy
* Never remove safety limits without justification
* Always set explicit timeouts on external calls
* Always run relevant tests before considering work complete

---

## 12. Final Rule

When in doubt:

**Favor clarity, reversibility, and architectural integrity over ceremony.**
