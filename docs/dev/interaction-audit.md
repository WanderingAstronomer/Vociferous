# Interaction Architecture Audit

**Date:** 2026-01-11  
**Purpose:** Baseline documentation of current interaction pathways prior to intent-driven refactor.

---

## Overview

This document enumerates all current pathways that mutate workspace state and maps implicit state transitions. It serves as the authoritative reference against which the intent-driven refactor will be measured.

---

## 1. State Definition

### WorkspaceState Enum

**Location:** `src/ui/constants/enums.py`

```python
class WorkspaceState(Enum):
    IDLE = "idle"       # No transcript selected, not recording
    RECORDING = "recording"  # Actively recording audio
    VIEWING = "viewing"      # Transcript selected, read-only
    EDITING = "editing"      # Explicit edit mode
```

### Current State Variables

| Variable | Location | Type | Description |
|----------|----------|------|-------------|
| `_state` | `MainWorkspace` | `WorkspaceState` | Primary UI state |
| `_has_unsaved_changes` | `MainWorkspace` | `bool` | Edit tracking flag |
| `_history_manager` | `MainWorkspace` | `HistoryManager` | Data source reference |

---

## 2. State Mutation Points

All locations where `WorkspaceState` is directly mutated:

### MainWorkspace (`src/ui/components/workspace/workspace.py`)

| Line | Method | Transition | Trigger |
|------|--------|------------|---------|
| 247-251 | `set_state()` | Any → Any | **Primary setter** |
| 284-286 | `load_transcript()` | → VIEWING or → IDLE | Text presence check |
| 307 | `display_new_transcript()` | → VIEWING | New entry received |
| 366 | `_on_primary_click()` | IDLE/VIEWING → RECORDING | Start button |
| 379 | `_on_primary_click()` | RECORDING → (transcribing UI) | Stop button |
| 390-395 | `_on_edit_save_click()` | VIEWING → EDITING, EDITING → VIEWING | Edit/Save button |
| 405-411 | `_on_destructive_click()` | RECORDING → IDLE, EDITING → VIEWING | Cancel/Delete button |

### MainWindow (`src/ui/components/main_window/main_window.py`)

| Line | Method | Transition | Trigger |
|------|--------|------------|---------|
| 219 | `_on_cancel_requested()` | → IDLE | Cancel recording signal |
| 261-262 | `_on_delete_requested()` | → IDLE (conditional) | Delete confirmation |
| 406 | `update_transcription_status()` | → RECORDING | Status string "recording" |
| 411 | `update_transcription_status()` | → IDLE | Status string "idle"/"error" |
| 504 | `_clear_all_history()` | → IDLE | Clear history confirmed |

### External State Access

The following methods bypass `set_state()` by calling `load_transcript()` which internally sets state:

| Caller | Method | Effect |
|--------|--------|--------|
| `MainWindow._on_entry_selected()` | `workspace.load_transcript(text, timestamp)` | Sidebar → VIEWING |
| `VociferousApp` (main.py) | `main_window.workspace.display_new_transcript(entry)` | Transcription complete → VIEWING |

---

## 3. Signal-Slot Wiring

### WorkspaceControls → MainWorkspace

**Location:** `src/ui/components/workspace/controls.py` (lines 34-37)

| Signal | Type | Connected To |
|--------|------|--------------|
| `primaryClicked` | `pyqtSignal()` | `workspace._on_primary_click` |
| `editSaveClicked` | `pyqtSignal()` | `workspace._on_edit_save_click` |
| `destructiveClicked` | `pyqtSignal()` | `workspace._on_destructive_click` |
| `refineClicked` | `pyqtSignal()` | `workspace.refineRequested.emit` |

**Wiring Location:** `workspace.py` lines 174-178

```python
self.controls.primaryClicked.connect(self._on_primary_click)
self.controls.editSaveClicked.connect(self._on_edit_save_click)
self.controls.destructiveClicked.connect(self._on_destructive_click)
self.controls.refineClicked.connect(self.refineRequested.emit)
```

### WorkspaceContent → MainWorkspace

**Location:** `src/ui/components/workspace/content.py` (lines 54-57)

