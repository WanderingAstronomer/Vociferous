<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import {
        getTranscript,
        getTranscripts,
        getTags,
        getConfig,
        refineTranscript,
        commitRefinement,
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
            navigator.clipboard.writeText(refinedText);
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
        navigator.clipboard.writeText(originalText);
        copiedOriginal = true;
        setTimeout(() => (copiedOriginal = false), 2000);
    }

    function handleCopyRefined() {
        navigator.clipboard.writeText(refinedText);
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

    onMount(async () => {
        loadPrompts();

        try {
            const cfg = await getConfig();
            const display = cfg.display as Record<string, unknown> | undefined;
            renderMarkdown = Boolean(display?.render_markdown_in_editor);
        } catch { /* default false */ }

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
    });

    onDestroy(() => {
        unsubRefinement?.();
        unsubRefinementError?.();
        unsubRefinementProgress?.();
        stopRefineTimer();
    });

    $effect(() => {
        if (nav.current !== "refine") return;
        const pending = nav.consumePendingTranscriptRequest();
        if (!pending) return;
        if (pending.id === selectedId) return;
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
                    <h3 class="m-0 flex-1 text-center text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-secondary)]">
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
                                <MarkdownBody text={originalText} className="text-[var(--text-sm)] text-[var(--text-primary)]" />
                            {:else}
                                <p class="m-0 text-[var(--text-sm)] text-[var(--text-primary)] whitespace-pre-wrap leading-relaxed">{originalText}</p>
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
                    <h3 class="m-0 flex-1 text-center text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-secondary)]">
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
                            <p class="m-0 text-[var(--text-sm)] text-[var(--text-secondary)] font-[var(--weight-emphasis)]">
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
                                <p class="m-0 mt-[var(--space-1)] text-[var(--text-xs)] text-red-400/80">{refineError}</p>
                            </div>
                        </EmptyState>
                    {:else if refinedText}
                        <WorkspacePanel>
                            {#if showDiff}
                                <DiffView original={originalText} revised={refinedText} className="text-[var(--text-sm)]" />
                            {:else if renderMarkdown}
                                <MarkdownBody text={refinedText} className="text-[var(--text-sm)] text-[var(--text-primary)]" />
                            {:else}
                                <p class="m-0 text-[var(--text-sm)] text-[var(--text-primary)] whitespace-pre-wrap leading-relaxed">{refinedText}</p>
                            {/if}
                        </WorkspacePanel>
                    {:else}
                        <EmptyState
                            icon={Sparkles}
                            message="Ready to refine"
                        />
                    {/if}
                </div>
            </div>
        </div>

        <!-- Analytics Delta (visible after refinement) -->
        {#if hasRefined && refinedText}
            <div class="shrink-0 mx-[var(--space-4)] mb-[var(--space-2)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] bg-[var(--surface-secondary)] px-[var(--space-4)] py-[var(--space-2)]">
                <div class="flex items-center justify-center gap-[var(--space-6)] flex-wrap text-[13px]">
                    <div class="flex items-center gap-1.5">
                        <span class="text-[var(--text-tertiary)]">Words</span>
                        <span class="text-[var(--text-primary)] tabular-nums">{origMetrics.wordCount} → {refMetrics.wordCount}</span>
                        <span class="text-[var(--accent)] tabular-nums text-[12px]">({delta(origMetrics.wordCount, refMetrics.wordCount)})</span>
                    </div>
                    <div class="flex items-center gap-1.5">
                        <span class="text-[var(--text-tertiary)]">Sentences</span>
                        <span class="text-[var(--text-primary)] tabular-nums">{origMetrics.sentenceCount} → {refMetrics.sentenceCount}</span>
                        <span class="text-[var(--accent)] tabular-nums text-[12px]">({delta(origMetrics.sentenceCount, refMetrics.sentenceCount)})</span>
                    </div>
                    <div class="flex items-center gap-1.5">
                        <span class="text-[var(--text-tertiary)]">Avg Sentence</span>
                        <span class="text-[var(--text-primary)] tabular-nums">{origMetrics.avgSentenceLength} → {refMetrics.avgSentenceLength}</span>
                        <span class="text-[var(--accent)] tabular-nums text-[12px]">({deltaF(origMetrics.avgSentenceLength, refMetrics.avgSentenceLength)})</span>
                    </div>
                    <div class="flex items-center gap-1.5">
                        <span class="text-[var(--text-tertiary)]">Grade</span>
                        <span class="text-[var(--text-primary)] tabular-nums">{origMetrics.fkGrade} → {refMetrics.fkGrade}</span>
                        <span class="text-[var(--accent)] tabular-nums text-[12px]">({deltaF(origMetrics.fkGrade, refMetrics.fkGrade)})</span>
                    </div>
                    <div class="flex items-center gap-1.5">
                        <span class="text-[var(--text-tertiary)]">Fillers</span>
                        <span class="text-[var(--text-primary)] tabular-nums">{origMetrics.fillerCount} → {refMetrics.fillerCount}</span>
                        <span class="text-[var(--accent)] tabular-nums text-[12px]">({delta(origMetrics.fillerCount, refMetrics.fillerCount)})</span>
                    </div>
                </div>
            </div>
        {/if}

        <!-- Footer Controls -->
        <div class="px-[var(--space-4)]">
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
                                options={savedPrompts.map((p) => ({ value: String(p.id), label: p.display_name || `Prompt #${p.id}` }))}
                                value={selectedPromptId}
                                onchange={handlePromptSelect}
                                placeholder="Load a saved prompt…"
                            />
                        </div>
                        {#if selectedPromptId}
                            <button
                                class="bg-none border-none text-[var(--text-tertiary)] cursor-pointer p-[var(--space-1)] rounded-[var(--radius-sm)] flex transition-colors duration-[var(--transition-fast)] hover:text-[var(--accent)]"
                                onclick={editSelectedPrompt}
                                title="Edit this prompt"
                            >
                                <ExternalLink size={14} />
                            </button>
                        {/if}
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
        <ActionBar>
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
