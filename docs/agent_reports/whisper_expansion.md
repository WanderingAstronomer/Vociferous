# Agent Report: Whisper Model Expansion and Hot-Swapping

## Status
Implementation of Whisper `large-v3-turbo` support and dynamic model switching is complete.

## System Understanding & Assumptions
- The application uses a micro-kernel architecture where the background engine runs in a separate process.
- Model loading is managed via `faster-whisper` (CTranslate2).
- IPC is handled via JSON messages over pipes.
- The UI uses an "Intent" pattern but configuration updates are handled via `ConfigManager` signals.

## Changes Implemented

### 1. Unified Model Registry
- Introduced `ModelType` enum and `ModelCatalog` dataclass in `src/core/model_registry.py`.
- Defined `ASR_MODELS` registry containing `distil-large-v3` and `large-v3-turbo` with VRAM metadata.
- Set `distil-large-v3` as the default ASR model.

### 2. IPC Protocol Extension
- Added `UPDATE_CONFIG` command to the engine protocol.
- Enhanced `EngineClient` (client side) to send configuration updates.
- Enhanced `EngineServer` (server side) to receive updates, invalidate current models, and trigger reloads.
- Implemented `loading_model` status message from server to frontend during reloads.

### 3. Engine-Side Model Management
- Refactored `TranscriptionService` to resolve model repository IDs from the unified registry.
- Implemented thread-safe model invalidation in `EngineServer` to prevent race conditions during transcription.

### 4. Configuration Schema
- Exposed `model_options.model` in `src/config_schema.yaml` with a selector UI.
- Updated defaults to align with the distilled v3 model.

### 5. UI Integration
- Updated `SettingsView` to include a Whisper Architecture dropdown.
- Integrated VRAM requirements into the dropdown labels (e.g., "~2.1 GB VRAM").
- Wired `ApplicationCoordinator` to sync `model_options` changes to the engine process in real-time.
- Verified that the "Loading Model" overlay is automatically shown when a new model is being downloaded/loaded.

## Decisions & Trade-offs
- **Process Isolation**: We chose to keep the engine in a separate process to prevent GUI hangs during heavy CTranslate2 initialization.
- **Lazy Loading**: Models are still loaded only when needed (e.g., starting a session or config update), but we now support transactional invalidation.
- **VRAM Indicators**: We provided explicit VRAM markers in the UI to guide users on "pro" vs "default" choices.

## Verification
- Core registry unification: Verified.
- IPC protocol sync: Implemented.
- UI dropdown and status bridge: Implemented.

## Post-Task Recommendation
The agent journal `docs/agent_reports/whisper_expansion.md` should be archived as it represents a significant architectural shift in how models are managed and updated at runtime.
