Below is a **rewritten, expanded, and invariants-first version** of the prompt file. It preserves all of your intent, but makes the rules *explicitly normative*, clarifies causality, strengthens invariants, and removes any ambiguity an autonomous agent could exploit. This is written as a **policy-grade instruction file**, not guidance.

You can drop this in as a direct replacement.

---

# Vociferous — AI Agent Operating Instructions (Authoritative)

## 0. Purpose and Authority

This document defines **binding operational constraints** for any autonomous or semi-autonomous agent operating within the Vociferous repository. These instructions are normative, not advisory.
Deviations are considered defects unless explicitly approved by the user.

The goals of this document are to:

1. Preserve architectural integrity over time
2. Enforce causal correctness in UI, data, and execution flows
3. Prevent undocumented behavior drift
4. Ensure long-term maintainability and agent interoperability

An agent must **fully understand these instructions before making changes**. If any instruction conflicts with existing code, the instruction takes precedence unless the user explicitly authorizes a change to this file.

---

## 1. Project Overview

**Vociferous** is a modern **Python 3.12+**, Linux-native, speech-to-text dictation system built around **OpenAI Whisper** via **faster-whisper**. It provides a **PyQt6** graphical interface with:

* System tray integration
* Global hotkey support across **Wayland** and **X11**
* Background audio capture and inference
* A persistent transcription history with dual-text semantics
* Pluggable input and output backends

Vociferous is designed as a **human-first, intent-driven system**. User actions express *desire*, not execution. Execution is centralized, observable, and constrained.

---

## 2. Architectural Principles (Non-Negotiable)

### 2.1 Intent-Driven UI (Primary Design Law)

All user interaction follows a **strict Intent Pattern** implemented in `src/ui/interaction/`.

#### Definition

An **Intent** is a declarative, immutable expression of *what the user wants*, not *how it is done*.

Examples:

* `BeginRecordingIntent`
* `StopRecordingIntent`
* `ViewTranscriptIntent`
* `EditNormalizedTextIntent`

#### Mandatory Rules

1. **Instantiation**

   * ALL user actions (buttons, menu items, hotkeys, tray actions) MUST resolve to an `InteractionIntent` dataclass.
   * Intents MUST be immutable: `@dataclass(slots=True, frozen=True)`.

2. **Propagation**

   * Intents MUST propagate **upward** through the widget hierarchy:

```
Leaf Widget → Component → Workspace → MainWindow / Controller
```
   * Propagation occurs exclusively via **Qt signals carrying intents**.

3. **Execution Authority**

   * Only **core controllers** (e.g., `MainWindow`, `MainWorkspace`) may:

     * Mutate application state
     * Trigger background work
     * Interact with the data layer
   * Leaf or sibling widgets MUST NEVER perform execution logic.

4. **Isolation Invariant**

   * **Sibling widgets MUST NOT communicate directly**.
   * All communication MUST follow:

```
Signal → Intent → Parent Slot
```

Violations of this pattern are architectural defects.

---

## 3. Data Layer and Persistence Model

### 3.1 ORM and Storage

Persistence is implemented using **SQLAlchemy 2.0+**.

* **Engine**: SQLite
* **Location**: `~/.config/vociferous/vociferous.db`
* **Schema Definitions**: `src/models.py`
* **Access Layer**: `src/history_manager.py`

### 3.2 Dual-Text Invariant (Critical)

Each transcription entry contains **two distinct textual representations**:

1. **`raw_text`**

   * Immutable
   * Represents the *verbatim* Whisper output
   * MUST NEVER be edited, normalized, or overwritten

2. **`normalized_text`**

   * Mutable
   * User-visible and editable
   * May be regenerated, refined, or replaced

This separation is **foundational**. Any code that modifies `raw_text` violates system invariants.

### 3.3 Data Access Rules

* UI code MUST NOT execute raw SQL.
* Prefer `HistoryManager` methods for all CRUD operations.
* If new access patterns are required:

  * Extend `HistoryManager`
  * Do NOT bypass it from UI or controller code

### 3.4 Performance Constraints

* DTOs (e.g., `HistoryEntry`) MUST use `slots=True`.
* Assume history lists may grow large.
* Avoid eager loading unless explicitly required.

---

## 4. Core Runtime Components

### 4.1 Application Orchestrator

* Entry point: `src/main.py`
* Responsibilities:

  * Initialize subsystems
  * Wire Qt signals
  * Coordinate background state → UI state

