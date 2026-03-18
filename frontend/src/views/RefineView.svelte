<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import {
        getTranscript,
        getTranscripts,
        getTags,
        getConfig,
        refineTranscript,
        commitRefinement,
        cancelBulkRefinement,
        type Transcript,
        type Tag,
    } from "../lib/api";
    import { toast } from "../lib/toast.svelte";
    import { ws } from "../lib/ws";
    import { nav } from "../lib/navigation.svelte";
    import { wordCount } from "../lib/formatters";
    import { computeTextMetrics, type TextMetrics } from "../lib/textAnalysis";
    import WorkspacePanel from "../lib/components/WorkspacePanel.svelte";
    import MarkdownBody from "../lib/components/MarkdownBody.svelte";
    import DiffView from "../lib/components/DiffView.svelte";
    import CustomSelect from "../lib/components/CustomSelect.svelte";
    import Tooltip from "../lib/components/Tooltip.svelte";
    import StyledButton from "../lib/components/StyledButton.svelte";
    import EmptyState from "../lib/components/EmptyState.svelte";
    import ActionBar from "../lib/components/ActionBar.svelte";
    import ToggleSwitch from "../lib/components/ToggleSwitch.svelte";
    import {
        Sparkles,
        Copy,
        Check,
        RotateCcw,
        ThumbsUp,
        Pencil,
        Trash2,
        Loader2,
        FileText,
        ExternalLink,
        ArrowUpDown,
        X,
    } from "lucide-svelte";

    const DEFAULT_REFINEMENT_LEVEL = 2;

    /* ── State ── */
    let selectedId: number | null = $state(null);
    let transcriptName = $state("");
    let originalText = $state("");
    let refinedText = $state("");
    let customInstructions = $state("");
    let isRefining = $state(false);
    let hasRefined = $state(false);
    let copied = $state(false);
    let copiedOriginal = $state(false);
    let accepted = $state(false);
    let refineStatus = $state("");
    let refineElapsed = $state(0);
    let refineTimer: ReturnType<typeof setInterval> | null = $state(null);
    let refineError = $state("");
    let showDiff = $state(false);
    let renderMarkdown = $state(false);

    /* ── Prompt System ── */
    let savedPrompts: Transcript[] = $state([]);
    let selectedPromptId: string = $state("");
    let defaultPromptId: number | null = $state(null);

    /* ── Bulk Refinement Tracking ── */
    let bulkRefineActive = $state(false);
    let bulkRefineCompleted = $state(0);
    let bulkRefineFailed = $state(0);
    let bulkRefineTotal = $state(0);

    /* ── Derived analytics ── */
    let origMetrics: TextMetrics = $derived(computeTextMetrics(originalText));
    let refMetrics: TextMetrics = $derived(computeTextMetrics(refinedText));

    /* ── Data ── */
    async function loadPrompts() {
        try {
            const tags = await getTags();
            const promptTag = tags.find((t: Tag) => t.name === "Prompt" && t.is_system);
            if (!promptTag) return;
            const result = await getTranscripts({ limit: 100, tag_ids: [promptTag.id] });
            savedPrompts = result.items;

            if (!selectedPromptId && defaultPromptId) {
                const def = savedPrompts.find((p) => p.id === defaultPromptId);
                if (def) {
                    selectedPromptId = String(def.id);
                }
            }

            // If a prompt is selected, keep customInstructions in sync with
            // any edits that were saved while this view wasn't active.
            if (selectedPromptId) {
                const id = Number(selectedPromptId);
                const fresh = savedPrompts.find((p) => p.id === id);
                if (fresh) {
                    customInstructions = fresh.text || fresh.normalized_text || fresh.raw_text || "";
                }
            }
        } catch (e) {
            console.error("Failed to load saved prompts:", e);
        }
    }

    function handlePromptSelect(val: string) {
        selectedPromptId = val;
        if (!val) return;
        const id = Number(val);
        const prompt = savedPrompts.find((p) => p.id === id);
        if (prompt) {
            customInstructions = prompt.text || prompt.normalized_text || prompt.raw_text || "";
        }
    }

    function editSelectedPrompt() {
        const id = Number(selectedPromptId);
        if (!id) return;
        nav.navigateToEdit(id, { view: "refine", transcriptId: selectedId ?? null });
    }

    async function selectTranscript(id: number) {
        selectedId = id;
        refinedText = "";
        hasRefined = false;
        showDiff = false;
        refineError = "";
        if (isRefining) {
            isRefining = false;
            stopRefineTimer();
        }
        try {
            const t = await getTranscript(id);
            originalText = t.text || t.normalized_text || t.raw_text || "";
            transcriptName = t.display_name?.trim() || `Transcript #${id}`;
        } catch (e) {
            console.error("Failed to load transcript:", e);
            originalText = "";
            transcriptName = "";
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
        refineError = "";
        startRefineTimer();
        try {
            await refineTranscript(selectedId, DEFAULT_REFINEMENT_LEVEL, customInstructions.trim());
        } catch (e) {
            console.error("Refinement failed:", e);
            refineError = e instanceof Error ? e.message : "Refinement request failed. Check that the model is loaded.";
            toast.error(refineError);
            isRefining = false;
            stopRefineTimer();
        }
    }

    async function handleAccept() {
        if (!refinedText || selectedId === null) return;
        try {
            await commitRefinement(selectedId, refinedText);
            navigator.clipboard.writeText(refinedText).catch(() => {});
            originalText = refinedText;
            accepted = true;
            setTimeout(() => (accepted = false), 2000);
            toast.success("Refinement committed");
        } catch (e) {
            toast.error(e instanceof Error ? e.message : "Failed to commit refinement");
        }
    }

    function editSelectedTranscript() {
        if (selectedId == null) return;
        nav.navigateToEdit(selectedId, { view: "refine", transcriptId: selectedId });
    }

    function handleDiscard() {
        refinedText = "";
        hasRefined = false;
        showDiff = false;
    }

    async function handleRerun() {
        refinedText = "";
        hasRefined = false;
        showDiff = false;
        await handleRefine();
    }

    function handleCopyOriginal() {
        navigator.clipboard.writeText(originalText).catch(() => {});
        copiedOriginal = true;
        setTimeout(() => (copiedOriginal = false), 2000);
    }

    function handleCopyRefined() {
        navigator.clipboard.writeText(refinedText).catch(() => {});
        copied = true;
        setTimeout(() => (copied = false), 2000);
    }

    /* ── Analytics helpers ── */
    function delta(a: number, b: number): string {
        const d = b - a;
        if (d === 0) return "—";
        return d > 0 ? `+${d}` : `${d}`;
    }

    function deltaF(a: number, b: number, decimals = 1): string {
        const d = b - a;
        if (Math.abs(d) < 0.05) return "—";
        const s = d.toFixed(decimals);
        return d > 0 ? `+${s}` : s;
    }

    /* ── WebSocket ── */
    let unsubRefinement: (() => void) | undefined;
    let unsubRefinementError: (() => void) | undefined;
    let unsubRefinementProgress: (() => void) | undefined;
    let unsubBulkStarted: (() => void) | undefined;
    let unsubBulkProgress: (() => void) | undefined;
    let unsubBulkComplete: (() => void) | undefined;
    let unsubBulkError: (() => void) | undefined;
    let unsubTranscriptUpdated: (() => void) | undefined;

    onMount(async () => {
        try {
            const cfg = await getConfig();
            const display = cfg.display as Record<string, unknown> | undefined;
            renderMarkdown = Boolean(display?.render_markdown_in_editor);

            const refinement = cfg.refinement as Record<string, unknown> | undefined;
            if (refinement?.default_prompt_transcript_id) {
                defaultPromptId = Number(refinement.default_prompt_transcript_id);
                if (!selectedPromptId && savedPrompts.length > 0) {
                    const def = savedPrompts.find((p) => p.id === defaultPromptId);
                    if (def) {
                        selectedPromptId = String(def.id);
                        customInstructions = def.text || def.normalized_text || def.raw_text || "";
                    }
                }
            }
        } catch {
            /* default false */
        }

        unsubRefinement = ws.on("refinement_complete", (data) => {
            if (data.transcript_id === selectedId) {
                refinedText = data.text;
                isRefining = false;
                hasRefined = true;
                refineError = "";
                stopRefineTimer();
                toast.success("Refinement complete");
            }
        });

        unsubRefinementError = ws.on("refinement_error", (data) => {
            if (!data.transcript_id || data.transcript_id === selectedId) {
                isRefining = false;
                stopRefineTimer();
                refineError = data.message || "Refinement failed unexpectedly.";
                toast.error(refineError);
                console.error("Refinement error:", data.message);
            }
        });

        unsubRefinementProgress = ws.on("refinement_progress", (data) => {
            if (data.transcript_id === selectedId) {
                refineStatus = data.message || "Processing…";
            }
        });

        unsubBulkStarted = ws.on("bulk_refinement_started", (data) => {
            bulkRefineActive = true;
            bulkRefineTotal = data.total;
            bulkRefineCompleted = 0;
            bulkRefineFailed = 0;
        });

        unsubBulkProgress = ws.on("bulk_refinement_progress", (data) => {
            bulkRefineCompleted = data.completed;
            bulkRefineFailed = data.failed;
        });

        unsubBulkComplete = ws.on("bulk_refinement_complete", () => {
            bulkRefineActive = false;
        });

        unsubBulkError = ws.on("bulk_refinement_error", () => {
            bulkRefineActive = false;
        });

        // Reload the saved-prompts list whenever a prompt transcript is edited
        // or whenever a transcript is tagged/untagged as a Prompt.
        unsubTranscriptUpdated = ws.on("transcript_updated", (data) => {
            if (savedPrompts.some((p) => p.id === data.id) || data.tags?.some((t) => t.name === "Prompt")) {
                void loadPrompts();
            }
        });
    });

    onDestroy(() => {
        unsubRefinement?.();
        unsubRefinementError?.();
        unsubRefinementProgress?.();
        unsubBulkStarted?.();
        unsubBulkProgress?.();
        unsubBulkComplete?.();
        unsubBulkError?.();
        unsubTranscriptUpdated?.();
        stopRefineTimer();
    });

    // Reload the saved-prompts list every time the view becomes active so
    // edits made in EditView are immediately reflected in the dropdown.
    $effect(() => {
        if (nav.current === "refine") {
            void loadPrompts();
        }
    });

    $effect(() => {
        if (nav.current !== "refine") return;
        const pending = nav.consumePendingTranscriptRequest();
        if (!pending) return;
        if (pending.id === selectedId) return;

        if (isRefining) {
            toast.warning("A refinement is in progress — wait for it to finish or discard first");
            return;
        }
        if (hasRefined && refinedText && !accepted) {
            toast.warning("Accept or discard the current refinement before switching transcripts");
            return;
        }

        void selectTranscript(pending.id);
    });
</script>

<div class="flex flex-col h-full bg-[var(--surface-primary)] overflow-hidden">
    {#if selectedId === null}
        <!-- No transcript selected — show helpful empty state -->
        <div class="flex-1 flex items-center justify-center">
            <EmptyState
                icon={Sparkles}
                message="Navigate here from Transcribe or Transcriptions to refine a transcript"
            />
        </div>
    {:else}
        <!-- Comparison Area -->
        <div class="flex-1 flex gap-[var(--space-4)] p-[var(--space-4)] min-h-0 overflow-hidden">
            <!-- Original Panel -->
            <div
                class="flex-1 flex flex-col border border-[var(--shell-border)] rounded-[var(--radius-lg)] bg-[var(--surface-secondary)] overflow-hidden"
            >
                <div
                    class="flex items-center py-[var(--space-3)] px-[var(--space-4)] border-b border-[var(--shell-border)]"
                >
                    <div class="flex items-center gap-1 w-10">
                        {#if originalText}
                            <button
                                class="bg-none border-none text-[var(--text-tertiary)] cursor-pointer p-[var(--space-1)] rounded-[var(--radius-sm)] flex transition-colors duration-[var(--transition-fast)] hover:text-[var(--accent)]"
                                onclick={handleCopyOriginal}
                                title="Copy original"
                            >
                                {#if copiedOriginal}
                                    <Check size={14} />
                                {:else}
                                    <Copy size={14} />
                                {/if}
                            </button>
                        {/if}
                    </div>
                    <h3
                        class="m-0 flex-1 text-center text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-secondary)]"
                    >
                        Original Transcript
                    </h3>
                    <div class="flex items-center gap-1 w-10 justify-end">
                        {#if originalText}
                            <button
                                class="bg-none border-none text-[var(--text-tertiary)] cursor-pointer p-[var(--space-1)] rounded-[var(--radius-sm)] flex transition-colors duration-[var(--transition-fast)] hover:text-[var(--accent)]"
                                onclick={editSelectedTranscript}
                                title="Edit transcript"
                            >
                                <Pencil size={14} />
                            </button>
                        {/if}
                    </div>
                </div>
                <div class="flex-1 overflow-y-auto p-[var(--space-4)]">
                    {#if originalText}
                        <WorkspacePanel>
                            {#if renderMarkdown}
                                <MarkdownBody
                                    text={originalText}
                                    className="text-[var(--text-sm)] text-[var(--text-primary)]"
                                />
                            {:else}
                                <p
                                    class="m-0 text-[var(--text-sm)] text-[var(--text-primary)] whitespace-pre-wrap leading-relaxed"
                                >
                                    {originalText}
                                </p>
                            {/if}
                        </WorkspacePanel>
                    {:else}
                        <EmptyState icon={FileText} message="Loading transcript…" />
                    {/if}
                </div>
            </div>

            <!-- Refined Panel -->
            <div
                class="flex-1 flex flex-col border border-[var(--shell-border)] rounded-[var(--radius-lg)] bg-[var(--surface-secondary)] overflow-hidden"
            >
                <div
                    class="flex items-center py-[var(--space-3)] px-[var(--space-4)] border-b border-[var(--shell-border)]"
                >
                    <div class="flex items-center gap-1 w-10">
                        {#if refinedText}
                            <button
                                class="bg-none border-none text-[var(--text-tertiary)] cursor-pointer p-[var(--space-1)] rounded-[var(--radius-sm)] flex transition-colors duration-[var(--transition-fast)] hover:text-[var(--accent)]"
                                onclick={handleCopyRefined}
                                title="Copy refined"
                            >
                                {#if copied}
                                    <Check size={14} />
                                {:else}
                                    <Copy size={14} />
                                {/if}
                            </button>
                        {/if}
                    </div>
                    <h3
                        class="m-0 flex-1 text-center text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-secondary)]"
                    >
                        Refined / AI Suggestion
                    </h3>
                    <div class="flex items-center gap-1 w-10 justify-end">
                        {#if refinedText}
                            <button
                                class="bg-none border-none text-[var(--text-tertiary)] cursor-pointer p-[var(--space-1)] rounded-[var(--radius-sm)] flex transition-colors duration-[var(--transition-fast)] hover:text-[var(--accent)]"
                                onclick={() => (showDiff = !showDiff)}
                                title={showDiff ? "Show clean text" : "Show changes"}
                            >
                                <ArrowUpDown size={14} />
                            </button>
                        {/if}
                    </div>
                </div>
                <div class="flex-1 overflow-y-auto p-[var(--space-4)]">
                    {#if isRefining}
                        <EmptyState icon={Loader2} spinning>
                            <p
                                class="m-0 text-[var(--text-sm)] text-[var(--text-secondary)] font-[var(--weight-emphasis)]"
                            >
                                {refineStatus}
                            </p>
                            <p class="m-0 font-[var(--font-mono)] text-[var(--text-xs)] text-[var(--text-tertiary)]">
                                {refineElapsed}s elapsed
                            </p>
                        </EmptyState>
                    {:else if refineError}
                        <EmptyState>
                            <div
                                class="rounded-[var(--radius-md)] bg-red-500/10 border border-red-500/30 px-[var(--space-4)] py-[var(--space-3)] max-w-md text-center"
                            >
                                <p class="m-0 text-[var(--text-sm)] text-red-400 font-[var(--weight-emphasis)]">
                                    Refinement Failed
                                </p>
                                <p class="m-0 mt-[var(--space-1)] text-[var(--text-xs)] text-red-400/80">
                                    {refineError}
                                </p>
                            </div>
                        </EmptyState>
                    {:else if refinedText}
                        <WorkspacePanel>
                            {#if showDiff}
                                <DiffView
                                    original={originalText}
                                    revised={refinedText}
                                    className="text-[var(--text-sm)]"
                                />
                            {:else if renderMarkdown}
                                <MarkdownBody
                                    text={refinedText}
                                    className="text-[var(--text-sm)] text-[var(--text-primary)]"
                                />
                            {:else}
                                <p
                                    class="m-0 text-[var(--text-sm)] text-[var(--text-primary)] whitespace-pre-wrap leading-relaxed"
                                >
                                    {refinedText}
                                </p>
                            {/if}
                        </WorkspacePanel>
                    {:else}
                        <EmptyState icon={Sparkles} message="Ready to refine" />
                    {/if}
                </div>
            </div>
        </div>

        <!-- Analytics Delta (visible after refinement) -->
        {#if hasRefined && refinedText}
            <div
                class="shrink-0 mx-[var(--space-4)] mb-[var(--space-2)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] bg-[var(--surface-secondary)] px-[var(--space-4)] py-[var(--space-2)]"
            >
                <div class="flex items-center justify-center gap-[var(--space-6)] flex-wrap text-[13px]">
                    <div class="flex items-center gap-1.5">
                        <Tooltip
                            text="Total number of words in the text. Fewer words after refinement usually means filler and redundancy were removed."
                        >
                            <span
                                class="text-[var(--text-tertiary)] cursor-help border-b border-dotted border-[var(--text-tertiary)]/40"
                                >Words</span
                            >
                        </Tooltip>
                        <span class="text-[var(--text-primary)] tabular-nums"
                            >{origMetrics.wordCount} → {refMetrics.wordCount}</span
                        >
                        <span class="text-[var(--accent)] tabular-nums text-[12px]"
                            >({delta(origMetrics.wordCount, refMetrics.wordCount)})</span
                        >
                    </div>
                    <div class="flex items-center gap-1.5">
                        <Tooltip
                            text="Number of sentences detected. Changes indicate the model split or merged sentences for clarity."
                        >
                            <span
                                class="text-[var(--text-tertiary)] cursor-help border-b border-dotted border-[var(--text-tertiary)]/40"
                                >Sentences</span
                            >
                        </Tooltip>
                        <span class="text-[var(--text-primary)] tabular-nums"
                            >{origMetrics.sentenceCount} → {refMetrics.sentenceCount}</span
                        >
                        <span class="text-[var(--accent)] tabular-nums text-[12px]"
                            >({delta(origMetrics.sentenceCount, refMetrics.sentenceCount)})</span
                        >
                    </div>
                    <div class="flex items-center gap-1.5">
                        <Tooltip
                            text="Average number of words per sentence. Lower values mean shorter, punchier sentences. Typical prose is 15–20."
                        >
                            <span
                                class="text-[var(--text-tertiary)] cursor-help border-b border-dotted border-[var(--text-tertiary)]/40"
                                >Avg Sentence Length</span
                            >
                        </Tooltip>
                        <span class="text-[var(--text-primary)] tabular-nums"
                            >{origMetrics.avgSentenceLength} → {refMetrics.avgSentenceLength}</span
                        >
                        <span class="text-[var(--accent)] tabular-nums text-[12px]"
                            >({deltaF(origMetrics.avgSentenceLength, refMetrics.avgSentenceLength)})</span
                        >
                    </div>
                    <div class="flex items-center gap-1.5">
                        <Tooltip
                            text="Flesch-Kincaid Grade Level — the U.S. school grade needed to understand the text. Lower is more accessible. 8–10 is typical for general audiences."
                        >
                            <span
                                class="text-[var(--text-tertiary)] cursor-help border-b border-dotted border-[var(--text-tertiary)]/40"
                                >FK Score</span
                            >
                        </Tooltip>
                        <span class="text-[var(--text-primary)] tabular-nums"
                            >{origMetrics.fkGrade} → {refMetrics.fkGrade}</span
                        >
                        <span class="text-[var(--accent)] tabular-nums text-[12px]"
                            >({deltaF(origMetrics.fkGrade, refMetrics.fkGrade)})</span
                        >
                    </div>
                    <div class="flex items-center gap-1.5">
                        <Tooltip
                            text="Common filler words and phrases like 'um', 'uh', 'you know', 'basically', 'literally'. Fewer is better — refinement should strip most of these."
                        >
                            <span
                                class="text-[var(--text-tertiary)] cursor-help border-b border-dotted border-[var(--text-tertiary)]/40"
                                >Filler Words</span
                            >
                        </Tooltip>
                        <span class="text-[var(--text-primary)] tabular-nums"
                            >{origMetrics.fillerCount} → {refMetrics.fillerCount}</span
                        >
                        <span class="text-[var(--accent)] tabular-nums text-[12px]"
                            >({delta(origMetrics.fillerCount, refMetrics.fillerCount)})</span
                        >
                    </div>
                </div>
            </div>
        {/if}

        <!-- Footer Controls -->
        <div class="px-[var(--space-4)]">
            <!-- Bulk Refinement Progress -->
            {#if bulkRefineActive}
                <div
                    class="flex items-center gap-3 border border-[var(--shell-border)] rounded-[var(--radius-lg)] bg-[var(--surface-secondary)] px-[var(--space-4)] py-[var(--space-2)] mb-[var(--space-2)]"
                >
                    <Loader2 size={14} class="animate-spin text-[var(--accent)] shrink-0" />
                    <span class="text-[13px] text-[var(--text-secondary)]">
                        Bulk refine: {bulkRefineCompleted} of {bulkRefineTotal}
                        {#if bulkRefineFailed > 0}
                            <span class="text-red-400">({bulkRefineFailed} failed)</span>
                        {/if}
                    </span>
                    <div class="flex-1 h-1.5 rounded-full bg-[var(--shell-border)] overflow-hidden">
                        <div
                            class="h-full rounded-full bg-[var(--accent)] transition-all duration-300"
                            style="width: {bulkRefineTotal > 0
                                ? ((bulkRefineCompleted + bulkRefineFailed) / bulkRefineTotal) * 100
                                : 0}%"
                        ></div>
                    </div>
                    <button
                        class="bg-none border-none text-[var(--text-tertiary)] cursor-pointer p-[var(--space-1)] rounded-[var(--radius-sm)] flex transition-colors duration-[var(--transition-fast)] hover:text-red-400"
                        onclick={async () => {
                            try {
                                await cancelBulkRefinement();
                            } catch {}
                        }}
                        title="Cancel bulk refinement"
                    >
                        <X size={14} />
                    </button>
                </div>
            {/if}

            <!-- Custom Instructions Card -->
            <div
                class="flex flex-col gap-[var(--space-2)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] py-[var(--space-3)] px-[var(--space-4)] bg-[var(--surface-secondary)]"
            >
                <h4
                    class="m-0 text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-secondary)] text-center"
                >
                    Instructions (Optional)
                </h4>
                <p class="m-0 text-[var(--text-xs)] text-[var(--text-tertiary)] text-center">
                    Default behavior fixes grammar and punctuation with minimal wording changes.
                </p>
                {#if savedPrompts.length > 0}
                    <div class="flex items-center gap-[var(--space-2)]">
                        <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] shrink-0">Saved Prompts</span>
                        <div class="flex-1">
                            <CustomSelect
                                options={savedPrompts.map((p) => ({
                                    value: String(p.id),
                                    label: p.display_name || `Prompt #${p.id}`,
                                }))}
                                value={selectedPromptId}
                                onchange={handlePromptSelect}
                                placeholder="Load a saved prompt…"
                            />
                        </div>
                        <!-- Always rendered so the CustomSelect width stays stable
                             between the first open (no prompt selected) and subsequent
                             opens (prompt selected). Visibility toggles via CSS only. -->
                        <button
                            class="bg-none border-none text-[var(--text-tertiary)] cursor-pointer p-[var(--space-1)] rounded-[var(--radius-sm)] flex transition-colors duration-[var(--transition-fast)] hover:text-[var(--accent)]"
                            class:invisible={!selectedPromptId}
                            class:pointer-events-none={!selectedPromptId}
                            tabindex={selectedPromptId ? 0 : -1}
                            onclick={editSelectedPrompt}
                            title="Edit this prompt"
                        >
                            <ExternalLink size={14} />
                        </button>
                    </div>
                {/if}
                <textarea
                    class="flex-1 resize-none py-[var(--space-2)] px-[var(--space-3)] border border-[var(--shell-border)] rounded-[var(--radius-sm)] bg-[var(--surface-primary)] text-[var(--text-primary)] text-[var(--text-sm)] font-[inherit] outline-none transition-[border-color] duration-[var(--transition-fast)] focus:border-[var(--accent)] disabled:opacity-50"
                    placeholder="Add specific instructions (e.g., 'Make it bullet points', 'Fix technical jargon')…"
                    bind:value={customInstructions}
                    disabled={isRefining}
                    rows="4"
                ></textarea>
            </div>
        </div>

        <!-- Action Bar -->
        <ActionBar padx="px-[var(--space-4)]">
            {#if hasRefined}
                <StyledButton
                    variant="destructive"
                    size="sm"
                    title="Clear this refinement result from the view"
                    onclick={handleDiscard}
                >
                    <Trash2 size={15} /> Discard
                </StyledButton>
                <div class="flex items-center gap-1.5 ml-2" title="Toggle diff highlight view">
                    <span class="text-[12px] text-[var(--text-tertiary)] whitespace-nowrap select-none">Diff</span>
                    <ToggleSwitch size="sm" checked={showDiff} onChange={() => (showDiff = !showDiff)} />
                </div>
                <div class="flex items-center gap-1.5 ml-2" title="Render text as formatted markdown">
                    <span class="text-[12px] text-[var(--text-tertiary)] whitespace-nowrap select-none">Markdown</span>
                    <ToggleSwitch
                        size="sm"
                        checked={renderMarkdown}
                        onChange={() => (renderMarkdown = !renderMarkdown)}
                    />
                </div>
                <div class="flex-1"></div>
                {#if !accepted}
                    <StyledButton variant="neutral" size="sm" onclick={handleRerun}>
                        <RotateCcw size={15} /> Re-run
                    </StyledButton>
                {/if}
                <StyledButton variant="primary" size="sm" onclick={handleAccept}>
                    {#if accepted}
                        <Check size={15} /> Accepted!
                    {:else}
                        <ThumbsUp size={15} /> Accept & Copy
                    {/if}
                </StyledButton>
            {:else}
                <div class="flex-1"></div>
                <StyledButton
                    variant="primary"
                    size="sm"
                    onclick={handleRefine}
                    disabled={selectedId === null || isRefining}
                >
                    {#if isRefining}
                        <Loader2 size={15} class="spin" /> Refining… {refineElapsed}s
                    {:else}
                        <Sparkles size={15} /> Refine
                    {/if}
                </StyledButton>
            {/if}
        </ActionBar>
    {/if}
</div>
