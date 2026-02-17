<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import { getTranscripts, getTranscript, refineTranscript, type Transcript } from "../lib/api";
    import { ws } from "../lib/ws";
    import { nav } from "../lib/navigation.svelte";
    import WorkspacePanel from "../lib/components/WorkspacePanel.svelte";
    import { Sparkles, Copy, Check, RotateCcw, ThumbsUp, X, Loader2, FileText, ChevronDown } from "lucide-svelte";

    /* ── Strength Levels ── */
    const STRENGTH_LEVELS = [
        { value: 0, label: "Literal", desc: "Mechanical cleanup only; preserve wording." },
        { value: 1, label: "Structural", desc: "Remove disfluencies and speech noise." },
        { value: 2, label: "Neutral", desc: "Professional clarity with moderate rewriting." },
        { value: 3, label: "Intent", desc: "Rewrite for intent and readability." },
        { value: 4, label: "Overkill", desc: "Aggressive restructuring and diction upgrades." },
    ] as const;

    /* ── State ── */
    let transcripts: Transcript[] = $state([]);
    let selectedId: number | null = $state(null);
    let originalText = $state("");
    let refinedText = $state("");
    let strengthLevel = $state(2); // Default: Neutral
    let customInstructions = $state("");
    let isRefining = $state(false);
    let hasRefined = $state(false);
    let copied = $state(false);
    let copiedOriginal = $state(false);
    let accepted = $state(false);
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
        refineTimer = setInterval(() => {
            refineElapsed += 1;
        }, 1000);
    }

    function stopRefineTimer() {
        if (refineTimer) {
            clearInterval(refineTimer);
            refineTimer = null;
        }
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
        navigator.clipboard.writeText(refinedText);
        accepted = true;
        setTimeout(() => (accepted = false), 2000);
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
        loadTranscripts().then(() => {
            // If navigated here with a pending transcript (e.g., from History/Search Refine button)
            const pendingId = nav.consumePendingTranscript();
            if (pendingId != null) {
                selectTranscript(pendingId);
            }
        });

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

<div class="flex flex-col h-full bg-[var(--surface-primary)] overflow-hidden">
    <!-- Transcript Picker (compact top bar) -->
    <div class="relative py-[var(--space-3)] px-[var(--space-4)] border-b border-[var(--shell-border)]">
        <button
            class="flex items-center gap-[var(--space-2)] py-[var(--space-2)] px-[var(--space-3)] border border-[var(--shell-border)] rounded-[var(--radius-md)] bg-[var(--surface-secondary)] text-[var(--text-primary)] text-[var(--text-sm)] cursor-pointer w-full max-w-[400px] text-left transition-[border-color] duration-[var(--transition-fast)] hover:border-[var(--accent)]"
            onclick={() => (showPicker = !showPicker)}
        >
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
            <div
                class="absolute top-full left-[var(--space-4)] right-[var(--space-4)] max-w-[400px] max-h-[280px] overflow-y-auto bg-[var(--surface-primary)] border border-[var(--shell-border)] rounded-[var(--radius-md)] shadow-[0_8px_24px_rgba(0,0,0,0.3)] z-10"
            >
                {#if loadingTranscripts}
                    <div
                        class="p-[var(--space-4)] text-center text-[var(--text-tertiary)] text-[var(--text-sm)] flex items-center justify-center gap-[var(--space-2)]"
                    >
                        <Loader2 size={16} class="spin" /> Loading…
                    </div>
                {:else if transcripts.length === 0}
                    <div
                        class="p-[var(--space-4)] text-center text-[var(--text-tertiary)] text-[var(--text-sm)] flex items-center justify-center gap-[var(--space-2)]"
                    >
                        No transcripts available
                    </div>
                {:else}
                    {#each transcripts as t (t.id)}
                        <button
                            class="flex items-center gap-[var(--space-2)] w-full py-[var(--space-2)] px-[var(--space-3)] border-none bg-transparent text-[var(--text-primary)] text-[var(--text-sm)] text-left cursor-pointer transition-[background] duration-[var(--transition-fast)] hover:bg-[var(--hover-overlay)] {selectedId ===
                            t.id
                                ? 'bg-[rgba(90,159,212,0.1)]'
                                : ''}"
                            onclick={() => selectTranscript(t.id)}
                        >
                            <span class="text-[var(--text-tertiary)] text-[var(--text-xs)] shrink-0 min-w-[32px]"
                                >#{t.id}</span
                            >
                            <span class="overflow-hidden text-ellipsis whitespace-nowrap">{truncateText(t.text)}</span>
                        </button>
                    {/each}
                {/if}
            </div>
        {/if}
    </div>

    <!-- Comparison Area -->
    <div class="flex-1 flex gap-[var(--space-4)] p-[var(--space-4)] min-h-0 overflow-hidden">
        <!-- Original Panel -->
        <div
            class="flex-1 flex flex-col border border-[var(--shell-border)] rounded-[var(--radius-lg)] bg-[var(--surface-secondary)] overflow-hidden"
        >
            <div
                class="flex items-center justify-between py-[var(--space-3)] px-[var(--space-4)] border-b border-[var(--shell-border)]"
            >
                <h3 class="m-0 text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-secondary)]">
                    Original Transcript
                </h3>
                {#if originalText}
                    <button
                        class="bg-none border-none text-[var(--text-tertiary)] cursor-pointer p-[var(--space-1)] rounded-[var(--radius-sm)] flex transition-colors duration-[var(--transition-fast)] hover:text-[var(--accent)]"
                        onclick={handleCopyOriginal}
                    >
                        {#if copiedOriginal}
                            <Check size={14} />
                        {:else}
                            <Copy size={14} />
                        {/if}
                    </button>
                {/if}
            </div>
            <div class="flex-1 overflow-y-auto p-[var(--space-4)]">
                {#if originalText}
                    <WorkspacePanel>
                        <p
                            class="text-[var(--text-sm)] leading-[1.7] text-[var(--text-primary)] m-0 whitespace-pre-wrap"
                        >
                            {originalText}
                        </p>
                    </WorkspacePanel>
                {:else}
                    <div
                        class="flex flex-col items-center justify-center h-full gap-[var(--space-2)] text-[var(--text-tertiary)]"
                    >
                        <FileText size={28} strokeWidth={1.2} />
                        <p class="m-0 text-[var(--text-sm)]">Select a transcript to begin</p>
                    </div>
                {/if}
            </div>
        </div>

        <!-- Refined Panel -->
        <div
            class="flex-1 flex flex-col border border-[var(--shell-border)] rounded-[var(--radius-lg)] bg-[var(--surface-secondary)] overflow-hidden"
        >
            <div
                class="flex items-center justify-between py-[var(--space-3)] px-[var(--space-4)] border-b border-[var(--shell-border)]"
            >
                <h3 class="m-0 text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-secondary)]">
                    Refined / AI Suggestion
                </h3>
                {#if refinedText}
                    <button
                        class="bg-none border-none text-[var(--text-tertiary)] cursor-pointer p-[var(--space-1)] rounded-[var(--radius-sm)] flex transition-colors duration-[var(--transition-fast)] hover:text-[var(--accent)]"
                        onclick={handleCopyRefined}
                    >
                        {#if copied}
                            <Check size={14} />
                        {:else}
                            <Copy size={14} />
                        {/if}
                    </button>
                {/if}
            </div>
            <div class="flex-1 overflow-y-auto p-[var(--space-4)]">
                {#if isRefining}
                    <div
                        class="flex flex-col items-center justify-center h-full gap-[var(--space-2)] text-[var(--text-tertiary)]"
                    >
                        <Loader2 size={28} class="spin" />
                        <p class="m-0 text-[var(--text-sm)] text-[var(--text-secondary)] font-[var(--weight-emphasis)]">
                            {refineStatus}
                        </p>
                        <p class="m-0 font-[var(--font-mono)] text-[var(--text-xs)] text-[var(--text-tertiary)]">
                            {refineElapsed}s elapsed
                        </p>
                    </div>
                {:else if refinedText}
                    <WorkspacePanel>
                        <p
                            class="text-[var(--text-sm)] leading-[1.7] text-[var(--text-primary)] m-0 whitespace-pre-wrap"
                        >
                            {refinedText}
                        </p>
                    </WorkspacePanel>
                {:else}
                    <div
                        class="flex flex-col items-center justify-center h-full gap-[var(--space-2)] text-[var(--text-tertiary)]"
                    >
                        <Sparkles size={28} strokeWidth={1.2} />
                        <p class="m-0 text-[var(--text-sm)]">
                            {selectedId !== null ? "Ready to refine" : "Refinement will appear here"}
                        </p>
                    </div>
                {/if}
            </div>
        </div>
    </div>

    <!-- Footer Controls -->
    <div class="flex gap-[var(--space-4)] px-[var(--space-4)]">
        <!-- Custom Instructions Card -->
        <div
            class="flex-[2] flex flex-col gap-[var(--space-2)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] py-[var(--space-3)] px-[var(--space-4)] bg-[var(--surface-secondary)]"
        >
            <h4
                class="m-0 text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-secondary)] text-center"
            >
                Custom Instructions
            </h4>
            <textarea
                class="flex-1 resize-none py-[var(--space-2)] px-[var(--space-3)] border border-[var(--shell-border)] rounded-[var(--radius-sm)] bg-[var(--surface-primary)] text-[var(--text-primary)] text-[var(--text-sm)] font-[inherit] outline-none transition-[border-color] duration-[var(--transition-fast)] focus:border-[var(--accent)] disabled:opacity-50"
                placeholder="Add specific instructions (e.g., 'Make it bullet points', 'Fix technical jargon')…"
                bind:value={customInstructions}
                disabled={isRefining}
                rows="3"
            ></textarea>
        </div>

        <!-- Strength Selector Card -->
        <div
            class="flex-1 flex flex-col items-center gap-[var(--space-2)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] py-[var(--space-3)] px-[var(--space-4)] bg-[var(--surface-secondary)]"
        >
            <h4
                class="m-0 text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-secondary)] text-center"
            >
                Refinement Strength
            </h4>
            <div class="text-[var(--text-lg)] font-[var(--weight-emphasis)] text-[var(--accent)]">
                {currentStrength.label}
            </div>

            <input
                type="range"
                class="w-full accent-[var(--accent)] cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                min="0"
                max="4"
                step="1"
                bind:value={strengthLevel}
                disabled={isRefining}
            />

            <div class="flex justify-between w-full">
                {#each STRENGTH_LEVELS as level}
                    <span
                        class="text-[var(--text-xs)] transition-colors duration-[var(--transition-fast)] {strengthLevel ===
                        level.value
                            ? 'text-[var(--accent)] font-[var(--weight-emphasis)]'
                            : 'text-[var(--text-tertiary)]'}">{level.label}</span
                    >
                {/each}
            </div>

            <p class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic text-center m-0">
                {currentStrength.desc}
            </p>
        </div>
    </div>

    <!-- Action Bar -->
    <div
        class="flex gap-[var(--space-2)] py-[var(--space-3)] px-[var(--space-4)] border-t border-[var(--shell-border)] justify-center"
    >
        {#if hasRefined}
            <button
                class="accept-btn flex items-center gap-[var(--space-1)] py-[var(--space-2)] px-[var(--space-4)] border rounded-[var(--radius-md)] text-white text-[var(--text-sm)] font-[var(--weight-emphasis)] cursor-pointer transition-[color,border-color,background,transform] duration-[var(--transition-fast)] {accepted
                    ? 'border-[var(--color-success)] bg-[var(--color-success)]'
                    : 'border-[var(--accent)] bg-[var(--accent)] hover:bg-[var(--blue-5)] hover:border-[var(--blue-5)]'}"
                onclick={handleAccept}
            >
                {#if accepted}
                    <Check size={15} /> Copied!
                {:else}
                    <ThumbsUp size={15} /> Accept & Copy
                {/if}
            </button>
            <button
                class="flex items-center gap-[var(--space-1)] py-[var(--space-2)] px-[var(--space-4)] border border-[var(--shell-border)] rounded-[var(--radius-md)] bg-[var(--surface-secondary)] text-[var(--text-secondary)] text-[var(--text-sm)] font-[var(--weight-emphasis)] cursor-pointer transition-[color,border-color,background] duration-[var(--transition-fast)] hover:text-[var(--text-primary)] hover:border-[var(--accent)]"
                onclick={handleRerun}
            >
                <RotateCcw size={15} /> Re-run
            </button>
            <button
                class="flex items-center gap-[var(--space-1)] py-[var(--space-2)] px-[var(--space-4)] border border-[var(--shell-border)] rounded-[var(--radius-md)] bg-[var(--surface-secondary)] text-[var(--text-secondary)] text-[var(--text-sm)] font-[var(--weight-emphasis)] cursor-pointer transition-[color,border-color,background] duration-[var(--transition-fast)] hover:text-[var(--text-primary)] hover:border-[var(--accent)]"
                onclick={handleDiscard}
            >
                <X size={15} /> Discard
            </button>
        {:else}
            <button
                class="flex items-center gap-[var(--space-1)] py-[var(--space-2)] px-[var(--space-4)] border border-[var(--accent)] rounded-[var(--radius-md)] bg-[var(--accent)] text-white text-[var(--text-sm)] font-[var(--weight-emphasis)] cursor-pointer transition-[color,border-color,background] duration-[var(--transition-fast)] hover:bg-[var(--blue-5)] hover:border-[var(--blue-5)] disabled:opacity-50 disabled:cursor-not-allowed"
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
    .accept-btn:active {
        transform: scale(0.93);
    }
</style>