| Signal | Type | Connected To |
|--------|------|--------------|
| `textChanged` | `pyqtSignal()` | `workspace._on_text_changed` |
| `editRequested` | `pyqtSignal()` | `workspace._on_edit_save_click` |
| `deleteRequested` | `pyqtSignal()` | `workspace._on_destructive_click` |

**Wiring Location:** `workspace.py` lines 179-181

```python
self.content.textChanged.connect(self._on_text_changed)
self.content.editRequested.connect(self._on_edit_save_click)
self.content.deleteRequested.connect(self._on_destructive_click)
```

### MainWorkspace → MainWindow

**Location:** `src/ui/components/workspace/workspace.py` (lines 58-64)

| Signal | Type | Handler |
|--------|------|---------|
| `startRequested` | `pyqtSignal()` | `main_window._on_start_requested` |
| `stopRequested` | `pyqtSignal()` | `main_window._on_stop_requested` |
| `cancelRequested` | `pyqtSignal()` | `main_window._on_cancel_requested` |
| `saveRequested` | `pyqtSignal(str)` | `main_window._on_save_requested` |
| `deleteRequested` | `pyqtSignal()` | `main_window._on_delete_requested` |

**Wiring Location:** `main_window.py` lines 160-165

```python
self.workspace.startRequested.connect(self._on_start_requested)
self.workspace.stopRequested.connect(self._on_stop_requested)
self.workspace.cancelRequested.connect(self._on_cancel_requested)
self.workspace.saveRequested.connect(self._on_save_requested)
self.workspace.deleteRequested.connect(self._on_delete_requested)
```

### Sidebar → MainWindow → MainWorkspace

**Location:** `src/ui/components/sidebar/sidebar_new.py` (lines 55-58)

| Signal | Type | Handler |
|--------|------|---------|
| `entrySelected` | `pyqtSignal(str, str)` | `main_window._on_entry_selected` |

**Wiring Location:** `main_window.py` line 130

```python
self.sidebar.entrySelected.connect(self._on_entry_selected)
```

**Handler Effect:** `main_window.py` lines 272-280

```python
@pyqtSlot(str, str)
def _on_entry_selected(self, text: str, timestamp: str) -> None:
    try:
        self.workspace.load_transcript(text, timestamp)  # ← Direct state mutation
    except Exception as e:
        logger.exception("Error loading transcript")
        show_error_dialog(...)
```

---

## 4. State Transition Flows

### Flow 1: Start Recording (Button)

```
User clicks "Start" button
  → WorkspaceControls.primaryClicked.emit()
  → MainWorkspace._on_primary_click()
    → match self._state:
        case IDLE | VIEWING:
          → self.set_state(WorkspaceState.RECORDING)  ← STATE CHANGE
          → self.startRequested.emit()
  → MainWindow._on_start_requested()
    → self.startRecordingRequested.emit()
  → VociferousApp.start_result_thread()
```

### Flow 2: Stop Recording (Button)

```
User clicks "Stop" button
  → WorkspaceControls.primaryClicked.emit()
  → MainWorkspace._on_primary_click()
    → match self._state:
        case RECORDING:
          → self.show_transcribing_status()  ← UI update only
          → self.stopRequested.emit()
  → MainWindow._on_stop_requested()
    → self.stopRecordingRequested.emit()
  → VociferousApp._stop_recording_from_ui()
  → (async transcription)
  → VociferousApp.on_transcription_complete()
    → main_window.workspace.display_new_transcript(entry)
      → self.set_state(WorkspaceState.VIEWING)  ← STATE CHANGE
```

### Flow 3: Sidebar Selection

```
User clicks transcript in sidebar
  → SidebarWidget._on_entry_selected()
    → self.entrySelected.emit(text, timestamp)
  → MainWindow._on_entry_selected()
    → self.workspace.load_transcript(text, timestamp)  ← BYPASSES VALIDATION
      → if text:
          self.set_state(WorkspaceState.VIEWING)  ← STATE CHANGE
        else:
          self.set_state(WorkspaceState.IDLE)  ← STATE CHANGE
```

