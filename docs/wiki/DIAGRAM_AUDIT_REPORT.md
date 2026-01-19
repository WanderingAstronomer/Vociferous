# Diagram Audit Report

**Date:** 2026-01-19  
**Scope:** All wiki `.md` files in `docs/wiki/`  
**Purpose:** Identify diagrams suitable for Mermaid conversion with repository-backed trace points

---

## Audit Methodology

This audit examined:
1. **ASCII code blocks** — Fenced blocks with box-drawing characters
2. **Existing Mermaid blocks** — Syntax and semantic accuracy
3. **Prose flows** — Stepwise descriptions without diagrams

---

## Audit Results

| Page | Section | Current Form | Proposed Mermaid Type | Convert? | Rationale | Evidence Trace Points |
|------|---------|--------------|----------------------|----------|-----------|----------------------|
| Architecture.md | Layered Architecture | ASCII code block | **block** (block diagram) | **Yes** | The ASCII diagram shows structural containment of components across layers. This maps precisely to Mermaid's `block` diagram which allows explicit positioning and nested subgraphs. The `flowchart` with subgraphs is also viable. | • `src/core/application_coordinator.py:62` — `ApplicationCoordinator`<br>• `src/services/slm_service.py:44` — `SLMService`<br>• `src/core_runtime/client.py:22` — `EngineClient`<br>• `src/core_runtime/engine.py` — `TranscriptionEngine`<br>• `src/database/history_manager.py` — `HistoryManager`<br>• `src/ui/components/main_window/main_window.py:87` — `MainWindow` |
| Architecture.md | MainWindow Layout | ASCII code block | **None** | **No** | This is a pixel-geometry UI layout (MainWindow → IconRail, ViewHost, ActionDock). While the containment is traceable, converting to a structural diagram would be redundant with the layered architecture diagram above. The ASCII representation clearly conveys spatial arrangement which Mermaid diagrams cannot replicate. | N/A — Layout-only |
| Architecture.md | Engine Communication | Existing Mermaid | **None (Keep)** | **No** | The existing `sequenceDiagram` is syntactically valid and semantically accurate. Actors map to real classes. | • `src/ui/components/main_window/main_window.py` — `MainWindow`<br>• `src/core/application_coordinator.py` — Coordinator<br>• `src/core_runtime/client.py` — `EngineClient`<br>• `src/core_runtime/server.py` — `EngineServer`<br>• `src/core_runtime/engine.py` — `TranscriptionEngine` |
| Architecture.md | State Machine | Existing Mermaid | **None (Keep)** | **No** | Valid `stateDiagram-v2`. States match engine states in codebase. | • `src/core_runtime/client.py` — Engine states |
| Architecture.md | Navigation | Existing Mermaid | **None (Keep)** | **No** | Valid `flowchart LR`. Nodes match actual view classes. | • `src/ui/views/*.py` — View classes |
| Architecture.md | Signal-Based Comm. | Existing Mermaid | **None (Keep)** | **No** | Valid `sequenceDiagram`. Correctly shows Qt signal pattern. | • Qt signal/slot pattern throughout |
| UI-Views-Overview.md | MainWindow Layout | ASCII code block | **None** | **No** | Same as Architecture.md — pixel-geometry layout representation. ASCII is more appropriate for spatial arrangement. | N/A — Layout-only |
| UI-Views-Overview.md | Capabilities Flow | Existing Mermaid | **None (Keep)** | **No** | Valid `sequenceDiagram`. | • `src/ui/contracts/capabilities.py` |
| UI-Views-Overview.md | Navigation Flow | Existing Mermaid | **None (Keep)** | **No** | Valid `flowchart TB`. | • `src/ui/components/main_window/view_host.py` |
| Refinement-System.md | System Architecture | ASCII code block | **flowchart TB** | **Yes** | The ASCII shows vertical component stack. Can be converted to a flowchart with subgraphs for clearer component relationships. | • `src/core/application_coordinator.py` — Coordinator<br>• `src/services/slm_service.py:44` — `SLMService`<br>• `src/refinement/engine.py` — `RefinementEngine`<br>• Model registry constants in `src/core/` |
| Refinement-System.md | State Diagram | Existing Mermaid | **Refine** | **Yes** | Syntactically valid but transitions are incomplete. Missing some transitions evidenced in `SLMService`. Should add `ERROR --> DISABLED` recovery path and refine transition labels. | • `src/services/slm_service.py:44-57` — `SLMState` enum |
| Refinement-System.md | Provisioning Flow | Existing Mermaid | **None (Keep)** | **No** | Valid and accurate `sequenceDiagram`. | • `src/services/slm_service.py` — `ProvisioningWorker` |
| Refinement-System.md | MOTD Flow | Existing Mermaid | **None (Keep)** | **No** | Valid `sequenceDiagram`. | • `src/services/slm_service.py` — MOTD generation |
| Data-and-Persistence.md | ER Diagram | Existing Mermaid | **None (Keep)** | **No** | Valid `erDiagram`. Matches ORM models. | • `src/database/models.py` — `Transcript`, `Project`, `TranscriptVariant` |
| Data-and-Persistence.md | Create Transcript | Existing Mermaid | **None (Keep)** | **No** | Valid `sequenceDiagram`. | • `src/database/history_manager.py` |
| View-Transcribe.md | Layout | ASCII code block | **None** | **No** | UI layout representation — not structural containment. Appropriate as ASCII. | N/A — Layout-only |
| View-Transcribe.md | State Diagram | Existing Mermaid | **Refine** | **Yes** | Valid but states don't exactly match `WorkspaceState` enum. Needs alignment with actual enum values. | • `src/ui/constants/enums.py:10` — `WorkspaceState` |
| View-Transcribe.md | Audio Data Flow | Existing Mermaid | **None (Keep)** | **No** | Valid `sequenceDiagram`. | • Audio visualization flow |
| View-History.md | Layout | ASCII code block | **None** | **No** | Master-detail layout — pixel geometry. | N/A — Layout-only |
| View-History.md | Model Stack | Existing Mermaid | **None (Keep)** | **No** | Valid `flowchart TB`. | • `src/database/history_manager.py`<br>• View models |
| View-History.md | Change Handling | Existing Mermaid | **None (Keep)** | **No** | Valid `sequenceDiagram`. | • `src/database/signal_bridge.py` |
| View-Search.md | Layout | ASCII code block | **None** | **No** | Table layout — pixel geometry. | N/A — Layout-only |
| View-Search.md | Model Stack | Existing Mermaid | **None (Keep)** | **No** | Valid `flowchart TB`. | • Search proxy model |
| View-Refine.md | Layout | ASCII code block | **None** | **No** | Side-by-side panel layout — pixel geometry. | N/A — Layout-only |
| View-Refine.md | Entry/Accept/Re-Run | Existing Mermaid | **None (Keep)** | **No** | Valid `sequenceDiagram` instances. | • `src/ui/views/refine_view.py` |
| View-Settings.md | Layout | ASCII code block | **None** | **No** | Settings form layout — pixel geometry. | N/A — Layout-only |
| View-Settings.md | Persistence Flows | Existing Mermaid | **None (Keep)** | **No** | Valid `sequenceDiagram`. | • `src/core/config_manager.py` |
| View-User.md | Layout | ASCII code block | **None** | **No** | Cards layout — pixel geometry. | N/A — Layout-only |
| View-User.md | Statistics Calc. | Existing Mermaid | **None (Keep)** | **No** | Valid `sequenceDiagram`. | • `src/database/history_manager.py` |
| Design-System.md | — | Tables only | **None** | **No** | No diagrams present. Color/spacing tokens are best expressed as tables. | N/A |
| Getting-Started.md | — | No diagrams | **None** | **No** | Installation steps as prose/commands. No structural flows to diagram. | N/A |
| Testing-Philosophy.md | — | No diagrams | **None** | **No** | Test organization as prose/tables. No flows requiring diagrams. | N/A |
| Home.md | — | Images only | **None** | **No** | Landing page with screenshots. No structural diagrams needed. | N/A |

