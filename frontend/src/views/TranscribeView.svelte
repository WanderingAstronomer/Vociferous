<script lang="ts">
    /**
     * TranscribeView — State-driven transcription workspace.
     *
     * States (matching old PyQt6 WorkspaceState):
     *   IDLE         — Welcome greeting, ready to record
     *   RECORDING    — Active recording with spectrum visualizer
     *   TRANSCRIBING — Processing audio, spinner shown
     *   READY        — Fresh transcript just arrived
     *   VIEWING      — Viewing a transcript
     *   EDITING      — Editing transcript text
     */

    import { ws } from "../lib/ws";
    import { onMount } from "svelte";
    import {
        Mic,
        Square,
        Copy,
        Check,
        Pencil,
        Trash2,
        Save,
        Undo2,
        Loader2,
    } from "lucide-svelte";
    import WorkspacePanel from "../lib/components/WorkspacePanel.svelte";
    import BarSpectrumVisualizer from "../lib/components/BarSpectrumVisualizer.svelte";

    type WorkspaceState =
        | "idle"
        | "recording"
        | "transcribing"
        | "ready"
        | "viewing"
        | "editing";

    let viewState = $state<WorkspaceState>("idle");
    let transcriptText = $state("");
    let editText = $state("");
    let transcriptId = $state<number | null>(null);
    let transcriptTimestamp = $state("");
    let durationMs = $state(0);
    let speechDurationMs = $state(0);
    let copied = $state(false);

    let visualizerRef: BarSpectrumVisualizer | undefined = $state();

    /* ===== Derived state ===== */
    let wordCount = $derived(
        viewState === "recording" || viewState === "transcribing" || viewState === "editing" || viewState === "viewing"
            ? (viewState === "editing" ? editText : transcriptText).split(/\s+/).filter(Boolean).length
            : 0
    );
    let isRecording = $derived(viewState === "recording");
    let isTranscribing = $derived(viewState === "transcribing");
    let hasText = $derived(
        Boolean(transcriptText) && viewState !== "idle"
    );

    /* ===== Greeting ===== */
    let greeting = $derived.by(() => {
        const hour = new Date().getHours();
        if (hour < 12) return "Good morning";
        if (hour < 17) return "Good afternoon";
        return "Good evening";
    });

    /* ===== Metrics formatting ===== */
    function formatDuration(ms: number): string {
        if (ms <= 0) return "—";
        const secs = Math.round(ms / 1000);
        const m = Math.floor(secs / 60);
        const s = secs % 60;
        return m > 0 ? `${m}m ${s}s` : `${s}s`;
    }

    function formatWpm(words: number, ms: number): string {
        if (ms <= 0 || words <= 0) return "—";
        const minutes = ms / 60000;
        return `${Math.round(words / minutes)} wpm`;
    }

    /* ===== WebSocket handlers ===== */
    onMount(() => {
        const unsubs = [
            ws.on("recording_started", () => {
                viewState = "recording";
                transcriptText = "";
                transcriptId = null;
                transcriptTimestamp = "";
                durationMs = 0;
                speechDurationMs = 0;
            }),
            ws.on("recording_stopped", (data) => {
                visualizerRef?.reset();
                if (data.cancelled) {
                    viewState = "idle";
                } else {
                    viewState = "transcribing";
                }
            }),
            ws.on("transcription_complete", (data) => {
                transcriptText = data.text;
                transcriptId = data.id;
                durationMs = data.duration_ms ?? 0;
                speechDurationMs = data.speech_duration_ms ?? 0;
                viewState = "ready";
            }),
            ws.on("transcription_error", (data) => {
                transcriptText = `Error: ${data.message}`;
                viewState = "ready";
            }),
            ws.on("audio_spectrum", (data) => {
                if (viewState === "recording" && visualizerRef) {
                    visualizerRef.addSpectrum(data.bands);
                }
            }),
        ];
        return () => unsubs.forEach((fn) => fn());
    });

    /* ===== Actions ===== */
    function startRecording() {
        ws.send("start_recording");
    }

    function stopRecording() {
        ws.send("stop_recording");
    }

    function toggleRecording() {
        if (isRecording) stopRecording();
        else startRecording();
    }

    function copyToClipboard() {
        const text = viewState === "editing" ? editText : transcriptText;
        if (text) {
            navigator.clipboard.writeText(text);
            copied = true;
            setTimeout(() => (copied = false), 1500);
        }
    }

    function enterEditMode() {
        if (!hasText || isRecording || isTranscribing) return;
        editText = transcriptText;
        viewState = "editing";
    }

    function commitEdits() {
        transcriptText = editText;
        viewState = "viewing";
        // TODO: send save to backend
    }

    function discardEdits() {
        editText = "";
        viewState = "viewing";
    }

    function deleteTranscript() {
        if (transcriptId != null) {
            // TODO: confirm dialog, then API call
            transcriptText = "";
            transcriptId = null;
            viewState = "idle";
        }
    }

    function resetToIdle() {
        if (viewState === "ready" || viewState === "viewing") {
            viewState = "idle";
            transcriptText = "";
            transcriptId = null;
        }
    }
