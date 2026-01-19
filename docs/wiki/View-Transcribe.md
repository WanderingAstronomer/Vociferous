# View: Transcribe

The **Transcribe View** is the primary operational surface of Vociferous. It remains in focus during active dictation, recording, and immediate post-processing. It is designed as a state-driven workspace that adapts to the current phase of the transcription lifecycle.

<img src="https://raw.githubusercontent.com/WanderingAstronomer/Vociferous/main/docs/images/transcribe_view.png" alt="Transcribe View - Idle State" width="800" />

## Component Hierarchy

The view is composed of the following hierarchical components, managed by the `MainWorkspace`:

1.  **Workspace Header**: displays the current mode (Idle, Recording, Viewing) and the Message of the Day (MOTD).
2.  **Transcript Metrics**: (Hidden during recording) Displays word count, audio duration, and speech duration.
3.  **Content Panel**: The central flexible area that hosts:
    *   **Live Visualizer**: Real-time waveform and spectrum display during recording.
    *   **Transcript Editor**: A read-only or editable text surface for the resulting text.
4.  **Batch Status Footer**: Shows background processing status at the bottom of the screen.

---

## Workspace States

The view implements a strict state machine (`WorkspaceState`) that dictates UI behavior and available capabilities.

### 1. IDLE
*   **Visuals**: Grey/Neutral accents. Displays a welcome greeting or "Ready to Record" message.
*   **Behavior**: Passive. Waiting for user input.
*   **Actions**: `Start Recording` is available.

### 2. RECORDING
*   **Visuals**: **Red/Active** styling.
*   **Content**: Shows the real-time audio visualizer and live partial transcription text (if supported by the model).
*   **Actions**:
    *   `Stop Recording`: Finalizes the audio and begins transcription.
    *   `Cancel Recording`: Discards the current buffer immediately.

<img src="https://raw.githubusercontent.com/WanderingAstronomer/Vociferous/main/docs/images/transcribe_view-active_recording.png" alt="Transcribe View - Active Recording" width="800" />

### 3. TRANSCRIBING
*   **Visuals**: **Amber/Busy** styling.
*   **Content**: Displays a "Transcribing..." loading state or spinner.
*   **Actions**: Locked. User must wait for the engine to return text.

### 4. READY (Viewing)
*   **Visuals**: **Green/Success** styling.
*   **Content**: Displays the final `normalized_text` from the transcription engine.
*   **Metrics**: Visible. Shows Word Count, Total Duration, and Speech Duration.
*   **Actions**:
    *   `Copy`: Copy text to clipboard.
    *   `Edit`: Enter editing mode.
    *   `Refine`: Send text to the Refinement Engine (if enabled).
    *   `Delete`: Discard this transcript.
    *   `Start Recording`: Auto-archives current text and starts new session.

### 5. EDITING
*   **Visuals**: **Blue/Focus** styling.
*   **Content**: Text area becomes writable.
*   **Actions**:
    *   `Save`: Commit changes to `normalized_text`.
    *   `Discard`: Revert to the version before editing started.

---

## Capabilities & Interaction

The view exposes its capabilities to the main application controller via the `Capabilities` contract. These capabilities update dynamically based on the state:

| Action | IDLE | RECORDING | TRANSCRIBING | READY | EDITING |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Start** | ✅ | ❌ | ❌ | ✅ | ❌ |
| **Stop** | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Cancel** | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Copy** | ❌ | ❌ | ❌ | ✅ | ❌ |
| **Edit** | ❌ | ❌ | ❌ | ✅ | ❌ |
| **Refine** | ❌ | ❌ | ❌ | ✅ | ❌ |
| **Save** | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Discard** | ❌ | ❌ | ❌ | ❌ | ✅ |

### Visual Feedback
The `ContentPanel` uses dynamic Qt profiling to paint its background based on state properties:
*   `property="recording"`: Triggers active recording styles.
*   `property="editing"`: Triggers focus styles for text manipulation.