#### Invariant 8 (Authoritative)

> **The orchestrator is the ONLY entity allowed to push background engine state (Recording, Transcribing, Idle) into the UI layer.**

Any direct UI mutation from background components is forbidden.

---

### 4.2 Background Execution and Threading

* Background inference and audio handling are managed in `src/result_thread.py`.
* All heavy work MUST occur off the main thread.

#### Threading Rules

1. Never block the Qt main thread
2. Never share mutable state across threads
3. All cross-thread communication MUST use `pyqtSignal`

Violations will result in UI instability and undefined behavior.

---

### 4.3 Input Backends

* Defined in `src/key_listener.py`
* Follow the `InputBackend` protocol

Supported backends:

* `evdev` (Wayland)
* `pynput` (X11)

Backend selection MUST remain pluggable and runtime-selectable.

---

## 5. Development Workflow and Governance

### 5.1 Changelog Discipline (Mandatory)

Every change MUST be recorded in `CHANGELOG.md`.

* Follow existing structure and tone
* Use categories:

  * `Added`
  * `Changed`
  * `Deprecated`
  * `Removed`
  * `Fixed`
  * `Security`

#### Versioning Rules

* Increment **Patch** for bug fixes
* Increment **Minor** for new features or behavioral changes
* Increment **Major** for breaking changes or invariant shifts

Versioning must reflect *impact*, not effort.

---

### 5.2 Documentation Synchronization

If code behavior, architecture, or workflows change, you MUST update:

* `README.md`
* Relevant `docs/wiki/` files

Documentation drift is treated as a **critical defect**, not a cosmetic issue.

---

### 5.3 Agent Research Journals (Required for Complex Work)

For non-trivial tasks, agents MUST create one or more Markdown files under:

```
docs/agent_resources/agent_reports/
```

These files serve as **living system intelligence**.

#### Required Contents

* System understanding and assumptions
* Identified invariants and causal chains
* Data flow and ownership reasoning
* UI intent → execution mappings
* Trade-offs considered and decisions made

Journals must be written **before or during** implementation, not retroactively.

---

### 5.4 Auto-Commit Policy

* **Safe State**

  * If all checks pass and the system is stable, you MAY commit locally.
  * Use conventional commits.
  * NEVER push.

* **Unsafe or Partial State**

  * DO NOT commit.
  * Provide a clear Post-Task Recommendation instead.

---

### 5.5 Risk Management and Branching

If a task implies:

* Architectural refactors
* Cross-cutting changes
* Invariant modifications

You MUST STOP and ask whether a new feature branch should be created before proceeding.

---

### 5.6 Definition of Done (Strict)

A task is **not complete** unless ALL of the following pass:

1. `ruff check .`
2. `mypy .`
3. `pytest`

Partial success is not success.

---

## 6. Execution Environment

### 6.1 Virtual Environment (Critical)

ALL operations MUST use the project virtual environment.

Examples:

* `.venv/bin/python`
* `.venv/bin/pip`
* `.venv/bin/ruff`

System Python is forbidden.

---

### 6.2 Running the Application

The application MUST be launched using the wrapper script:

```bash
python scripts/run.py
```

This ensures correct GPU and library configuration.

---

## 7. Language and Code Standards

### 7.1 Python 3.12+

* Mandatory type hints
* Use modern syntax:

  * `str | int`
  * `list[str]`
* Prefer `match / case` for state machines
* Use frozen, slotted dataclasses for intents and value objects

---

### 7.2 Qt and UI Standards

* Styling MUST use `src/ui/styles/unified_stylesheet.py`
* Ad-hoc `setStyleSheet()` calls are forbidden
* Long-lived objects MUST implement `cleanup()`
* Heavy imports MUST be guarded with `if TYPE_CHECKING:`

---

## 8. Developer Platform Constraints

### 8.1 Wayland

* Requires `evdev`
* User must be in the `input` group
* `QT_WAYLAND_DISABLE_WINDOWDECORATION=1` is default

### 8.2 GPU

* Managed exclusively via `scripts/run.py`

---

## 9. Configuration Management

* `src/config_schema.yaml` is the **single source of truth**
* Access configuration only via `ConfigManager`
* Never hardcode config values

---

## 10. Post-Task Requirement

Upon task completion, the agent MUST explicitly recommend whether any agent journals created during the task should be:

* Archived
* Relocated
* Removed

This recommendation must be included in the final output.