</script>

<div class="transcribe-view">
    <!-- Header -->
    <div class="workspace-header">
        {#if viewState === "idle"}
            <h1 class="header-greeting">{greeting}</h1>
            <p class="header-subtitle">Press the mic or use your hotkey to begin</p>
        {:else if viewState === "recording"}
            <div class="header-status recording-status">
                <span class="recording-dot"></span>
                <span>Recording</span>
            </div>
        {:else if viewState === "transcribing"}
            <div class="header-status">
                <Loader2 size={18} class="spin" />
                <span>Transcribing…</span>
            </div>
        {:else}
            <div class="header-status">
                <span class="header-timestamp">{transcriptTimestamp || "Transcript"}</span>
            </div>
        {/if}
    </div>

    <!-- Metrics strip (visible when transcript loaded) -->
    {#if hasText && durationMs > 0}
        <div class="metrics-strip">
            <div class="metric">
                <span class="metric-label">Duration</span>
                <span class="metric-value">{formatDuration(durationMs)}</span>
            </div>
            <div class="metric-divider"></div>
            <div class="metric">
                <span class="metric-label">Speech</span>
                <span class="metric-value">{formatDuration(speechDurationMs)}</span>
            </div>
            <div class="metric-divider"></div>
            <div class="metric">
                <span class="metric-label">Words</span>
                <span class="metric-value">{wordCount}</span>
            </div>
            <div class="metric-divider"></div>
            <div class="metric">
                <span class="metric-label">Pace</span>
                <span class="metric-value">{formatWpm(wordCount, speechDurationMs || durationMs)}</span>
            </div>
        </div>
    {/if}

    <!-- Content panel -->
    <WorkspacePanel editing={viewState === "editing"} recording={isRecording || isTranscribing}>
        <!-- IDLE: centered record prompt -->
        {#if viewState === "idle"}
            <div class="content-center">
                <button class="record-button" onclick={startRecording} title="Start recording">
                    <Mic size={32} strokeWidth={1.5} />
                </button>
                <p class="record-hint">Tap to record</p>
            </div>

        <!-- RECORDING: visualizer + stop -->
        {:else if viewState === "recording"}
            <div class="content-recording">
                <div class="visualizer-container">
                    <BarSpectrumVisualizer
                        bind:this={visualizerRef}
                        active={isRecording}
                        numBars={64}
                    />
                </div>
                <button class="stop-button" onclick={stopRecording} title="Stop recording">
                    <Square size={20} fill="currentColor" />
                </button>
            </div>

        <!-- TRANSCRIBING: spinner -->
        {:else if viewState === "transcribing"}
            <div class="content-center">
                <Loader2 size={40} strokeWidth={1.5} class="spin" />
                <p class="transcribing-text">Processing audio…</p>
            </div>

        <!-- EDITING: editable textarea -->
        {:else if viewState === "editing"}
            <div class="content-text">
                <textarea
                    class="edit-area"
                    bind:value={editText}
                    spellcheck="true"
                ></textarea>
            </div>

        <!-- READY / VIEWING: display transcript text -->
        {:else}
            <div class="content-text">
                <p class="transcript-display">{transcriptText}</p>
            </div>
        {/if}
    </WorkspacePanel>

    <!-- Action bar (below panel) -->
    {#if viewState !== "idle" && viewState !== "transcribing"}
        <div class="action-bar">
            {#if viewState === "recording"}
                <!-- Recording: just the stop is in the panel -->
            {:else if viewState === "editing"}
                <button class="action-btn primary" onclick={commitEdits} title="Save edits">
                    <Save size={16} /> Save
                </button>
                <button class="action-btn ghost" onclick={discardEdits} title="Discard edits">
                    <Undo2 size={16} /> Discard
                </button>
            {:else}
                <!-- READY / VIEWING -->
                <button class="action-btn secondary" onclick={copyToClipboard} title="Copy to clipboard">
                    {#if copied}
                        <Check size={16} /> Copied
                    {:else}
                        <Copy size={16} /> Copy
                    {/if}
                </button>
                <button class="action-btn ghost" onclick={enterEditMode} title="Edit transcript">
                    <Pencil size={16} /> Edit
                </button>
                <button class="action-btn destructive" onclick={deleteTranscript} title="Delete transcript">
                    <Trash2 size={16} /> Delete
                </button>

                <div class="action-spacer"></div>

                <button class="action-btn ghost" onclick={resetToIdle} title="New recording">
                    <Mic size={16} /> New
                </button>
            {/if}
        </div>
    {/if}
</div>

<style>
    .transcribe-view {
        display: flex;
        flex-direction: column;
        height: 100%;
        padding: var(--space-4);
        gap: var(--minor-gap);
        max-width: var(--content-max-width);
        margin: 0 auto;
    }

    /* ===== Header ===== */

    .workspace-header {
        flex-shrink: 0;
        padding: var(--space-1) 0;
    }

    .header-greeting {
        font-size: var(--text-xl);
        font-weight: var(--weight-emphasis);
        color: var(--text-primary);
        margin: 0;
        line-height: var(--leading-tight);
    }

    .header-subtitle {
        font-size: var(--text-sm);
        color: var(--text-tertiary);
        margin: var(--space-0) 0 0;
    }

    .header-status {
        display: flex;
        align-items: center;
        gap: var(--space-1);
        font-size: var(--text-base);
        color: var(--text-secondary);
    }

    .header-timestamp {
        font-family: var(--font-mono);
        font-size: var(--text-sm);
        color: var(--text-tertiary);
    }

    .recording-status {
        color: var(--color-danger);
    }

    .recording-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--color-danger);
        animation: pulse-dot 1.2s ease-in-out infinite;
    }

    @keyframes pulse-dot {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.3; }
    }

    /* ===== Metrics strip ===== */

    .metrics-strip {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        padding: var(--space-1) var(--space-2);
        background: var(--surface-primary);
        border-radius: var(--radius-sm);
        flex-shrink: 0;
    }

    .metric {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }

    .metric-label {
        font-size: var(--text-xs);
        color: var(--text-tertiary);
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .metric-value {
        font-size: var(--text-sm);
        font-weight: var(--weight-emphasis);
        color: var(--text-primary);
        font-family: var(--font-mono);
    }

    .metric-divider {
        width: 1px;
        height: 24px;
        background: var(--shell-border);
        margin: 0 var(--space-1);
    }

    /* ===== Content layouts ===== */

    .content-center {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: var(--space-3);
    }

    .content-recording {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: var(--space-3);
    }

    .content-text {
        flex: 1;
        overflow-y: auto;
    }

    /* ===== Record button ===== */

    .record-button {
        width: 88px;
        height: 88px;
        border-radius: 50%;
        border: 2px solid var(--accent);
        background: transparent;
        color: var(--accent);
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition:
            background var(--transition-fast),
            border-color var(--transition-fast),
            color var(--transition-fast);
    }

    .record-button:hover {
        background: rgba(90, 159, 212, 0.12);
        border-color: var(--accent-hover);
        color: var(--accent-hover);
    }

    .record-hint {
        font-size: var(--text-sm);
        color: var(--text-tertiary);
    }

    /* ===== Visualizer ===== */

    .visualizer-container {
        flex: 1;
        min-height: 120px;
    }

    /* ===== Stop button ===== */

    .stop-button {
        align-self: center;
        width: 56px;
        height: 56px;
        border-radius: 50%;
        border: 2px solid var(--color-danger);
        background: transparent;
        color: var(--color-danger);
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: background var(--transition-fast);
        flex-shrink: 0;
    }

    .stop-button:hover {
        background: rgba(255, 107, 107, 0.12);
    }

    /* ===== Transcribing ===== */

    .transcribing-text {
        font-size: var(--text-sm);
        color: var(--text-tertiary);
    }

    /* ===== Transcript display ===== */

    .transcript-display {
        font-size: var(--text-base);
        line-height: var(--leading-relaxed);
        color: var(--text-primary);
        white-space: pre-wrap;
        word-break: break-word;
        margin: 0;
    }

    /* ===== Edit area ===== */

    .edit-area {
        width: 100%;
        height: 100%;
        min-height: 200px;
        background: transparent;
        color: var(--text-primary);
        border: none;
        outline: none;
        resize: none;
        font-family: var(--font-family);
        font-size: var(--text-base);
        line-height: var(--leading-relaxed);
        padding: 0;
    }

    .edit-area::placeholder {
        color: var(--text-tertiary);
    }

    /* ===== Action bar ===== */

    .action-bar {
        display: flex;
        align-items: center;
        gap: var(--space-1);
        padding: var(--space-1) 0;
        flex-shrink: 0;
    }

    .action-spacer {
        flex: 1;
    }

    .action-btn {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        height: 32px;
        padding: 0 var(--space-2);
        border: none;
        border-radius: var(--radius-sm);
        font-family: var(--font-family);
        font-size: var(--text-xs);
        font-weight: var(--weight-emphasis);
        cursor: pointer;
        transition:
            background var(--transition-fast),
            color var(--transition-fast);
        white-space: nowrap;
    }

    .action-btn.primary {
        background: var(--accent);
        color: var(--gray-0);
    }
    .action-btn.primary:hover {
        background: var(--accent-hover);
    }

    .action-btn.secondary {
        background: var(--surface-tertiary);
        color: var(--text-primary);
    }
    .action-btn.secondary:hover {
        background: var(--gray-6);
    }

    .action-btn.ghost {
        background: transparent;
        color: var(--text-secondary);
    }
    .action-btn.ghost:hover {
        color: var(--text-primary);
        background: var(--hover-overlay);
    }

    .action-btn.destructive {
        background: transparent;
        color: var(--text-tertiary);
    }
    .action-btn.destructive:hover {
        color: var(--color-danger);
        background: var(--color-danger-surface);
    }

    /* ===== Spinner ===== */

    :global(.spin) {
        animation: spin 1.2s linear infinite;
    }

    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
</style>