**⚠️ ISSUE:** No validation for:
- Current state (can select while recording)
- Unsaved edits (no prompt)
- Concurrent transcription

### Flow 4: Edit Transcript

```
User clicks "Edit" button
  → WorkspaceControls.editSaveClicked.emit()
  → MainWorkspace._on_edit_save_click()
    → match self._state:
        case VIEWING:
          → self.set_state(WorkspaceState.EDITING)  ← STATE CHANGE
```

### Flow 5: Save Edited Transcript

```
User clicks "Save" button
  → WorkspaceControls.editSaveClicked.emit()
  → MainWorkspace._on_edit_save_click()
    → match self._state:
        case EDITING:
          → edited_text = self.content.get_text()
          → self.content.set_transcript(edited_text, timestamp)
          → self._has_unsaved_changes = False
          → self.saveRequested.emit(edited_text)  ← STATE CHANGE pending
          → self.set_state(WorkspaceState.VIEWING)  ← STATE CHANGE
  → MainWindow._on_save_requested()
    → self.history_manager.update_entry(timestamp, text)
    → self.sidebar.load_history()
```

### Flow 6: Cancel Edit / Cancel Recording

```
User clicks "Cancel" button (during editing)
  → WorkspaceControls.destructiveClicked.emit()
  → MainWorkspace._on_destructive_click()
    → match self._state:
        case EDITING:
          → self._has_unsaved_changes = False
          → self.set_state(WorkspaceState.VIEWING)  ← STATE CHANGE

User clicks "Cancel" button (during recording)
  → MainWorkspace._on_destructive_click()
    → match self._state:
        case RECORDING:
          → self.cancelRequested.emit()
          → self.set_state(WorkspaceState.IDLE)  ← STATE CHANGE
```

### Flow 7: Delete Transcript

```
User clicks "Delete" button
  → WorkspaceControls.destructiveClicked.emit()
  → MainWorkspace._on_destructive_click()
    → match self._state:
        case VIEWING:
          → self.deleteRequested.emit()
  → MainWindow._on_delete_requested()
    → ConfirmationDialog.exec()
    → if confirmed:
        → self.history_manager.delete_entry(timestamp)
        → self.sidebar.load_history()
        → self.workspace.set_state(WorkspaceState.IDLE)  ← STATE CHANGE (external)
```

**⚠️ ISSUE:** `MainWindow` directly calls `workspace.set_state()`, bypassing workspace control.

---

## 5. Identified Authority Violations

### 5.1 Sidebar Selection Bypasses Validation

**Location:** `main_window.py` line 275

```python
self.workspace.load_transcript(text, timestamp)
```

**Problem:** No check for:
- `_state == RECORDING` (should reject or defer)
- `_state == EDITING and _has_unsaved_changes` (should prompt)

### 5.2 MainWindow Mutates Workspace State Directly

**Locations:**
- `main_window.py` line 219: `self.workspace.set_state(WorkspaceState.IDLE)` (cancel)
- `main_window.py` line 261-262: `self.workspace.set_state(WorkspaceState.IDLE)` (delete)
- `main_window.py` line 406: `self.workspace.set_state(WorkspaceState.RECORDING)` (status update)
- `main_window.py` line 411: `self.workspace.set_state(WorkspaceState.IDLE)` (status update)
- `main_window.py` line 504: `self.workspace.set_state(WorkspaceState.IDLE)` (clear history)

**Problem:** State authority is split between `MainWorkspace` and `MainWindow`.

### 5.3 Multiple Edit Entry Points

Edit mode can be entered via:
1. `WorkspaceControls.editSaveClicked` → `_on_edit_save_click()`
2. `WorkspaceContent.editRequested` → `_on_edit_save_click()` (context menu)

**Problem:** Same handler, but no unified validation point.

### 5.4 Delete Entry Points

Delete can be triggered via:
1. `WorkspaceControls.destructiveClicked` → `_on_destructive_click()` → `deleteRequested.emit()`
2. `WorkspaceContent.deleteRequested` → `_on_destructive_click()` → `deleteRequested.emit()`

