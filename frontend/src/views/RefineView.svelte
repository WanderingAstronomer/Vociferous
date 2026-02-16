<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import {
        getTranscripts,
        getTranscript,
        refineTranscript,
        type Transcript,
    } from "../lib/api";
    import { ws } from "../lib/ws";
    import WorkspacePanel from "../lib/components/WorkspacePanel.svelte";
    import {
        Sparkles,
        Copy,
        Check,
        RotateCcw,
        ThumbsUp,
        X,
        Loader2,
        FileText,
        ChevronDown,
    } from "lucide-svelte";

    /* ── Strength Levels ── */
    const STRENGTH_LEVELS = [
        { value: 0, label: "Minimal", desc: "Light cleanup — punctuation & formatting" },
        { value: 1, label: "Balanced", desc: "Grammar fixes & natural flow" },
        { value: 2, label: "Strong", desc: "Rewrite for clarity & conciseness" },
        { value: 3, label: "Overkill", desc: "Aggressive restructuring & polish" },
    ] as const;

    /* ── State ── */
    let transcripts: Transcript[] = $state([]);
    let selectedId: number | null = $state(null);
    let originalText = $state("");
    let refinedText = $state("");
    let strengthLevel = $state(1); // Default: Balanced
    let customInstructions = $state("");
    let isRefining = $state(false);
    let hasRefined = $state(false);
    let copied = $state(false);
    let copiedOriginal = $state(false);
    let showPicker = $state(false);
    let loadingTranscripts = $state(true);
    let refineStatus = $state("");
    let refineElapsed = $state(0);
    let refineTimer: ReturnType<typeof setInterval> | null = $state(null);

    let currentStrength = $derived(STRENGTH_LEVELS[strengthLevel]);

    /* ── Data ── */
    async function loadTranscripts() {
        try {
            transcripts = await getTranscripts(100);
        } catch (e) {
            console.error("Failed to load transcripts:", e);
        } finally {
            loadingTranscripts = false;
        }
    }

    async function selectTranscript(id: number) {
        selectedId = id;
        refinedText = "";
        hasRefined = false;
        showPicker = false;
        try {
            const t = await getTranscript(id);
            originalText = t.text;
        } catch (e) {
            console.error("Failed to load transcript:", e);
            originalText = "";
        }
    }

    /* ── Actions ── */
    function startRefineTimer() {
        refineElapsed = 0;
        refineStatus = "Preparing…";
        if (refineTimer) clearInterval(refineTimer);
        refineTimer = setInterval(() => { refineElapsed += 1; }, 1000);
    }

    function stopRefineTimer() {
        if (refineTimer) { clearInterval(refineTimer); refineTimer = null; }
        refineStatus = "";
    }

    async function handleRefine() {
        if (selectedId === null || isRefining) return;
        isRefining = true;
        startRefineTimer();
        try {
            await refineTranscript(selectedId, strengthLevel, customInstructions.trim());
            // Wait for WebSocket event to deliver result
        } catch (e) {
            console.error("Refinement failed:", e);
            isRefining = false;
            stopRefineTimer();
        }
    }

    function handleAccept() {
        if (!refinedText) return;
        // Copy refined text and reset
        navigator.clipboard.writeText(refinedText);
        copied = true;
        setTimeout(() => (copied = false), 2000);
    }

    function handleDiscard() {
        refinedText = "";
        hasRefined = false;
    }

    async function handleRerun() {
        refinedText = "";
        hasRefined = false;
        await handleRefine();
    }

    function handleCopyOriginal() {
        navigator.clipboard.writeText(originalText);
        copiedOriginal = true;
        setTimeout(() => (copiedOriginal = false), 2000);
    }

    function handleCopyRefined() {
        navigator.clipboard.writeText(refinedText);
        copied = true;
        setTimeout(() => (copied = false), 2000);
    }

    /* ── Formatting ── */
    function truncateText(text: string, max = 50): string {
        if (text.length <= max) return text;
        return text.slice(0, max) + "…";
    }

    /* ── WebSocket ── */
    let unsubRefinement: (() => void) | undefined;
    let unsubRefinementError: (() => void) | undefined;
    let unsubRefinementProgress: (() => void) | undefined;

    onMount(() => {
        loadTranscripts();

        unsubRefinement = ws.on("refinement_complete", (data) => {
            if (data.transcript_id === selectedId) {
                refinedText = data.text;
                isRefining = false;
                hasRefined = true;
                stopRefineTimer();
            }
        });

        unsubRefinementError = ws.on("refinement_error", (data) => {
            if (!data.transcript_id || data.transcript_id === selectedId) {
                isRefining = false;
                stopRefineTimer();
                console.error("Refinement error:", data.message);
            }
        });

        unsubRefinementProgress = ws.on("refinement_progress", (data) => {
            if (data.transcript_id === selectedId) {
                refineStatus = data.message || "Processing…";
            }
        });
    });

    onDestroy(() => {
        unsubRefinement?.();
        unsubRefinementError?.();
        unsubRefinementProgress?.();
        stopRefineTimer();
    });
