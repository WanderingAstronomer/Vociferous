# Vociferous — Copilot & VS Code AI Instructions

## 0. Scope and Intent

This file defines **authoritative, binding instructions** for GitHub Copilot, VS Code AI agents, and any autonomous or semi‑autonomous coding assistants operating in this repository.

These instructions exist to:

* Preserve long‑term architectural integrity
* Reduce cognitive and procedural friction for a **solo maintainer**
* Prevent AI‑introduced process ceremony
* Encode project invariants and design intent explicitly

All guidance in this file is **normative**, not advisory. If a conflict exists between AI defaults and this document, **this document takes precedence**.

---

## 1. Project Context (Always Read First)

**Vociferous** is a production‑quality, Linux‑native speech‑to‑text application written in **Python 3.12+**.

Core characteristics:

* Desktop GUI built with **PyQt6**
* Offline‑capable transcription using **Whisper / faster‑whisper**
* **Process-based Architecture**: Transcription runs in a dedicated subprocess (`core_runtime`) to ensure UI responsiveness.
* **Component-based Design**: Orchestrated by an `ApplicationCoordinator`.
* **Command Bus**: Centralized intent dispatch system.
* **Small Language Model (SLM)** integration for text refinement.

The project is actively developed and maintained by a **single primary developer**. All workflow rules are calibrated accordingly.

---

## 2. Architectural Invariants (Non‑Negotiable)

### 2.1 Composition Root

* `src/main.py` is a thin entry point only.
* **`src/core/application_coordinator.py`** is the true Composition Root. It owns the lifecycle of services, UI, and the runtime.
* New global services MUST be initialized in `ApplicationCoordinator`.

### 2.2 Intent-Driven Interaction

* **All** user actions that affect application state MUST be encapsulated as an `InteractionIntent`.
* Intents are dispatched via the **`CommandBus`** (`src/core/command_bus.py`).
* Widgets should NOT call service methods directly. They should dispatch intents.
* Intents are defined in `src/ui/interaction/intents.py`.

### 2.3 Process & Threading Model

* **Transcription Engine**: Runs in a separate process (`src/core_runtime/server.py`).
    * Communication is via IPC (`EngineClient` -> `PacketTransport`).
    * NEVER block the UI thread with model inference.
* **Background Services**: Other heavy tasks (like SLM) run in `QThread` wrappers (e.g., `SLMService`).
* The UI thread (`MainWindow`) handles ONLY presentation logic.

### 2.4 Persistence Model

* Access via **`HistoryManager`** (`src/database/history_manager.py`).
* **Immutability**: The original raw transcription is immutable.
* **Variants**: Edits, refinements, and formatted versions are stored as **variants** linked to the original transcript ID. Do not overwrite the original capture.

---

## 3. Repository Structure (Semantic and Binding)

The `src/` layout is intentional:

* `core/` — Application plumbing (Coordinator, CommandBus, Config, State).
* `core_runtime/` — Isolated process for the Transcription Engine (IPC server).
* `database/` — Persistence layer (Repositories, HistoryManager).
* `services/` — Business logic and background workers (SLM, Audio).
* `ui/` — PyQt6 views, widgets, and interaction logic.
    * `interaction/` — Intent definitions.
* `input_handler/` — Global hotkey and input listening.
* `provisioning/` — Model download and management tools.
* `refinement/` — Text processing engines.

Do not introduce new top‑level directories without explicit approval.

---

## 4. Coding Standards

### 4.1 Python

* Python **3.12+** only.
* **Strict Type Hints**: Every function signature must be typed.
* Prefer `dataclasses` (frozen, slotted) for value objects.
* Use `logging` (via `src.core.log_manager` or standard `logging.getLogger`).

### 4.2 Qt / UI

* Styling MUST go through `src/ui/styles/unified_stylesheet.py`.
* Avoid inline `setStyleSheet()`.
* **Signals/Slots**: Use `pyqtSignal` for cross-component communication if not using Intents.

---

## 5. Workflow Model (Solo Maintainer, Production Quality)

### 5.1 Core Principle

Process exists to **reduce risk and cognitive load**, not to simulate team workflows.
AI agents MUST NOT introduce ceremony unless it provides clear functional benefit.

### 5.2 Issues & Branches

* **Issues**: Optional. Only for complex, multi-session tracking.
* **Branches**:
    * Direct commits to `main` are ALLOWED for localized, low-risk changes.
    * Branches are REQUIRED for architectural refactors or high-risk features.

### 5.3 Commits

* Small, descriptive commits.
* Explain the *why*.

### 5.4 Anti‑Ceremony Rule (Explicit)

AI agents MUST NOT:
* Create branches, issues, or PRs "for best practice" without specific cause.
* Optimize for activity metrics.
* Suggest CI/CD complexity that requires maintenance.

---

## 6. Execution Environment

* Use the project virtual environment.
* Run the app via `./vociferous` (which wraps `src/main.py`).
* Ensure `requirements.txt` is respected.

---

## 7. Final Rule

When in doubt:

**Favor clarity, reversibility, and architectural integrity over ceremony.**
