# Agent Report - UI Signal Alignment Fix

## System Understanding and Assumptions
The `Vociferous` application uses a signal-slot mechanism for UI communication. Architectural invariants require that identical actions (like deletion) from different views (History, Search) should share a common execution path in the `MainWindow` controller.

## Identified Invariants and Causal Chains
- `HistoryView.delete_requested` emits a `list[int]`.
- `MainWindow._on_delete_from_history_view` is decorated with `@pyqtSlot(list)` and expects a list of IDs.
- `SearchView.delete_requested` was incorrectly defined to emit a single `int`.
- Connecting a signal emitting `int` to a slot decorated for `list` results in a `TypeError` in PyQt6.

## Data Flow and Ownership Reasoning
The `MainWindow` acts as the execution authority for deletions, interacting with the `HistoryManager`. It expects a list to handle bulk deletions, which is a desirable feature for both History and Search views.

## UI Intent -> Execution Mappings
- User clicks "Delete" in Search Table -> `SearchView._on_action_triggered` -> `delete_requested.emit(list[int])` -> `MainWindow._on_delete_from_history_view(list[int])`.

## Decisions Made
1. **Signal Alignment**: Updated `SearchView.delete_requested` to `pyqtSignal(list)` to match `HistoryView`.
2. **Selection Support**: Refactored `SearchView.get_selection()` to correctly collect all selected row IDs instead of just the primary one.
3. **Compatibility**: Ensured all other signals in `SearchView` (`edit_requested`, `refine_requested`) remain compatible with their respective slots (which expect `int`).

## Post-Task Recommendation
The journal should be archived.