</script>

<div class="refine-view">
    <!-- Transcript Picker (compact top bar) -->
    <div class="picker-bar">
        <button class="picker-toggle" onclick={() => (showPicker = !showPicker)}>
            <FileText size={15} />
            <span>
                {#if selectedId !== null}
                    Transcript #{selectedId}
                {:else}
                    Select a transcript to refine…
                {/if}
            </span>
            <ChevronDown size={14} />
        </button>

        {#if showPicker}
            <div class="picker-dropdown">
                {#if loadingTranscripts}
                    <div class="picker-loading"><Loader2 size={16} class="spin" /> Loading…</div>
                {:else if transcripts.length === 0}
                    <div class="picker-empty">No transcripts available</div>
                {:else}
                    {#each transcripts as t (t.id)}
                        <button
                            class="picker-item"
                            class:active={selectedId === t.id}
                            onclick={() => selectTranscript(t.id)}
                        >
                            <span class="picker-id">#{t.id}</span>
                            <span class="picker-text">{truncateText(t.text)}</span>
                        </button>
                    {/each}
                {/if}
            </div>
        {/if}
    </div>

    <!-- Comparison Area -->
    <div class="comparison">
        <!-- Original Panel -->
        <div class="panel">
            <div class="panel-header">
                <h3>Original Transcript</h3>
                {#if originalText}
                    <button class="panel-action" onclick={handleCopyOriginal}>
                        {#if copiedOriginal}
                            <Check size={14} />
                        {:else}
                            <Copy size={14} />
                        {/if}
                    </button>
                {/if}
            </div>
            <div class="panel-body">
                {#if originalText}
                    <WorkspacePanel>
                        <p class="panel-text">{originalText}</p>
                    </WorkspacePanel>
                {:else}
                    <div class="panel-empty">
                        <FileText size={28} strokeWidth={1.2} />
                        <p>Select a transcript to begin</p>
                    </div>
                {/if}
            </div>
        </div>

        <!-- Refined Panel -->
        <div class="panel">
            <div class="panel-header">
                <h3>Refined / AI Suggestion</h3>
                {#if refinedText}
                    <button class="panel-action" onclick={handleCopyRefined}>
                        {#if copied}
                            <Check size={14} />
                        {:else}
                            <Copy size={14} />
                        {/if}
                    </button>
                {/if}
            </div>
            <div class="panel-body">
                {#if isRefining}
                    <div class="panel-loading">
                        <Loader2 size={28} class="spin" />
                        <p class="refine-status">{refineStatus}</p>
                        <p class="refine-elapsed">{refineElapsed}s elapsed</p>
                    </div>
                {:else if refinedText}
                    <WorkspacePanel>
                        <p class="panel-text">{refinedText}</p>
                    </WorkspacePanel>
                {:else}
                    <div class="panel-empty">
                        <Sparkles size={28} strokeWidth={1.2} />
                        <p>{selectedId !== null ? "Ready to refine" : "Refinement will appear here"}</p>
                    </div>
                {/if}
            </div>
        </div>
    </div>

    <!-- Footer Controls -->
    <div class="footer-controls">
        <!-- Custom Instructions Card -->
        <div class="control-card instructions-card">
            <h4 class="card-label">Custom Instructions</h4>
            <textarea
                class="instructions-input"
                placeholder="Add specific instructions (e.g., 'Make it bullet points', 'Fix technical jargon')…"
                bind:value={customInstructions}
                disabled={isRefining}
                rows="3"
            ></textarea>
        </div>

        <!-- Strength Selector Card -->
        <div class="control-card strength-card">
            <h4 class="card-label">Refinement Strength</h4>
            <div class="strength-display">{currentStrength.label}</div>

            <input
                type="range"
                class="strength-slider"
                min="0"
                max="3"
                step="1"
                bind:value={strengthLevel}
                disabled={isRefining}
            />

            <div class="strength-labels">
                {#each STRENGTH_LEVELS as level}
                    <span
                        class="strength-tick"
                        class:active={strengthLevel === level.value}
                    >{level.label}</span>
                {/each}
            </div>

            <p class="strength-help">{currentStrength.desc}</p>
        </div>
    </div>

    <!-- Action Bar -->
    <div class="refine-actions">
        {#if hasRefined}
            <button class="action-btn primary" onclick={handleAccept}>
                <ThumbsUp size={15} /> Accept & Copy
            </button>
            <button class="action-btn" onclick={handleRerun}>
                <RotateCcw size={15} /> Re-run
            </button>
            <button class="action-btn" onclick={handleDiscard}>
                <X size={15} /> Discard
            </button>
        {:else}
            <button
                class="action-btn primary"
                onclick={handleRefine}
                disabled={selectedId === null || isRefining}
            >
                {#if isRefining}
                    <Loader2 size={15} class="spin" /> Refining… {refineElapsed}s
                {:else}
                    <Sparkles size={15} /> Refine
                {/if}
            </button>
        {/if}
    </div>
</div>

<style>
    /* ── Layout ── */
    .refine-view {
        display: flex;
        flex-direction: column;
        height: 100%;
        background: var(--surface-primary);
        overflow: hidden;
    }

    /* ── Picker Bar ── */
    .picker-bar {
        position: relative;
        padding: var(--space-3) var(--space-4);
        border-bottom: 1px solid var(--shell-border);
    }

    .picker-toggle {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        padding: var(--space-2) var(--space-3);
        border: 1px solid var(--shell-border);
        border-radius: var(--radius-md);
        background: var(--surface-secondary);
        color: var(--text-primary);
        font-size: var(--text-sm);
        cursor: pointer;
        width: 100%;
        max-width: 400px;
        text-align: left;
        transition: border-color var(--transition-fast);
    }

    .picker-toggle:hover {
        border-color: var(--accent);
    }

    .picker-dropdown {
        position: absolute;
        top: 100%;
        left: var(--space-4);
        right: var(--space-4);
        max-width: 400px;
        max-height: 280px;
        overflow-y: auto;
        background: var(--surface-primary);
        border: 1px solid var(--shell-border);
        border-radius: var(--radius-md);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
        z-index: 10;
    }

    .picker-loading,
    .picker-empty {
        padding: var(--space-4);
        text-align: center;
        color: var(--text-tertiary);
        font-size: var(--text-sm);
        display: flex;
        align-items: center;
        justify-content: center;
        gap: var(--space-2);
    }

    .picker-item {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        width: 100%;
        padding: var(--space-2) var(--space-3);
        border: none;
        background: transparent;
        color: var(--text-primary);
        font-size: var(--text-sm);
        text-align: left;
        cursor: pointer;
        transition: background var(--transition-fast);
    }

    .picker-item:hover {
        background: var(--hover-overlay);
    }

    .picker-item.active {
        background: rgba(90, 159, 212, 0.1);
    }

    .picker-id {
        color: var(--text-tertiary);
        font-size: var(--text-xs);
        flex-shrink: 0;
        min-width: 32px;
    }

    .picker-text {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    /* ── Comparison ── */
    .comparison {
        flex: 1;
        display: flex;
        gap: var(--space-4);
        padding: var(--space-4);
        min-height: 0;
        overflow: hidden;
    }

    .panel {
        flex: 1;
        display: flex;
        flex-direction: column;
        border: 1px solid var(--shell-border);
        border-radius: var(--radius-lg);
        background: var(--surface-secondary);
        overflow: hidden;
    }

    .panel-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: var(--space-3) var(--space-4);
        border-bottom: 1px solid var(--shell-border);
    }

    .panel-header h3 {
        margin: 0;
        font-size: var(--text-base);
        font-weight: var(--weight-emphasis);
        color: var(--text-secondary);
    }

    .panel-action {
        background: none;
        border: none;
        color: var(--text-tertiary);
        cursor: pointer;
        padding: var(--space-1);
        border-radius: var(--radius-sm);
        display: flex;
        transition: color var(--transition-fast);
    }

    .panel-action:hover {
        color: var(--accent);
    }

    .panel-body {
        flex: 1;
        overflow-y: auto;
        padding: var(--space-4);
    }

    .panel-text {
        font-size: var(--text-sm);
        line-height: 1.7;
        color: var(--text-primary);
        margin: 0;
        white-space: pre-wrap;
    }

    .panel-empty,
    .panel-loading {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 100%;
        gap: var(--space-2);
        color: var(--text-tertiary);
    }

    .panel-empty p,
    .panel-loading p {
        margin: 0;
        font-size: var(--text-sm);
    }

    .refine-status {
        color: var(--text-secondary);
        font-weight: var(--weight-emphasis);
    }

    .refine-elapsed {
        font-family: var(--font-mono);
        font-size: var(--text-xs);
        color: var(--text-tertiary);
    }

    /* ── Footer ── */
    .footer-controls {
        display: flex;
        gap: var(--space-4);
        padding: 0 var(--space-4);
    }

    .control-card {
        border: 1px solid var(--shell-border);
        border-radius: var(--radius-lg);
        padding: var(--space-3) var(--space-4);
        background: var(--surface-secondary);
    }

    .instructions-card {
        flex: 2;
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
    }

    .strength-card {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--space-2);
    }

    .card-label {
        margin: 0;
        font-size: var(--text-base);
        font-weight: var(--weight-emphasis);
        color: var(--text-secondary);
        text-align: center;
    }

    .instructions-input {
        flex: 1;
        resize: none;
        padding: var(--space-2) var(--space-3);
        border: 1px solid var(--shell-border);
        border-radius: var(--radius-sm);
        background: var(--surface-primary);
        color: var(--text-primary);
        font-size: var(--text-sm);
        font-family: inherit;
        outline: none;
        transition: border-color var(--transition-fast);
    }

    .instructions-input:focus {
        border-color: var(--accent);
    }

    .instructions-input:disabled {
        opacity: 0.5;
    }

    /* ── Strength Selector ── */
    .strength-display {
        font-size: var(--text-lg);
        font-weight: var(--weight-emphasis);
        color: var(--accent);
    }

    .strength-slider {
        width: 100%;
        accent-color: var(--accent);
        cursor: pointer;
    }

    .strength-slider:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    .strength-labels {
        display: flex;
        justify-content: space-between;
        width: 100%;
    }

    .strength-tick {
        font-size: var(--text-xs);
        color: var(--text-tertiary);
        transition: color var(--transition-fast);
    }

    .strength-tick.active {
        color: var(--accent);
        font-weight: var(--weight-emphasis);
    }

    .strength-help {
        font-size: var(--text-xs);
        color: var(--text-tertiary);
        font-style: italic;
        text-align: center;
        margin: 0;
    }

    /* ── Action Bar ── */
    .refine-actions {
        display: flex;
        gap: var(--space-2);
        padding: var(--space-3) var(--space-4);
        border-top: 1px solid var(--shell-border);
        justify-content: center;
    }

    .action-btn {
        display: flex;
        align-items: center;
        gap: var(--space-1);
        padding: var(--space-2) var(--space-4);
        border: 1px solid var(--shell-border);
        border-radius: var(--radius-md);
        background: var(--surface-secondary);
        color: var(--text-secondary);
        font-size: var(--text-sm);
        font-weight: var(--weight-emphasis);
        cursor: pointer;
        transition: color var(--transition-fast), border-color var(--transition-fast), background var(--transition-fast);
    }

    .action-btn:hover {
        color: var(--text-primary);
        border-color: var(--accent);
    }

    .action-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    .action-btn.primary {
        background: var(--accent);
        color: white;
        border-color: var(--accent);
    }

    .action-btn.primary:hover {
        background: var(--blue-5);
        border-color: var(--blue-5);
    }

    .action-btn.primary:disabled {
        background: var(--accent);
        opacity: 0.5;
    }

    /* ── Spin ── */
    :global(.spin) {
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        to {
            transform: rotate(360deg);
        }
    }
</style>