**Problem:** Actual deletion happens in `MainWindow`, state change also in `MainWindow`.

---

## 6. Files and Symbols Inventory

### Core State Management

| File | Symbol | Role |
|------|--------|------|
| `src/ui/constants/enums.py` | `WorkspaceState` | State enum |
| `src/ui/components/workspace/workspace.py` | `MainWorkspace` | State owner |
| `src/ui/components/workspace/workspace.py` | `set_state()` | Primary setter |
| `src/ui/components/workspace/workspace.py` | `_update_for_state()` | UI synchronization |

### Signal Emitters

| File | Symbol | Signals |
|------|--------|---------|
| `src/ui/components/workspace/controls.py` | `WorkspaceControls` | `primaryClicked`, `editSaveClicked`, `destructiveClicked`, `refineClicked` |
| `src/ui/components/workspace/content.py` | `WorkspaceContent` | `textChanged`, `editRequested`, `deleteRequested` |
| `src/ui/components/sidebar/sidebar_new.py` | `SidebarWidget` | `entrySelected` |

### Signal Handlers

| File | Symbol | Handles |
|------|--------|---------|
| `src/ui/components/workspace/workspace.py` | `_on_primary_click()` | Start/Stop |
| `src/ui/components/workspace/workspace.py` | `_on_edit_save_click()` | Edit/Save |
| `src/ui/components/workspace/workspace.py` | `_on_destructive_click()` | Cancel/Delete |
| `src/ui/components/main_window/main_window.py` | `_on_entry_selected()` | Sidebar selection |
| `src/ui/components/main_window/main_window.py` | `_on_delete_requested()` | Delete confirmation |

---

## 7. Refactor Targets

### Phase 2: Abstraction Introduction

1. Create `src/ui/interaction/intents.py` with intent dataclasses
2. Create `src/ui/interaction/results.py` with `IntentOutcome`, `IntentResult`
3. Add `handle_intent()` bridge in `MainWorkspace`

### Phase 3: Centralize State Mutation

1. Migrate `_on_primary_click()` → `BeginRecordingIntent` / `StopRecordingIntent`
2. Migrate `_on_edit_save_click()` → `EditTranscriptIntent` / `CommitEditsIntent`
3. Migrate `_on_destructive_click()` → `DiscardEditsIntent` / `DeleteTranscriptIntent`

### Phase 4: Sidebar Intent Migration

1. Replace `entrySelected` signal with `ViewTranscriptIntent` emission
2. Route through `workspace.handle_intent()` instead of `load_transcript()`
3. Add validation for recording/editing conflicts

### Audit Rule (Post-Phase 3)

```bash
# Should return 0 matches after Phase 3 (excluding handle_intent internals)
grep -rn "set_state(" src/ui/components/main_window/
```

---

## Appendix: Current Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              VociferousApp (main.py)                        │
│                                                                             │
│  ┌─────────────────┐    signals    ┌──────────────────────────────────────┐│
│  │  ResultThread   │──────────────▶│           MainWindow                 ││
│  │  (audio/whisper)│               │                                      ││
│  └─────────────────┘               │  ┌──────────┐   ┌────────────────┐  ││
│                                    │  │ Sidebar  │──▶│ MainWorkspace  │  ││
│                                    │  │          │   │                │  ││
│                                    │  │ entrySelected │  _state       │  ││
│                                    │  │          │   │  set_state()   │  ││
│                                    │  └──────────┘   │  _on_*_click() │  ││
│                                    │       ▲         │       ▲         │  ││
│                                    │       │         └───────┼─────────┘  ││
│                                    │       │                 │            ││
│                                    │       │         ┌───────┴─────────┐  ││
│                                    │       │         │ WorkspaceControls│ ││
│                                    │       │         │ primaryClicked  │  ││
│                                    │       │         │ editSaveClicked │  ││
│                                    │       │         └─────────────────┘  ││
│                                    └──────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘

Legend:
  ──▶  Signal connection
  ───  Direct method call
  [!]  Authority violation (state mutated outside MainWorkspace)
```

---

*This document is the authoritative baseline for the intent-driven interaction refactor.*