---

## Conversion Summary

### Items to Convert (3)

| Item | Page | Current | Target | Priority |
|------|------|---------|--------|----------|
| 1 | Architecture.md | ASCII layered architecture | `flowchart TB` with subgraphs | High |
| 2 | Refinement-System.md | ASCII component stack | `flowchart TB` | Medium |
| 3 | Refinement-System.md | Existing stateDiagram-v2 | Refined `stateDiagram-v2` | Medium |

### Items to Refine (1)

| Item | Page | Issue | Fix |
|------|------|-------|-----|
| 1 | View-Transcribe.md | State names don't match `WorkspaceState` enum exactly | Align state names with enum values |

### Items to Keep As-Is (20+)

All existing Mermaid diagrams are syntactically valid and semantically accurate. ASCII layout diagrams appropriately represent spatial UI arrangements.

---

## Conversion Decisions Not Made

The following were considered but rejected:

1. **MainWindow Layout diagrams** — These show pixel-relative positioning (IconRail left, ViewHost center, ActionDock right). Mermaid cannot express spatial arrangement semantics. Keeping as ASCII preserves intent.

2. **View Layout diagrams** (all views) — Same rationale. These are UI mockups, not architectural diagrams.

3. **Settings form layout** — Form field organization is better shown as ASCII boxes than as a flowchart which would imply flow/dependency.

---

## Evidence Verification

All trace points were verified against the repository:

- `src/core/application_coordinator.py:62` ✓
- `src/services/slm_service.py:44` ✓
- `src/ui/constants/enums.py:10` ✓
- `src/core_runtime/client.py:22` ✓
- `src/ui/components/main_window/main_window.py:87` ✓
- `src/refinement/engine.py` ✓
- `src/database/models.py` ✓
- `src/database/history_manager.py` ✓

---

## Next Step

Proceed to **Deliverable 2: Mermaid Conversion Patch** for the 4 identified items.
