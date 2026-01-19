# Agent Report - Signaling and Runtime Stability Fixes

## System Understanding and Assumptions
The Vociferous application uses a reactive signaling system based on a `DatabaseSignalBridge` singleton. This bridge communicates changes in the database to the UI layer, specifically to models like `TranscriptionModel`.

Assumptions:
- UI models should be idempotent when receiving signals about the same entity.
- The `ApplicationCoordinator` is responsible for glueing the background engine to the UI.

## Identified Invariants and Causal Chains
- **Dual-Text Invariant**: `raw_text` is immutable, `normalized_text` is editable.
- **Signaling Chain**: `HistoryManager.add_entry` -> `DatabaseSignalBridge.emit_change` -> `TranscriptionModel.on_entity_changed` -> UI Update.
- **Startup Invariant**: The application must launch via `./vociferous` which sets up the environment and GPU correctly.

## Data Flow and Ownership Reasoning
- `HistoryManager` owns the database access.
- `TranscriptionModel` owns the memory-resident list of transcripts used by the UI.
- `ApplicationCoordinator` coordinates the flow between `EngineClient` (audio/inference), `HistoryManager` (persistence), and `MainWindow` (display).

## UI Intent -> Execution Mappings
- **Transcription Complete**: `EngineClient` emits `TranscriptionResult` -> `ApplicationCoordinator` saves to `HistoryManager` -> `MainWindow.on_transcription_complete` is called to update UI metrics and display the result.

## Trade-offs Considered and Decisions Made
- **Idempotency in Model**: Decided to add an ID-check in `TranscriptionModel.add_entry` to prevent duplicate items when both the manager and the signal bridge might trigger an update.
- **Coordination in Controller**: Explicitly called `MainWindow.on_transcription_complete` from `ApplicationCoordinator` instead of relying solely on signals to ensure immediate UI responsiveness for the "metrics" and "view load" side-effects.

## Conclusion
The application is now stable, tests are passing, and the signaling system provides a unified way to handle database changes across the application.
